"""AsOf HTTP API (FastAPI).

    python -m asof.api                      # http://127.0.0.1:8000, docs at /docs

Every input is validated (lengths in UTF-8 bytes, because Db2 VARCHAR limits are bytes;
dates in a sane range; doc_id from an allow-list; no control characters). LLM-backed
endpoints are rate-limited per client. Errors never expose stack traces or SQL.
"""

from __future__ import annotations

import argparse
import hmac
import logging
import re
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__, db, impactagent, ledger, policy
from .askledger import LedgerAsker
from .assistant import DemoAssistant
from .config import ConfigError, Settings, get_settings
from .embeddings import get_embeddings
from .gate import Gate, GateRequest, GateResult
from .llm import LLMError, build_llm

log = logging.getLogger("asof.api")

MIN_DATE, MAX_DATE = date(2020, 1, 1), date(2035, 12, 31)
MAX_BODY_BYTES = 64 * 1024
UI_DIR = __import__("pathlib").Path(__file__).with_name("ui")
LOCAL_CLIENTS = {"127.0.0.1", "::1"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _text(max_bytes: int) -> Callable[[str], str]:
    def check(value: str) -> str:
        if _CONTROL.search(value):
            raise ValueError("control characters are not allowed")
        if len(value.encode("utf-8")) > max_bytes:
            raise ValueError(f"must be at most {max_bytes} bytes in UTF-8")
        return value
    return check


class BodyLimit:
    """Refuse request bodies over MAX_BODY_BYTES, counted as they stream in.

    The Content-Length check in the guard middleware rejects declared sizes early; this catches a
    chunked body, which has no Content-Length, before the application reads more than the limit.
    """

    def __init__(self, app, limit: int = MAX_BODY_BYTES):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        seen = 0

        async def limited():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    raise HTTPException(413, "request body too large")
            return message

        return await self.app(scope, limited, send)


def token_matches(given: str | None, expected: str) -> bool:
    """Constant-time comparison on UTF-8 bytes (hmac.compare_digest refuses non-ASCII str)."""
    return bool(given) and hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def _in_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise ValueError(f"must be between {MIN_DATE} and {MAX_DATE}")
    return value


Question = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_text(2000))]
Draft = Annotated[str, Field(min_length=1, max_length=4000), AfterValidator(_text(4000))]
AsOfDate = Annotated[date, AfterValidator(_in_range)]
DocId = Literal["AURELIA-CSP", "FERNHOLLOW-FEES"]  # the policy documents in domains.DOMAINS
Channel = Literal["chat", "email", "faq", "api", "demo"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GateIn(_In):
    question: Question
    draft_answer: Draft
    as_of_date: AsOfDate = Field(description="The date that decides which policy applies (booking or travel date). "
                                             "Supplied by the calling system, never guessed.")
    doc_id: DocId = "AURELIA-CSP"
    channel: Channel = "api"


class AskIn(_In):
    question: Question
    as_of_date: AsOfDate
    doc_id: DocId = "AURELIA-CSP"
    channel: Channel = "demo"


class ClaimOut(BaseModel):
    pass_no: int
    claim_no: int
    text: str
    area: str
    verdict: str
    llm_verdict: str | None
    rule_check: str
    rule_details: list[str]
    clause_id: str | None
    clause_title: str | None
    clause_version: str | None
    effective_from: date | None
    effective_to: date | None
    clause_text: str | None
    quoted_span: str | None
    reason: str


class GateOut(BaseModel):
    request_id: str
    ledger_id: int | None
    decision: str
    reason_code: str
    released: bool
    final_answer: str
    rewrite: str | None
    latency_ms: int
    model: str
    claims: list[ClaimOut]
    unchecked: list[str] = Field(default_factory=list, description="Details in the draft that no extracted claim "
                                 "stated; any makes the draft escalate.")


def _claims(result: GateResult) -> list[ClaimOut]:
    out = []
    for pass_no, items in ((1, result.claims), (2, result.rewrite_claims)):
        for c in items:
            cl = c.clause
            out.append(ClaimOut(
                pass_no=pass_no, claim_no=c.claim_no, text=c.text, area=c.area, verdict=c.verdict,
                llm_verdict=c.llm_verdict, rule_check=c.rule_check, rule_details=c.rule_details,
                clause_id=cl.clause_id if cl else None, clause_title=cl.title if cl else None,
                clause_version=cl.version_label if cl else None, effective_from=cl.bus_start if cl else None,
                effective_to=cl.bus_end if cl else None, clause_text=cl.clause_text if cl else None,
                quoted_span=c.quoted_span, reason=c.reason))
    return out


def gate_out(result: GateResult) -> GateOut:
    return GateOut(request_id=result.request_id, ledger_id=result.ledger_id, decision=result.decision,
                   reason_code=result.reason_code, released=result.released, final_answer=result.final_answer,
                   rewrite=result.rewrite, latency_ms=result.latency_ms, model=result.model_info, claims=_claims(result),
                   unchecked=result.unchecked)


class RateLimiter:
    """Sliding window per client address, for the endpoints that spend LLM calls."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


class LedgerQuestionIn(_In):
    question: Annotated[str, Field(min_length=3, max_length=500), AfterValidator(_text(500))]


class SuggestionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


def create_app(settings: Settings | None = None, *, gate: Gate | None = None, assistant: DemoAssistant | None = None,
               asker: LedgerAsker | None = None, schema: str = db.SCHEMA, rate_limit: int = 30) -> FastAPI:
    settings = settings or get_settings()
    state: dict[str, Any] = {"gate": gate, "assistant": assistant, "asker": asker}
    api_token = settings.asof_api_token.get_secret_value() if settings.asof_api_token else None
    limiter = RateLimiter(rate_limit)

    def app_conn():
        return db.connect(settings, "app")

    def components() -> tuple[Gate, DemoAssistant]:
        if state["gate"] is None or state["assistant"] is None:
            llm = build_llm(settings)
            emb = get_embeddings(settings.embedding_model)
            state["gate"] = state["gate"] or Gate(llm, emb, app_conn, schema)
            state["assistant"] = state["assistant"] or DemoAssistant(llm, emb, app_conn, schema)
        return state["gate"], state["assistant"]

    def ledger_asker() -> LedgerAsker:
        if state["asker"] is None:
            state["asker"] = LedgerAsker(components()[0].llm, settings, schema)
        return state["asker"]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            components()
        except ConfigError as exc:
            log.error("AsOf is not configured: %s", exc)
        yield

    app = FastAPI(title="AsOf", version=__version__, lifespan=lifespan,
                  description="Checks AI assistant answers against the policy in force on a date. Built on IBM Db2.")
    app.add_middleware(BodyLimit)
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=[h.strip() for h in settings.asof_allowed_hosts.split(",") if h.strip()])

    @app.middleware("http")
    async def guard(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"error": "request body too large"}, status_code=413)
        if api_token and request.url.path.startswith("/api/"):
            auth = request.headers.get("authorization", "")
            given = auth[7:].strip() if auth[:7].lower() == "bearer " else None
            if not token_matches(given, api_token):
                return JSONResponse({"error": "this AsOf server needs an API token (Authorization: Bearer ...)"},
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if request.method == "POST" and not limiter.allow(request.client.host if request.client else "unknown"):
            return JSONResponse({"error": "too many requests, try again in a minute"}, status_code=429)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(db.DatabaseError)
    async def _db_error(_: Request, exc: db.DatabaseError):
        log.error("database error: %s", exc)
        return JSONResponse({"error": "the database is unavailable", "sqlstate": exc.sqlstate}, status_code=503)

    @app.exception_handler(ConfigError)
    async def _config_error(_: Request, exc: ConfigError):
        log.error("configuration error: %s", exc)  # names the missing keys and the .env path: server log only
        return JSONResponse({"error": "the server configuration is incomplete; see the server log"}, status_code=500)

    @app.exception_handler(LLMError)
    async def _llm_error(_: Request, exc: LLMError):
        log.error("LLM error: %s", exc)
        return JSONResponse({"error": "the language model is unavailable"}, status_code=503)

    @app.get("/healthz")
    def healthz():
        try:
            conn = app_conn()
            try:
                db.query(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
            finally:
                conn.close()
            db_state = "ok"
        except ConfigError:
            db_state = "error: not configured"
        except db.DatabaseError as exc:
            db_state = f"error: SQLSTATE {exc.sqlstate or 'unknown'}"  # no host, user or message details
        return {"status": "ok" if db_state == "ok" else "degraded", "db2": db_state,
                "llm": f"{settings.llm_provider}:{settings.llm_model_name}", "version": __version__}

    def respond(result: GateResult) -> JSONResponse:
        body = gate_out(result).model_dump(mode="json")
        return JSONResponse(body, status_code=200 if result.released else 503)

    @app.post("/api/gate", response_model=GateOut)
    def check_answer(body: GateIn):
        g, _ = components()
        return respond(g.check(GateRequest(body.question, body.draft_answer, body.as_of_date, body.doc_id, body.channel)))

    @app.post("/api/assistant/ask")
    def ask_assistant(body: AskIn):
        g, a = components()
        draft = a.answer(body.question)
        result = g.check(GateRequest(body.question, draft.text, body.as_of_date, body.doc_id, body.channel))
        out = gate_out(result).model_dump(mode="json")
        out["assistant"] = {"draft": draft.text, "faq_ids": draft.faq_ids, "latency_ms": draft.latency_ms}
        return JSONResponse(out, status_code=200 if result.released else 503)

    @app.get("/api/ledger")
    def list_ledger(limit: Annotated[int, Query(ge=1, le=100)] = 25, offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
                    decision: Literal["PASS", "CORRECTED", "ESCALATED"] | None = None):
        conn = app_conn()
        try:
            rows = ledger.list_entries(conn, schema, limit, offset, decision)
        finally:
            conn.close()
        return [{k: r[k] for k in ("ledger_id", "created_at", "channel", "as_of_date", "decision", "reason_code",
                                   "question_redacted", "model_info", "latency_ms", "row_hash")} for r in rows]

    @app.post("/api/ledger/ask")
    def ask_the_ledger(body: LedgerQuestionIn):
        """Plain-English questions over the audit views, answered as the read-only analyst.

        The generated SQL runs only after the SQLGlot check, and is returned with the rows so the
        answer can be checked against them. The SQL and any Db2 message shown are the analyst's
        own query, never the application's.
        """
        return ledger_asker().ask(body.question).as_dict()

    @app.get("/api/ledger/{ledger_id}")
    def ledger_entry(ledger_id: Annotated[int, Path(ge=1)]):
        conn = app_conn()
        try:
            entry = ledger.get_entry(conn, ledger_id, schema)
        finally:
            conn.close()
        if entry is None:
            raise HTTPException(404, "no such ledger entry")
        return entry

    @app.get("/api/ledger/{ledger_id}/replay")
    def ledger_replay(ledger_id: Annotated[int, Path(ge=1)]):
        conn = app_conn()
        try:
            out = ledger.replay(conn, ledger_id, schema)
        finally:
            conn.close()
        if out is None:
            raise HTTPException(404, "no such ledger entry")
        return out

    @app.get("/api/chain/verify")
    def chain_verify():
        conn = app_conn()
        try:
            s = ledger.verify_chain(conn, schema)
        finally:
            conn.close()
        return {"status": s.status, "rows_checked": s.checked, "first_bad_ledger_id": s.first_bad, "detail": s.detail}

    @app.get("/api/policy/timeline")
    def policy_timeline(doc_id: DocId | None = None):
        conn = app_conn()
        try:
            return policy.timeline(conn, schema, doc_id)
        finally:
            conn.close()

    @app.get("/api/policy/clauses/{clause_id}/history")
    def clause_history(clause_id: Annotated[str, Path(pattern=r"^[A-Z]{3}-[0-9]{3}$")]):
        conn = app_conn()
        try:
            rows = policy.history(conn, clause_id, schema)
        finally:
            conn.close()
        if not rows:
            raise HTTPException(404, "no such clause")
        return rows

    @app.get("/api/impact/{clause_id}")
    def impact(clause_id: Annotated[str, Path(pattern=r"^[A-Z]{3}-[0-9]{3}$")]):
        conn = app_conn()
        try:
            return policy.change_impact(conn, clause_id, schema)
        finally:
            conn.close()

    @app.get("/api/analytics")
    def analytics():
        conn = app_conn()
        try:
            return policy.analytics(conn, schema)
        finally:
            conn.close()

    def require_editor(request: Request, token_header: str | None) -> None:
        """Editor actions: localhost only, or a matching ASOF_EDITOR_TOKEN (constant-time compare)."""
        token = settings.asof_editor_token.get_secret_value() if settings.asof_editor_token else None
        if token:
            if not token_matches(token_header, token):
                raise HTTPException(403, "policy changes need a valid X-AsOf-Editor-Token")
        elif (request.client.host if request.client else "") not in LOCAL_CLIENTS:
            raise HTTPException(403, "policy changes are only accepted from localhost unless ASOF_EDITOR_TOKEN is set")

    @app.post("/api/impact/{clause_id}/suggestions")
    def draft_suggestions(clause_id: Annotated[str, Path(pattern=r"^[A-Z]{3}-[0-9]{3}$")], request: Request,
                          x_asof_editor_token: Annotated[str | None, Header()] = None):
        """Run the change-impact agent: draft and check corrections for stale help-centre answers."""
        require_editor(request, x_asof_editor_token)
        drafted = impactagent.draft_fixes(components()[0], clause_id)
        conn = app_conn()
        try:
            return {"drafted": drafted, "suggestions": policy.suggestions(conn, clause_id, schema)}
        finally:
            conn.close()

    @app.get("/api/suggestions")
    def list_suggestions(clause_id: Annotated[str | None, Query(pattern=r"^[A-Z]{3}-[0-9]{3}$")] = None):
        conn = app_conn()
        try:
            return policy.suggestions(conn, clause_id, schema)
        finally:
            conn.close()

    @app.post("/api/suggestions/{suggestion_id}/decision")
    def decide(suggestion_id: Annotated[int, Path(ge=1, le=10**12)], body: SuggestionDecision, request: Request,
               x_asof_editor_token: Annotated[str | None, Header()] = None):
        """The policy editor approves (publishes) or rejects a drafted correction."""
        require_editor(request, x_asof_editor_token)
        editor = db.connect(settings, "editor")
        try:
            try:
                published = policy.decide_suggestion(editor, suggestion_id, body.approve, schema)
            except db.DatabaseError as exc:
                if exc.sqlstate in ("75022",):
                    raise HTTPException(404, "no such suggestion") from None
                if exc.sqlstate in ("75023", "75024"):
                    raise HTTPException(409, str(exc).split(": ", 1)[-1]) from None
                raise
        finally:
            editor.close()
        return {"suggestion_id": suggestion_id, "approved": body.approve, "published_answer_id": published or None}

    @app.post("/api/policy/change")
    def change_policy(body: policy.PolicyChange, request: Request,
                      x_asof_editor_token: Annotated[str | None, Header()] = None):
        require_editor(request, x_asof_editor_token)
        editor = db.connect(settings, "editor")
        try:
            try:
                result = policy.apply_change(editor, body, get_embeddings(settings.embedding_model), schema)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            except db.DatabaseError as exc:
                if exc.sqlstate and exc.sqlstate.startswith("750"):
                    raise HTTPException(422, str(exc).split(": ", 1)[-1]) from None
                raise
            return result | {"impact": policy.change_impact(editor, body.clause_id, schema)}
        finally:
            editor.close()

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/ui/")

    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    return app


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(prog="python -m asof.api")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
