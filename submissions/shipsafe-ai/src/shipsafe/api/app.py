"""ShipSafe AI HTTP API and web UI host (FastAPI).

Security model
- Every /api route except /api/health and /api/ready requires a bearer token.
- Roles: viewer (read), operator (+ run scans), admin (+ tokens, audit, reindex).
- Scan targets must resolve inside SHIPSAFE_ALLOWED_ROOTS.
- Security headers + strict CSP on every response; CORS is off unless configured.
- Every privileged action and every denied request is written to Db2 AUDIT_LOG.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..config import PACKAGE_ROOT, ShipSafeConfig
from ..db2.pool import ConnectionPool, Db2Unavailable
from ..reports.generator import sarif_document
from ..security import Principal, ROLES, TargetNotAllowed, hash_token, issue_token, list_workspaces, resolve_target, role_allows
from .jobs import STEPS, JobManager, RateLimiter
from .markdown import markdown_from_rows

log = logging.getLogger("shipsafe.api")
WEB_DIST = PACKAGE_ROOT / "web" / "dist"

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'; object-src 'none'")


class ScanRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=512)
    profile: str = Field("pre-pr", pattern="^(quick|pre-pr|deep)$")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(3, ge=1, le=10)
    category: Optional[str] = Field(None, max_length=64)


class TokenRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Za-z0-9 ._\-]+$")
    role: str = Field("viewer", pattern="^(viewer|operator|admin)$")


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", "replace")
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if obj is not None and not isinstance(obj, (str, int, float, bool)):
        return str(obj)
    return obj


def create_app(config: Optional[ShipSafeConfig] = None, pool: Optional[ConnectionPool] = None) -> FastAPI:
    config = config or ShipSafeConfig.load()
    pool = pool or ConnectionPool(config.db2, backend=config.backend, size=config.pool_size)
    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        yield
        app_.state.jobs.shutdown()
        app_.state.pool.close()

    app = FastAPI(title="ShipSafe AI", version=__version__, docs_url="/api/docs", redoc_url=None,
                  openapi_url="/api/openapi.json", lifespan=lifespan)
    limiter = RateLimiter(config.scan_rate_per_minute)

    def kb_factory(repo):
        if not repo.is_db2:
            return None
        from ..knowledge import PolicyKnowledgeBase

        return PolicyKnowledgeBase(repo, config.embedding_provider, config.embedding_dimension)

    def audit(actor: str, action: str, outcome: str, **kw) -> None:
        try:
            with pool.repository() as repo:
                repo.audit(actor, action, outcome, **kw)
        except Exception as exc:  # never break a request because auditing failed
            log.error("audit unavailable: %s", exc)

    jobs = JobManager(config, pool, kb_factory, audit)
    app.state.config, app.state.pool, app.state.jobs = config, pool, jobs

    if config.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins, allow_methods=["GET", "POST", "DELETE"],
                           allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id", uuid.uuid4().hex[:16])[:64]
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Db2Unavailable as exc:
            response = JSONResponse({"error": "db2_unavailable", "detail": str(exc)[:300]}, status_code=503)
        dur = round((time.perf_counter() - t0) * 1000, 1)
        response.headers.update({
            "X-Request-ID": rid, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy": CSP,
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        })
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            log.info("%s %s -> %s", request.method, request.url.path, response.status_code,
                     extra={"request_id": rid, "method": request.method, "path": request.url.path,
                            "status": response.status_code, "duration_ms": dur})
        return response

    @app.exception_handler(Db2Unavailable)
    async def db2_down(_: Request, exc: Db2Unavailable):
        return JSONResponse({"error": "db2_unavailable", "detail": str(exc)[:300]}, status_code=503)

    # ------------------------------------------------------------------ auth
    def principal(request: Request) -> Principal:
        if not config.auth_enabled:
            return Principal("local", "local-dev", "admin")
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        ip = request.client.host if request.client else None
        if not token:
            raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
        with pool.repository() as repo:
            row = repo.find_token(hash_token(token))
            if not row or int(row["REVOKED"]):
                repo.audit("anonymous", "auth.denied", "denied", target=request.url.path, client_ip=ip,
                           detail="unknown or revoked token")
                raise HTTPException(401, "Invalid or revoked token", headers={"WWW-Authenticate": "Bearer"})
            repo.touch_token(row["TOKEN_ID"])
        return Principal(row["TOKEN_ID"], row["NAME"], row["ROLE"])

    def require(role: str):
        def dep(request: Request, p: Principal = Depends(principal)) -> Principal:
            if not role_allows(p.role, role):
                audit(p.name, "auth.forbidden", "denied", role=p.role, target=request.url.path,
                      client_ip=request.client.host if request.client else None, detail=f"requires {role}")
                raise HTTPException(403, f"This action requires the '{role}' role")
            return p
        return dep

    viewer, operator, admin = require("viewer"), require("operator"), require("admin")

    # --------------------------------------------------------------- health
    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/ready")
    def ready():
        try:
            with pool.repository() as repo:
                info = repo.check_connection()
                kb = kb_factory(repo)
                info["policy_chunks"] = kb.chunk_count() if kb else 0
            return {"status": "ready", "db2": _jsonable(info)}
        except Exception as exc:
            return JSONResponse({"status": "degraded", "db2": {"connected": False, "error": str(exc)[:300]}},
                                status_code=503)

    @app.get("/api/me")
    def me(p: Principal = Depends(viewer)):
        return {"name": p.name, "role": p.role, "token_id": p.token_id, "auth_enabled": config.auth_enabled}

    # ------------------------------------------------------------- dashboard
    @app.get("/api/overview")
    def overview(p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            return _jsonable({
                "stats": repo.overview_stats(),
                "posture": repo.project_posture(),
                "trend": list(reversed(repo.get_assessment_history(limit=40))),
                "breakdown": repo.severity_breakdown(),
                "recent": repo.list_assessments(limit=8),
            })

    @app.get("/api/assessments")
    def assessments(limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0),
                    project_id: Optional[str] = Query(None, max_length=96), p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            return _jsonable({"items": repo.list_assessments(limit, offset, project_id)})

    @app.get("/api/assessments/{assessment_id}")
    def assessment(assessment_id: str, p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            asm = repo.get_assessment(assessment_id)
            if not asm:
                raise HTTPException(404, "Assessment not found")
            return _jsonable({
                "assessment": asm,
                "findings": repo.get_findings(assessment_id),
                "tool_runs": repo.get_tool_runs(assessment_id),
                "dependencies": repo.get_dependencies(asm["PROJECT_ID"]),
                "history": list(reversed(repo.get_assessment_history(limit=20, project_id=asm["PROJECT_ID"]))),
            })

    @app.get("/api/assessments/{assessment_id}/report")
    def report(assessment_id: str, format: str = Query("markdown", pattern="^(markdown|json|sarif)$"),
               p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            asm = repo.get_assessment(assessment_id)
            if not asm:
                raise HTTPException(404, "Assessment not found")
            findings, runs = repo.get_findings(assessment_id), repo.get_tool_runs(assessment_id)
        name = f"shipsafe-{assessment_id}"
        if format == "sarif":
            return JSONResponse(sarif_document(assessment_id, _jsonable(findings)),
                                headers={"Content-Disposition": f'attachment; filename="{name}.sarif"'})
        if format == "json":
            return JSONResponse(_jsonable({"assessment": asm, "findings": findings, "tool_runs": runs}),
                                headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
        return PlainTextResponse(markdown_from_rows(_jsonable(asm), _jsonable(findings), _jsonable(runs)),
                                 media_type="text/markdown",
                                 headers={"Content-Disposition": f'attachment; filename="{name}.md"'})

    @app.get("/api/compare")
    def compare(previous: str = Query(..., max_length=64), current: str = Query(..., max_length=64),
                p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            for aid in (previous, current):
                if not repo.get_assessment(aid):
                    raise HTTPException(404, f"Assessment {aid} not found")
            return _jsonable(repo.compare_assessments(previous, current))

    # ----------------------------------------------------------------- scans
    @app.get("/api/workspaces")
    def workspaces(p: Principal = Depends(operator)):
        return {"roots": config.allowed_roots, "items": list_workspaces(config.allowed_roots)}

    @app.post("/api/scans", status_code=202)
    def start_scan(body: ScanRequest, request: Request, p: Principal = Depends(operator)):
        ip = request.client.host if request.client else None
        try:
            target = resolve_target(body.target, config.allowed_roots)
        except TargetNotAllowed as exc:
            audit(p.name, "scan.rejected", "denied", role=p.role, target=body.target, client_ip=ip, detail=str(exc))
            raise HTTPException(400, str(exc))
        if not limiter.allow(p.token_id):
            raise HTTPException(429, "Scan rate limit reached; try again in a minute")
        audit(p.name, "scan.requested", "success", role=p.role, target=str(target), client_ip=ip,
              detail=f"profile={body.profile}")
        return {**jobs.submit(str(target), body.profile, p.name), "steps_total": STEPS}

    @app.get("/api/scans")
    def list_scans(p: Principal = Depends(viewer)):
        return {"items": jobs.recent()}

    @app.get("/api/scans/{job_id}")
    def scan_status(job_id: str, p: Principal = Depends(viewer)):
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Scan job not found")
        return _jsonable({**job, "steps_total": STEPS})

    # -------------------------------------------------------------- policies
    @app.get("/api/policies")
    def policies(p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            kb = kb_factory(repo)
            return _jsonable({"items": repo.list_knowledge_docs(), "chunks": kb.chunk_count() if kb else 0})

    @app.post("/api/policies/search")
    def search(body: SearchRequest, p: Principal = Depends(viewer)):
        with pool.repository() as repo:
            kb = kb_factory(repo)
            if kb is None:
                raise HTTPException(503, "Policy search requires the IBM Db2 backend")
            t0 = time.perf_counter()
            hits = kb.retrieve(body.query, top_k=body.top_k, category=body.category)
            return {"query": body.query, "results": hits, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}

    @app.post("/api/policies/reindex")
    def reindex(request: Request, p: Principal = Depends(admin)):
        with pool.repository() as repo:
            kb = kb_factory(repo)
            if kb is None:
                raise HTTPException(503, "Policy search requires the IBM Db2 backend")
            stats = kb.ingest_directory(config.policies_dir)
            repo.audit(p.name, "policies.reindexed", "success", role=p.role, detail=str(stats)[:500],
                       client_ip=request.client.host if request.client else None)
            return {"documents": stats, "chunks": kb.chunk_count()}

    # ----------------------------------------------------------- admin area
    @app.get("/api/tokens")
    def tokens(p: Principal = Depends(admin)):
        with pool.repository() as repo:
            return _jsonable({"items": repo.list_tokens(), "roles": ROLES})

    @app.post("/api/tokens", status_code=201)
    def create_token(body: TokenRequest, request: Request, p: Principal = Depends(admin)):
        token_id, token, digest = issue_token()
        with pool.repository() as repo:
            repo.create_token(token_id, body.name, body.role, digest)
            repo.audit(p.name, "token.created", "success", role=p.role, target=token_id,
                       detail=f"name={body.name} role={body.role}",
                       client_ip=request.client.host if request.client else None)
        return {"token_id": token_id, "name": body.name, "role": body.role, "token": token,
                "notice": "Copy this token now. It is stored only as a SHA-256 hash and cannot be shown again."}

    @app.delete("/api/tokens/{token_id}")
    def revoke_token(token_id: str, request: Request, p: Principal = Depends(admin)):
        if token_id == p.token_id:
            raise HTTPException(400, "You cannot revoke the token you are signed in with")
        with pool.repository() as repo:
            if not repo.revoke_token(token_id):
                raise HTTPException(404, "Token not found")
            repo.audit(p.name, "token.revoked", "success", role=p.role, target=token_id,
                       client_ip=request.client.host if request.client else None)
        return {"revoked": token_id}

    @app.get("/api/audit")
    def audit_log(limit: int = Query(100, ge=1, le=500), action: Optional[str] = Query(None, max_length=64),
                  p: Principal = Depends(admin)):
        with pool.repository() as repo:
            return _jsonable({"items": repo.list_audit(limit, action)})

    # ------------------------------------------------------------- web UI
    if WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "Not found")
            candidate = (WEB_DIST / path).resolve()
            if path and candidate.is_file() and WEB_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def no_ui():
            return PlainTextResponse("ShipSafe API is running. Build the web UI with: cd web && npm ci && npm run build")

    return app
