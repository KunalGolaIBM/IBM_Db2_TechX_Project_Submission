"""AsOf HTTP API (FastAPI).

    python -m asof.api                      # http://127.0.0.1:8000, docs at /docs

Every input is validated (lengths in UTF-8 bytes, because Db2 VARCHAR limits are bytes;
dates in a sane range; doc_id from an allow-list; no control characters). LLM-backed
endpoints are rate-limited per client. Errors never expose stack traces or SQL.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import logging
import re
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path as PathlibPath  # fastapi's Path is the route parameter
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import (
    __version__,
    backtest,
    db,
    demolive,
    headline,
    impactagent,
    intake,
    ledger,
    notices,
    policy,
    redteam,
    review,
    router,
    rowaccess,
    trusted,
)
from .anchor import AnchorLog
from .anchor import verify as verify_anchors
from .askledger import LedgerAsker
from .assistant import DemoAssistant
from .config import ConfigError, Settings, get_settings
from .embeddings import get_embeddings
from .gate import Gate, GateRequest, GateResult
from .llm import LLMError, build_llm
from .replay import ReplayMiss
from .users import APIUser, authenticate

log = logging.getLogger("asof.api")

MIN_DATE, MAX_DATE = date(2020, 1, 1), date(2035, 12, 31)
MAX_BODY_BYTES = 64 * 1024
# GETs that do real work in Db2 share the POST rate limit: VERIFY_CHAIN recomputes every hash in the ledger.
COSTLY_GETS = frozenset({"/api/chain/verify", "/api/chain/anchors"})

_EDITOR_POSTS = re.compile(r"^/api/(?:policy/(?:change|preview|drafts|drafts/[^/]+/decision)|impact/[^/]+/suggestions"
                           r"|suggestions/[^/]+/decision)$")
# The one route that takes more than MAX_BODY_BYTES: a policy document upload (asof/intake.py).
UPLOAD_PATH = "/api/policy/drafts"
UPLOAD_LIMIT = intake.MAX_PDF_BYTES
BACKTEST_PATH = "/api/backtests"  # the other large body: a CSV of past answers (asof/backtest.py)


def body_limit(method: str, path: str) -> int:
    if method == "POST" and path == BACKTEST_PATH:
        return backtest.MAX_CSV_BYTES
    return UPLOAD_LIMIT if method == "POST" and path == UPLOAD_PATH else MAX_BODY_BYTES


def required_role(method: str, path: str) -> str | None:
    """The role an /api/ request needs with ASOF_AUTH=users. None: any signed-in user. A route not named
    here needs the auditor role, so a new route is never open by accident."""
    if method == "POST" and path in ("/api/gate", "/api/assistant/ask", BACKTEST_PATH):
        return "checker"
    if method == "POST" and _EDITOR_POSTS.match(path):
        return "editor"
    if path.startswith(("/api/reviews", "/api/notices")):  # the specialist inbox, reads and writes
        return "reviewer"
    if method == "GET" and (path.startswith("/api/policy/") or path == "/api/whoami"):
        return None
    return "auditor"


COSTLY_GET_SUFFIXES = ("/evidence",)  # evidence packs run VERIFY_CHAIN too
UI_DIR = PathlibPath(__file__).with_name("ui")
LOCAL_CLIENTS = {"127.0.0.1", "::1"}
# What the public demo's pages say in place of the replay-mode advice to add a model key.
PUBLIC_DEMO_NOTICE = ("Public demo: the built-in scenarios replay recorded model outputs while Db2 runs live. "
                      "To check your own answers, run AsOf locally with ./quickstart.sh.")
NO_MODEL = ("No language model is configured: add OPENROUTER_API_KEY to .env, or set LLM_PROVIDER=ollama with Ollama "
            "running, or LLM_PROVIDER=replay to replay the built-in scenarios, then restart AsOf.")
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

    def __init__(self, app, limit: int | None = None):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        seen = 0
        limit = self.limit or body_limit(scope.get("method", ""), scope.get("path", ""))

        async def limited():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise HTTPException(413, "request body too large")
            return message

        return await self.app(scope, limited, send)


def token_matches(given: str | None, expected: str) -> bool:
    """Constant-time comparison on UTF-8 bytes (hmac.compare_digest refuses non-ASCII str)."""
    if not given:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


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
    doc_id: DocId | Literal["auto"] = Field("AURELIA-CSP", description="The policy document, or auto to let the router "
                                            "decide (it asks a person rather than guess; asof/router.py).")
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
    row_hash: str | None = Field(None, description="Receipt: the decision's SHA-256 ledger row hash. Kept outside Db2, "
                                 "it proves later (POST /api/ledger/receipt) that the record was not rewritten.")
    route: dict[str, Any] | None = Field(None, description="With doc_id auto: which document the router chose and why, "
                                         "or why it asked a person instead (decision ESCALATED, reason ROUTE_UNCERTAIN).")


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
                   unchecked=result.unchecked, row_hash=result.row_hash)


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


ROW_REF = r"^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?$"


def row_ref(value: str) -> tuple[date, datetime]:
    """`2026-05-01_2026-11-06T04:00:00.123456`: a clause row's business start and the time Db2 recorded it."""
    start, recorded = value.split("_", 1)
    try:
        return date.fromisoformat(start), datetime.fromisoformat(recorded)
    except ValueError:
        raise HTTPException(422, "a row is named <business start>_<recorded at>, both ISO 8601") from None


class LedgerQuestionIn(_In):
    question: Annotated[str, Field(min_length=3, max_length=500), AfterValidator(_text(500))]
    # "all" (the all-domain analyst) or a domain key from GET /api/ledger/ask/scopes (that domain's analyst).
    scope: str = Field("all", pattern=r"^[a-z]{1,20}$")


class LedgerAttackIn(_In):
    attack: Literal["delete", "messages", "tables", "update", "heavy"]
    scope: str = Field("all", pattern=r"^[a-z]{1,20}$")


class ReceiptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_id: int = Field(ge=1, le=10**12)
    row_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class DraftDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    accept: list[Annotated[int, Field(ge=1, le=12)]] = Field(default_factory=list, max_length=12)
    preview: bool = False


class SuggestionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


class NoticeDraftIn(_In):
    clause_id: Annotated[str, Field(pattern=r"^[A-Z]{3}-[0-9]{3}$")]


class NoticeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


class ReplyIn(_In):
    """A specialist's reply to a held decision. doc_id may differ from the held one only when the router was unsure."""
    reply: Annotated[str, Field(min_length=1, max_length=review.MAX_REPLY_CHARS), AfterValidator(_text(4000))]
    note: Annotated[str, Field(max_length=1000), AfterValidator(_text(1000))] | None = None
    doc_id: DocId | None = None


def create_app(settings: Settings | None = None, *, gate: Gate | None = None, assistant: DemoAssistant | None = None,
               asker: LedgerAsker | None = None, schema: str = db.SCHEMA, rate_limit: int = 30,
               intake_model: Any = None, read_limit: int = 240, live: demolive.LiveChecks | None = None,
               backtest_guard: backtest.BeforeCheck | None = None,
               backtest_launch: Callable[[Callable[[], None]], None] | None = None) -> FastAPI:
    settings = settings or get_settings()
    state: dict[str, Any] = {"gate": gate, "assistant": assistant, "asker": asker, "intake_llm": intake_model}
    users_mode = settings.asof_auth == "users"
    api_token = settings.asof_api_token.get_secret_value() if settings.asof_api_token and not users_mode else None
    if users_mode and (settings.asof_api_token or settings.asof_editor_token):
        log.warning("ASOF_AUTH=users: the shared ASOF_API_TOKEN and ASOF_EDITOR_TOKEN are not used")
    limiter = RateLimiter(rate_limit)
    demo = settings.asof_public_demo
    reads = RateLimiter(read_limit)  # public demo only: every API read is limited per address too

    def client_address(request: Request) -> str:
        """The caller's address. The public demo sits behind its own Caddy on the same machine, so the peer is always
        local: the caller is the last X-Forwarded-For entry, which Caddy sets (it drops whatever the client sent)."""
        host = request.client.host if request.client else "unknown"
        if demo and host in LOCAL_CLIENTS:
            return request.headers.get("x-forwarded-for", "").split(",")[-1].strip() or "proxy"
        return host

    def is_local(request: Request) -> bool:
        return not demo and (request.client.host if request.client else "") in LOCAL_CLIENTS

    def demo_off(what: str) -> None:
        """Refuse an action that changes policy or sends something, in the public demo only."""
        if demo:
            raise HTTPException(403, f"Disabled in the public demo: {what}. Every check and every read works here; "
                                     "to try this too, run AsOf locally with ./quickstart.sh (one command, no API key).")

    # Runtime connections are pooled: on the dev machine opening one costs about 0.2 s and closing it
    # about 0.9 s, and a check uses three (see db.ConnectionPool).
    # ASOF_TRUSTED_CONTEXT: trusted connections, each request switched to its API user's Db2 ID (asof/trusted.py).
    pool = db.ConnectionPool(settings, "app", trusted=settings.asof_trusted_context)
    anchors = AnchorLog.from_settings(settings, schema)  # None: ASOF_ANCHOR_KEY unset, anchoring off

    def app_conn():
        return pool.connect()

    start_lock = threading.Lock()  # sync routes run in a thread pool: two first requests must not build two gates

    def components() -> tuple[Gate, DemoAssistant]:
        if state["gate"] is None or state["assistant"] is None:
            with start_lock:
                if state["gate"] is None or state["assistant"] is None:
                    if not settings.llm_ready:  # a plain answer for the person setting it up, without server paths
                        raise HTTPException(503, NO_MODEL)
                    llm = build_llm(settings)
                    emb = get_embeddings(settings.embedding_model)
                    state["gate"] = state["gate"] or Gate(llm, emb, app_conn, schema,
                                                          deadline_s=settings.asof_check_deadline_s, anchors=anchors)
                    state["assistant"] = state["assistant"] or DemoAssistant(llm, emb, app_conn, schema)
        return state["gate"], state["assistant"]

    def intake_llm():
        """The model for policy intake: same provider and fallback as checks, larger output cap, longer deadline."""
        if state.get("intake_llm") is None:
            if not settings.llm_ready:
                raise HTTPException(503, NO_MODEL)
            state["intake_llm"] = build_llm(settings, max_output_tokens=settings.asof_intake_max_output_tokens,
                                            deadline_s=settings.asof_intake_timeout_s)
        return state["intake_llm"]

    def doc_router() -> router.Router:
        """The router behind doc_id "auto". Its agent gets the configured model without the local fallback, so a failed
        routing call asks a person instead of letting an unmeasured model decide; ASOF_ROUTER_AGENT says when it runs."""
        if state.get("router") is None:
            llm = None
            if settings.asof_router_agent != "off" and settings.llm_ready:
                client = build_llm(settings, fallback=False)
                llm = client if router.agent_runs(settings.asof_router_agent, client.info) else None
            log.info("routing agent: %s", llm.info if llm else "off (close calls go to a person)")
            state["router"] = router.Router(get_embeddings(settings.embedding_model), app_conn, schema, llm)
        return state["router"]

    def ledger_asker() -> LedgerAsker:
        if state["asker"] is None:
            state["asker"] = LedgerAsker(components()[0].llm, settings, schema)
        return state["asker"]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if not settings.llm_ready:  # start anyway: the timeline, ledger and impact screens need no model
            log.warning("no language model configured; checks will answer 503 until one is")
        else:
            try:
                components()
            except ConfigError as exc:
                log.error("AsOf is not configured: %s", exc)
        yield
        pool.close()

    app = FastAPI(title="AsOf", version=__version__, lifespan=lifespan,
                  description="Checks AI assistant answers against the policy in force on a date. Built on IBM Db2.")
    app.add_middleware(BodyLimit)
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=[h.strip() for h in settings.asof_allowed_hosts.split(",") if h.strip()])

    def lookup_user(token: str | None) -> APIUser | None:
        if not token:
            return None
        conn = app_conn()
        try:
            return authenticate(conn, token, schema)
        finally:
            conn.close()

    def requested_by(request: Request) -> str | None:
        user = getattr(request.state, "user", None)
        return user.name if user else None

    @app.middleware("http")
    async def guard(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > body_limit(request.method, request.url.path):
            return JSONResponse({"error": "request body too large"}, status_code=413)
        auth = request.headers.get("authorization", "")
        given = auth[7:].strip() if auth[:7].lower() == "bearer " else None
        user: APIUser | None = None
        if users_mode and request.url.path.startswith("/api/"):
            try:
                user = await run_in_threadpool(lookup_user, given)
            except db.DatabaseError as exc:
                log.error("API user lookup failed: %s", exc)
                return JSONResponse({"error": "the database is unavailable", "sqlstate": exc.sqlstate}, status_code=503)
            if user is None:
                return JSONResponse({"error": "this AsOf server needs your personal API token (Authorization: Bearer ...)"},
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
            role = required_role(request.method, request.url.path)
            if role and not user.can(role):
                return JSONResponse({"error": f"API user {user.name} does not have the {role} role"}, status_code=403)
            request.state.user = user
        elif api_token and request.url.path.startswith("/api/"):
            if not token_matches(given, api_token):
                return JSONResponse({"error": "this AsOf server needs an API token (Authorization: Bearer ...)"},
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
        costly = (request.method == "POST" or request.url.path in COSTLY_GETS
                  or request.url.path.endswith(COSTLY_GET_SUFFIXES))
        caller = f"user:{user.name}" if user else client_address(request)
        if costly and not limiter.allow(caller):
            return JSONResponse({"error": "too many requests, try again in a minute"}, status_code=429)
        if demo and not costly and request.url.path.startswith("/api/") and not reads.allow(caller):
            return JSONResponse({"error": "too many requests, try again in a minute"}, status_code=429)
        # Trusted context: everything this request does on the runtime pool runs in Db2 as its API user.
        as_user = db.SESSION_USER.set(trusted.authid(user.name)) if user and settings.asof_trusted_context else None
        try:
            response = await call_next(request)
        finally:
            if as_user is not None:
                db.SESSION_USER.reset(as_user)
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
        if isinstance(exc, ReplayMiss) and demo:
            return JSONResponse({"error": "This public demo runs in replay mode, with recorded model outputs for the "
                                          "built-in scenarios only: pick one of the suggested questions. To ask anything "
                                          "else, run AsOf locally with a model key."}, status_code=503)
        if isinstance(exc, ReplayMiss):  # replay mode on an input it has no recording for: say so, plainly
            return JSONResponse({"error": "Replay mode has recorded model outputs only for the built-in scenarios. "
                                          "To ask anything else, add OPENROUTER_API_KEY and set LLM_PROVIDER=openrouter "
                                          "in .env (or use Ollama), then restart."}, status_code=503)
        return JSONResponse({"error": "the language model is unavailable"}, status_code=503)

    # ---------- live checks on the public demo (asof/demolive.py) ----------
    # With ASOF_DEMO_LIVE=true, an input the recording holds exactly replays; anything else is a live check, if one can
    # start (input limits, then the pause, the visitor's limits, free slots and Db2's daily cap); otherwise it is refused.
    def live_gate(llm: demolive.Meter) -> Gate:
        return Gate(llm, get_embeddings(settings.embedding_model), app_conn, schema,
                    deadline_s=min(settings.asof_check_deadline_s, demolive.LIVE_CHECK_DEADLINE_S), anchors=anchors)

    def live_assistant(llm: demolive.Meter) -> DemoAssistant:
        return DemoAssistant(llm, get_embeddings(settings.embedding_model), app_conn, schema)

    if not (demo and settings.asof_demo_live):
        live = None
    elif live is None:
        live = demolive.LiveChecks.from_settings(settings, app_conn, schema, live_gate, live_assistant)
        log.info("public demo: live checks %s (%s, %d a day, %d recorded inputs replay)",
                 "on" if live.available else "unavailable: no OPENROUTER_API_KEY in the environment", live.model,
                 live.cap, len(live.recorded))

    def live_limits(model: type[BaseModel], **fields: str) -> None:
        """The live input limits, checked before anything else runs; a 422 like any other invalid input."""
        try:
            model.model_validate(fields)
        except ValidationError as exc:
            raise RequestValidationError([{**e, "loc": ("body", *e["loc"])} for e in exc.errors()]) from None

    def run_gate(g: Gate, req: GateRequest, request: Request) -> GateResult:
        """Check one draft: replayed if the recording holds it exactly, else live (or refused, in the demo)."""
        if live is None or live.recorded_gate(req.doc_id, req.question, req.draft_answer, req.as_of):
            return g.check(req)
        with live.check(client_address(request)) as session:
            result: GateResult = session.gate.check(req)
            return result

    @app.exception_handler(demolive.LiveRefused)
    async def _live_refused(_: Request, exc: demolive.LiveRefused):
        log.warning("live check refused (%s)", exc.reason)
        return JSONResponse({"error": exc.message, "reason": exc.reason,
                             "live_checks": "unavailable" if exc.reason == "unavailable" else "paused"},
                            status_code=exc.status,
                            headers={"Retry-After": str(exc.retry_after_s)} if exc.retry_after_s else None)

    def replay_model() -> str | None:
        from .replay import shipped_model

        return shipped_model() if settings.llm_provider == "replay" else None

    @app.get("/healthz")
    def healthz(request: Request):
        clock = None
        try:
            conn = app_conn()
            try:
                clock = db.utc_label(db.query(conn, "SELECT CURRENT TIMEZONE FROM SYSIBM.SYSDUMMY1")[0][0])
            finally:
                conn.close()
            db_state = "ok"
        except ConfigError:
            db_state = "error: not configured"
        except db.DatabaseError as exc:
            db_state = f"error: SQLSTATE {exc.sqlstate or 'unknown'}"  # no host, user or message details
        live_now = live.status(client_address(request)) if live is not None else None  # says nothing about the key
        return {"status": "ok" if db_state == "ok" and settings.llm_ready else "degraded", "db2": db_state,
                "db2_clock": clock,  # the zone of every Db2 timestamp the UI shows
                "llm": f"{settings.llm_provider}:{settings.llm_model_name}", "llm_ready": settings.llm_ready,
                "replay": settings.llm_provider == "replay", "replay_model": replay_model(),
                "anchoring": "on" if anchors is not None else "off", "db2_tls": settings.db2_ssl,
                "auth": "users" if users_mode else ("token" if api_token else "local"),
                "public_demo": demo,
                "public_demo_notice": live_now["notice"] if live_now else (PUBLIC_DEMO_NOTICE if demo else None),
                "live_checks": live_now["state"] if live_now else None, "live_model": live.model if live else None,
                "headline": headline.banner(),  # the measured results banner, from the published result files
                "version": __version__}

    def respond(result: GateResult) -> JSONResponse:
        body = gate_out(result).model_dump(mode="json")
        return JSONResponse(body, status_code=200 if result.released else 503)

    @app.get("/api/whoami")
    def whoami(request: Request):
        user = getattr(request.state, "user", None)
        return {"auth": "users" if users_mode else ("token" if api_token else "local"),
                "user": user.name if user else None, "roles": sorted(user.roles) if user else None}

    @app.post("/api/gate", response_model=GateOut)
    def check_answer(body: GateIn, request: Request):
        if live is not None:
            live_limits(demolive.LiveGateIn, question=body.question, draft_answer=body.draft_answer)
        g, _ = components()
        if body.doc_id != "auto":
            return respond(run_gate(g, GateRequest(body.question, body.draft_answer, body.as_of_date, body.doc_id,
                                                   body.channel, requested_by(request)), request))
        r = doc_router().route(body.question, body.draft_answer, body.as_of_date)
        req = GateRequest(body.question, body.draft_answer, body.as_of_date, r.doc_id or r.leader, body.channel,
                          requested_by(request), r.as_json())
        result = run_gate(g, req, request) if r.doc_id else g.hold(req, "ROUTE_UNCERTAIN", f"router:{r.method}")
        out = gate_out(result).model_dump(mode="json") | {"route": jsonable_encoder(router.describe(r))}
        return JSONResponse(out, status_code=200 if result.released else 503)

    @app.post("/api/assistant/ask")
    def ask_assistant(body: AskIn, request: Request):
        if live is not None:
            live_limits(demolive.LiveAskIn, question=body.question)
        g, a = components()
        if live is not None and not live.recorded_ask(body.doc_id, body.question, body.as_of_date):
            with live.check(client_address(request)) as session:
                return assistant_reply(session.gate, session.assistant, body, request)
        return assistant_reply(g, a, body, request)

    def assistant_reply(g: Gate, a: DemoAssistant, body: AskIn, request: Request) -> JSONResponse:
        draft = a.answer(body.question)
        result = g.check(GateRequest(body.question, draft.text, body.as_of_date, body.doc_id, body.channel,
                                     requested_by(request)))
        out = gate_out(result).model_dump(mode="json")
        out["assistant"] = {"draft": draft.text, "faq_ids": draft.faq_ids, "latency_ms": draft.latency_ms}
        return JSONResponse(out, status_code=200 if result.released else 503)

    @app.get("/api/ledger")
    def list_ledger(limit: Annotated[int, Query(ge=1, le=100)] = 25, offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
                    decision: Literal["PASS", "CORRECTED", "ESCALATED", "REVIEWED"] | None = None):
        conn = app_conn()
        try:
            rows = ledger.list_entries(conn, schema, limit, offset, decision)
        finally:
            conn.close()
        return [{k: r[k] for k in ("ledger_id", "created_at", "channel", "as_of_date", "decision", "reason_code",
                                   "question_redacted", "model_info", "latency_ms", "row_hash", "uncovered")} for r in rows]

    @app.post("/api/ledger/ask")
    def ask_the_ledger(body: LedgerQuestionIn):
        """Plain-English questions over the audit views, answered as the read-only analyst.

        The generated SQL runs only after the SQLGlot check, and is returned with the rows so the
        answer can be checked against them. The SQL and any Db2 message shown are the analyst's
        own query, never the application's.
        """
        if body.scope not in {s.key for s in rowaccess.scopes(settings)}:
            raise HTTPException(422, f"unknown scope {body.scope!r}: see GET /api/ledger/ask/scopes")
        return ledger_asker().ask(body.question, scope=body.scope).as_dict()

    @app.post("/api/ledger/attack")
    def ask_the_ledger_attack(body: LedgerAttackIn):
        """An attack chip: fixed SQL of the kind a manipulated model might write, sent through the same layers as the
        model's SQL, with the layer that stopped it (asof/redteam.py). No model is called."""
        if body.scope not in {s.key for s in rowaccess.scopes(settings)}:
            raise HTTPException(422, f"unknown scope {body.scope!r}: see GET /api/ledger/ask/scopes")
        return redteam.run(ledger_asker(), body.attack, body.scope).as_dict()

    @app.get("/api/ledger/attacks")
    def ask_the_ledger_attacks():
        """The attack chips: key, label and the SQL each sends."""
        return [{"key": a.key, "label": a.label, "sql": a.sql} for a in redteam.ATTACKS.values()]

    @app.get("/api/ledger/ask/scopes")
    def ask_the_ledger_scopes():
        """Who Ask the ledger can run as: every domain (the all-domain analyst), then one analyst per domain whose
        decisions alone Db2's row permissions return."""
        return [s.as_dict() for s in rowaccess.scopes(settings)]

    @app.get("/api/ledger/{ledger_id}")
    def ledger_entry(ledger_id: Annotated[int, Path(ge=1, le=10**12)]):
        conn = app_conn()
        try:
            entry = ledger.get_entry(conn, ledger_id, schema)
            if entry is not None:  # the specialist inbox's link, in either direction
                kind = entry["decision"].strip()
                entry["review"] = (review.review_of(conn, ledger_id, schema) if kind == "ESCALATED"
                                   else review.reviewed_for(conn, ledger_id, schema) if kind == "REVIEWED" else None)
        finally:
            conn.close()
        if entry is None:
            raise HTTPException(404, "no such ledger entry")
        return entry

    @app.get("/api/ledger/{ledger_id}/replay")
    def ledger_replay(ledger_id: Annotated[int, Path(ge=1, le=10**12)]):
        conn = app_conn()
        try:
            out = ledger.replay(conn, ledger_id, schema)
        finally:
            conn.close()
        if out is None:
            raise HTTPException(404, "no such ledger entry")
        return out

    @app.get("/api/ledger/{ledger_id}/evidence")
    def ledger_evidence(ledger_id: Annotated[int, Path(ge=1, le=10**12)]):
        """An evidence pack for one decision, as a JSON download (runs VERIFY_CHAIN, so rate-limited)."""
        conn = app_conn()
        try:
            out = ledger.evidence(conn, ledger_id, schema, anchors=anchors)
        finally:
            conn.close()
        if out is None:
            raise HTTPException(404, "no such ledger entry")
        return JSONResponse(jsonable_encoder(out), headers={
            "Content-Disposition": f'attachment; filename="asof-evidence-{ledger_id}.json"'})

    @app.post("/api/ledger/receipt")
    def check_receipt(body: ReceiptIn):
        """Does the ledger still hold the row a receipt was issued for? Runs VERIFY_CHAIN too."""
        conn = app_conn()
        try:
            r = ledger.check_receipt(conn, body.ledger_id, body.row_hash, schema)
        finally:
            conn.close()
        return {"ledger_id": r.ledger_id, "verdict": r.verdict, "found": r.found, "matches": r.matches,
                "chain_status": r.chain.status, "first_bad_ledger_id": r.chain.first_bad}

    @app.get("/api/chain/anchors")
    def chain_anchors():
        """Every chain-head anchor kept outside Db2 against the ledger now (catches a consistent rebuild)."""
        if anchors is None:
            return {"status": "OFF", "detail": "no ASOF_ANCHOR_KEY: chain-head anchoring is off"}
        conn = app_conn()
        try:
            return verify_anchors(anchors, conn, schema).as_dict()
        finally:
            conn.close()

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

    @app.get("/api/policy/clauses/{clause_id}/diff")
    def clause_diff(clause_id: Annotated[str, Path(pattern=r"^[A-Z]{3}-[0-9]{3}$")],
                    a: Annotated[str, Query(pattern=ROW_REF)], b: Annotated[str, Query(pattern=ROW_REF)]):
        """Two rows of a clause from its system-time history, compared: text word by word, RULE_JSON key by key.
        Each row is named `<business start>_<recorded at>`, the `from` and `recorded_at` of /history."""
        conn = app_conn()
        try:
            out = policy.diff(conn, clause_id, row_ref(a), row_ref(b), schema)
        finally:
            conn.close()
        if out is None:
            raise HTTPException(404, "no such clause version")
        return out

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
        """Editor actions: localhost only, or a matching ASOF_EDITOR_TOKEN (constant-time compare). With
        ASOF_AUTH=users the middleware has already required the editor role, from any client."""
        demo_off("changing policy")
        if users_mode:
            return
        token = settings.asof_editor_token.get_secret_value() if settings.asof_editor_token else None
        if token:
            if not token_matches(token_header, token):
                raise HTTPException(403, "policy changes need a valid X-AsOf-Editor-Token")
        elif not is_local(request):
            raise HTTPException(403, "policy changes are only accepted from localhost unless ASOF_EDITOR_TOKEN is set")

    def require_local_reviewer(request: Request) -> None:
        """Specialist actions in local mode: localhost only, as for editors, unless a token already authenticated the
        caller (ASOF_API_TOKEN, or ASOF_AUTH=users, where the middleware required the reviewer role)."""
        demo_off("specialist actions that record or send something")
        if users_mode or api_token:
            return
        if not is_local(request):
            raise HTTPException(403, "specialist actions are only accepted from localhost unless ASOF_AUTH=users or "
                                     "ASOF_API_TOKEN is set")

    @app.post("/api/impact/{clause_id}/suggestions")
    def draft_suggestions(clause_id: Annotated[str, Path(pattern=r"^[A-Z]{3}-[0-9]{3}$")], request: Request,
                          x_asof_editor_token: Annotated[str | None, Header()] = None):
        """Run the change-impact agent: draft and check corrections for stale help-centre answers."""
        demo_off("drafting help-centre corrections")
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
        demo_off("publishing or rejecting a help-centre correction")
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

    def as_editor(body: policy.PolicyChange, request: Request, token: str | None, preview: bool) -> dict[str, Any]:
        if not preview:
            demo_off("applying a policy change (Preview impact works: Db2 rolls it back)")
        if not (demo and preview):  # the demo's previews run in a transaction Db2 rolls back
            require_editor(request, token)
        if (who := requested_by(request)) is not None:  # the editor's name goes into the clause's change note
            body = body.model_copy(update={"change_note": f"[{who}] {body.change_note}"[:400]})
        editor = db.connect(settings, "editor")
        try:
            emb = get_embeddings(settings.embedding_model)
            try:
                if preview:
                    return policy.preview_change(editor, body, emb, schema)
                result = policy.apply_change(editor, body, emb, schema)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            except db.DatabaseError as exc:
                if exc.sqlstate and exc.sqlstate.startswith("750"):
                    raise HTTPException(422, str(exc).split(": ", 1)[-1]) from None
                raise
            return result | {"impact": policy.change_impact(editor, body.clause_id, schema)}
        finally:
            editor.close()

    @app.post("/api/policy/change")
    def change_policy(body: policy.PolicyChange, request: Request,
                      x_asof_editor_token: Annotated[str | None, Header()] = None):
        return as_editor(body, request, x_asof_editor_token, preview=False)

    @app.post("/api/policy/preview")
    def preview_policy(body: policy.PolicyChange, request: Request,
                       x_asof_editor_token: Annotated[str | None, Header()] = None):
        """The impact of a change, computed by Db2 inside a transaction that is rolled back: nothing is saved."""
        return as_editor(body, request, x_asof_editor_token, preview=True)

    # ---------- policy intake (asof/intake.py) ----------
    DRAFT_ERRORS = {"75043": 404, "75044": 403, "75045": 422, "75046": 422, "75047": 409, "75048": 409, "75042": 409,
                    "75011": 422, "75012": 409, "75013": 422, "75040": 422}

    def draft_error(exc: db.DatabaseError) -> HTTPException | None:
        status = DRAFT_ERRORS.get(exc.sqlstate or "")
        return HTTPException(status, str(exc).split(": ", 1)[-1]) if status else None

    @app.post("/api/policy/drafts")
    async def upload_policy_document(request: Request, doc_id: DocId,
                                     name: Annotated[str | None, Query(max_length=200)] = None,
                                     x_asof_editor_token: Annotated[str | None, Header()] = None):
        """A policy PDF becomes a draft of checked clause versions. Nothing is in force until an editor approves.
        The body is the PDF itself (Content-Type: application/pdf), at most 2 MB. The public demo takes the sample only."""
        if not demo:
            require_editor(request, x_asof_editor_token)
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf":
            raise HTTPException(415, "send the PDF itself as the request body, with Content-Type: application/pdf")
        data = await request.body()
        if demo and data != intake.SAMPLE_PDF.read_bytes():
            demo_off("uploading your own policy document (Use the sample works)")
        try:
            source = await run_in_threadpool(intake.read_pdf, data, name)
        except intake.IntakeError as exc:
            raise HTTPException(422, str(exc)) from None
        llm = intake_llm()

        def work() -> dict[str, Any]:
            conn = app_conn()
            try:
                proposals, discarded, model = intake.propose(llm, source, doc_id, conn, schema)
            finally:
                conn.close()
            editor = db.connect(settings, "editor")
            try:
                draft_id = intake.store_draft(editor, source, doc_id, model, proposals, requested_by(request), schema)
            finally:
                editor.close()
            reader = app_conn()  # the editor holds no SELECT on the timeline view; the runtime user reads drafts
            try:
                return {"draft": intake.get_draft(reader, draft_id, schema), "discarded": [d.__dict__ for d in discarded]}
            finally:
                reader.close()

        try:
            return await run_in_threadpool(work)
        except intake.IntakeError as exc:
            raise HTTPException(422, str(exc)) from None
        except db.DatabaseError as exc:
            raise draft_error(exc) or exc from None

    @app.get("/api/policy/drafts")
    def policy_drafts():
        conn = app_conn()
        try:
            return intake.list_drafts(conn, schema)
        finally:
            conn.close()

    @app.get("/api/policy/drafts/{draft_id}")
    def policy_draft(draft_id: Annotated[int, Path(ge=1, le=10**12)]):
        conn = app_conn()
        try:
            draft = intake.get_draft(conn, draft_id, schema)
        finally:
            conn.close()
        if draft is None:
            raise HTTPException(404, "no such draft")
        return draft

    @app.get("/api/policy/drafts/{draft_id}/source")
    def policy_draft_source(draft_id: Annotated[int, Path(ge=1, le=10**12)]):
        """The uploaded file, exactly as Db2 holds it (its SHA-256 is on the draft)."""
        conn = app_conn()
        try:
            found = intake.source_pdf(conn, draft_id, schema)
        finally:
            conn.close()
        if found is None:
            raise HTTPException(404, "no such draft")
        name, data = found
        return Response(data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{intake.safe_name(name)}"'})

    @app.get("/api/policy/intake/sample")
    def policy_intake_sample():
        """The built-in sample: a fictional revision of the Aurelia Air policy (replay mode has its extraction)."""
        return Response(intake.SAMPLE_PDF.read_bytes(), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{intake.SAMPLE_PDF.name}"'})

    @app.post("/api/policy/drafts/{draft_id}/decision")
    def decide_policy_draft(draft_id: Annotated[int, Path(ge=1, le=10**12)], body: DraftDecision, request: Request,
                            x_asof_editor_token: Annotated[str | None, Header()] = None):
        """Approve (with the items to accept), reject, or preview: preview applies the draft and runs CHANGE_IMPACT
        in one transaction, then rolls it back."""
        if not body.preview:
            demo_off("approving or rejecting a policy draft (Preview impact works: Db2 rolls it back)")
        if not (demo and body.preview):
            require_editor(request, x_asof_editor_token)
        if body.preview and not body.approve:
            raise HTTPException(422, "only an approval can be previewed")
        editor = db.connect(settings, "editor")
        try:
            try:
                out = intake.decide(editor, draft_id, body.approve, body.accept, get_embeddings(settings.embedding_model),
                                    requested_by(request), body.preview, schema)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            except db.DatabaseError as exc:
                raise draft_error(exc) or exc from None
        finally:
            editor.close()
        reader = app_conn()
        try:
            out["draft"] = intake.get_draft(reader, draft_id, schema)
        finally:
            reader.close()
        return out

    # ---------- the specialist inbox (asof/review.py) ----------
    def review_refused(exc: review.ReviewError, as_of: Any, reply: str = "") -> JSONResponse:
        body: dict[str, Any] = {"error": str(exc)}
        if exc.check is not None:
            body["check"] = review.check_out(exc.check, as_of, reply)
        return JSONResponse(jsonable_encoder(body), status_code=exc.status)

    def held_date(ledger_id: int) -> Any:
        conn = app_conn()
        try:
            entry = ledger.get_entry(conn, ledger_id, schema)
        finally:
            conn.close()
        return entry["as_of_date"] if entry else None

    @app.get("/api/reviews")
    def review_queue(limit: Annotated[int, Query(ge=1, le=100)] = 50):
        """Held decisions waiting for a specialist, oldest first, and the latest answered."""
        conn = app_conn()
        try:
            return review.queue(conn, schema, limit)
        finally:
            conn.close()

    @app.get("/api/reviews/{ledger_id}")
    def review_detail(ledger_id: Annotated[int, Path(ge=1, le=10**12)]):
        try:
            return review.detail(app_conn, get_embeddings(settings.embedding_model), ledger_id, schema)
        except review.ReviewError as exc:
            raise HTTPException(exc.status, str(exc)) from None

    @app.post("/api/reviews/{ledger_id}/check")
    def review_check(ledger_id: Annotated[int, Path(ge=1, le=10**12)], body: ReplyIn, request: Request):
        """The full check of a draft reply on the customer's date. Nothing is recorded or sent."""
        if not demo:  # nothing is recorded, so the public demo allows it
            require_local_reviewer(request)
        g, _ = components()
        try:
            result = review.check_reply(g, ledger_id, body.reply, body.doc_id, requested_by(request))
        except review.ReviewError as exc:
            return review_refused(exc, held_date(ledger_id), body.reply)
        return review.check_out(result, held_date(ledger_id), body.reply)

    @app.post("/api/reviews/{ledger_id}/resolve")
    def review_resolve(ledger_id: Annotated[int, Path(ge=1, le=10**12)], body: ReplyIn, request: Request):
        """Check the reply and send it: appended to the ledger as a REVIEWED decision through RESOLVE_ESCALATION."""
        demo_off("sending a specialist's reply (Check reply works)")
        require_local_reviewer(request)
        g, _ = components()
        try:
            done = review.resolve(g, ledger_id, body.reply, body.note, body.doc_id, requested_by(request),
                                  connect=lambda: db.connect(settings, "review"))
        except review.ReviewError as exc:
            return review_refused(exc, held_date(ledger_id), body.reply)
        return jsonable_encoder({"escalated_ledger_id": ledger_id, "ledger_id": done.ledger_id, "row_hash": done.row_hash,
                                 "outcome": done.outcome, "final_answer": done.final_answer,
                                 "check": review.check_out(done.check, held_date(ledger_id), body.reply)})

    # ---------- correction notices for stale answers (asof/notices.py) ----------
    @app.get("/api/notices")
    def notice_list(clause_id: Annotated[str | None, Query(pattern=r"^[A-Z]{3}-[0-9]{3}$")] = None,
                    status: Literal["PENDING", "SENT", "REJECTED"] | None = None):
        conn = app_conn()
        try:
            return notices.list_notices(conn, clause_id, status, schema)
        finally:
            conn.close()

    @app.post("/api/notices/draft")
    def notice_draft(body: NoticeDraftIn, request: Request):
        """Run the change-impact agent: a checked correction notice for every answer now stale for its date."""
        demo_off("drafting correction notices")
        require_local_reviewer(request)
        drafted = impactagent.draft_notices(components()[0], body.clause_id, requested_by(request))
        conn = app_conn()
        try:
            return jsonable_encoder({"drafted": drafted, "notices": notices.list_notices(conn, body.clause_id, None, schema)})
        finally:
            conn.close()

    @app.post("/api/notices/{notice_id}/decision")
    def notice_decision(notice_id: Annotated[int, Path(ge=1, le=10**12)], body: NoticeDecision, request: Request):
        """A specialist approves a notice for sending (it is marked SENT; AsOf sends nothing itself) or rejects it."""
        demo_off("approving or rejecting a correction notice")
        require_local_reviewer(request)
        conn = db.connect(settings, "review")  # the reviewer account: the runtime user cannot decide notices
        try:
            notices.decide(conn, notice_id, body.approve, requested_by(request), schema)
        except db.DatabaseError as exc:
            status = notices.REFUSALS.get(exc.sqlstate or "")
            if status is None:
                raise
            raise HTTPException(status, db.refusal_text(exc, "Db2 refused the decision.")) from None
        finally:
            conn.close()
        return {"notice_id": notice_id, "status": "SENT" if body.approve else "REJECTED"}

    # ---------- backtests: a CSV of past answers, checked in batch (asof/backtest.py) ----------
    # One run at a time in this process. A run goes on in a background thread after the upload is answered (202); the
    # page polls GET /api/backtests/{id}. backtest_guard is the hook a spend cap on live checks plugs into: called
    # before each row, it raises backtest.Stop to end the run there. backtest_launch replaces the thread in tests.
    backtest_lock = threading.Lock()
    sample_sha256 = hashlib.sha256(backtest.SAMPLE_CSV.read_bytes()).hexdigest()

    def in_a_thread(work: Callable[[], None]) -> None:
        threading.Thread(target=work, name="asof-backtest", daemon=True).start()

    launch = backtest_launch or in_a_thread

    @app.get("/api/backtests/sample")
    def backtest_sample():
        """The built-in sample: 20 fictional past answers over both policies, which replay mode can check."""
        return Response(backtest.SAMPLE_CSV.read_bytes(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{backtest.SAMPLE_NAME}"'})

    @app.post("/api/backtests")
    async def start_backtest(request: Request, doc_id: DocId | Literal["auto"] = "auto",
                             name: Annotated[str | None, Query(max_length=200)] = None):
        """Check every row of a CSV of past answers (question, draft, customer_date, channel, optional doc_id) through
        the normal check, on channel backtest. The body is the CSV itself (Content-Type: text/csv), at most 2 MB and
        ASOF_BACKTEST_MAX_ROWS rows. Answers 202 with the run's ID; the run goes on in the background."""
        demo_off("uploading and running a backtest (the sample run shown here is read-only)")
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "text/csv":
            raise HTTPException(415, "send the CSV itself as the request body, with Content-Type: text/csv")
        data = await request.body()
        try:
            upload = await run_in_threadpool(backtest.parse_csv, data, name, settings.asof_backtest_max_rows)
        except backtest.CsvError as exc:
            return JSONResponse({"error": f"The file cannot be run: {exc}", "errors": exc.errors,
                                 "total_errors": exc.total}, status_code=422)
        g, _ = components()
        routed = any((r.doc_id or doc_id) == "auto" for r in upload.rows)
        rtr = await run_in_threadpool(doc_router) if routed else None
        if not backtest_lock.acquire(blocking=False):
            raise HTTPException(409, "a backtest is already running on this server: wait for it to finish")
        try:
            bt = backtest.Backtest(g, app_conn, schema, router=rtr, before_check=backtest_guard)
            who, deadline_s = requested_by(request), settings.asof_backtest_deadline_s
            run_id = await run_in_threadpool(bt.start, upload, doc_id, deadline_s, who, upload.sha256 == sample_sha256)
        except BaseException:
            backtest_lock.release()
            raise

        def work() -> None:
            try:
                bt.run(run_id, upload, doc_id, deadline_s, who)
            finally:
                backtest_lock.release()

        launch(work)
        return JSONResponse({"run_id": run_id, "rows": len(upload.rows), "state": "RUNNING"}, status_code=202)

    @app.get("/api/backtests")
    def backtest_runs(limit: Annotated[int, Query(ge=1, le=100)] = 20):
        """The latest runs with their outcome counts, and the latest finished run of the built-in sample."""
        conn = app_conn()
        try:
            return jsonable_encoder({"runs": backtest.list_runs(conn, schema, limit),
                                     "sample_run_id": backtest.latest_sample(conn, schema),
                                     "running_here": backtest_lock.locked()})
        finally:
            conn.close()

    @app.get("/api/backtests/{run_id}")
    def backtest_report(run_id: Annotated[int, Path(ge=1, le=10**12)]):
        """The exposure report of one run: wrong answers by clause version, the money at stake, the costliest examples."""
        conn = app_conn()
        try:
            out = backtest.report(conn, run_id, schema)
        finally:
            conn.close()
        if out is None:
            raise HTTPException(404, "no such backtest run")
        return jsonable_encoder(out)

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/ui/")

    @app.get("/chat", include_in_schema=False)
    def chat():
        return RedirectResponse("/ui/chat.html")

    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    return app


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def bind_refusal(host: str, settings: Settings) -> str | None:
    """Why the server must not listen on `host`, or None. Local mode trusts its clients (it answers on localhost
    only), so listening beyond localhost needs authentication first: per-user tokens or the shared API token."""
    if host in LOOPBACK_HOSTS or settings.asof_auth == "users" or settings.asof_api_token:
        return None
    return (f"refusing to listen on {host}: local mode has no authentication. Set ASOF_AUTH=users (per-user tokens, "
            "python -m asof.users) or ASOF_API_TOKEN in .env first, or keep the default 127.0.0.1.")


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(prog="python -m asof.api")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    refusal = bind_refusal(args.host, get_settings())
    if refusal:
        raise SystemExit(refusal)
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
