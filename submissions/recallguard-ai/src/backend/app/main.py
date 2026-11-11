"""RecallGuard AI — FastAPI application entrypoint."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router
from app.core.config import get_settings
from app.database import DatabaseError, IntegrityViolation, init_database
from app.services.common import InvalidState, NotFound
from app.services.evidence import UploadRejected

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("recallguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_database()
    except DatabaseError as exc:  # keep serving /health so the failure is visible
        log.error("Starting in DEGRADED mode — database unavailable: %s", exc)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="RecallGuard AI API",
        version="1.0.0",
        description="IBM Db2-powered contamination investigation and targeted recall platform. "
                    "Supply-chain genealogy is computed by Db2 recursive SQL; AI agents (CrewAI) explain and verify.",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-User-Id", "X-User-Role"])

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        if request.url.path.startswith(s.api_prefix):
            log.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, resp.status_code, (time.perf_counter() - t0) * 1000)
        resp.headers["X-Data-Engine"] = "IBM-Db2" if s.db_mode == "db2" else "DEV-MODE-NOT-DB2"
        return resp

    def err(code: int, kind: str, msg: str) -> JSONResponse:
        return JSONResponse(status_code=code, content={"error": kind, "detail": msg})

    app.add_exception_handler(NotFound, lambda r, e: err(404, "not_found", str(e)))
    app.add_exception_handler(InvalidState, lambda r, e: err(409, "invalid_state", str(e)))
    app.add_exception_handler(UploadRejected, lambda r, e: err(422, "upload_rejected", str(e)))
    app.add_exception_handler(IntegrityViolation, lambda r, e: err(409, "integrity_violation", str(e)[:300]))
    app.add_exception_handler(DatabaseError, lambda r, e: err(503, "database_unavailable", str(e)[:300]))

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": "validation_error", "detail": exc.errors()})

    app.include_router(router, prefix=s.api_prefix)

    @app.get("/", include_in_schema=False)
    def root():
        return {"app": s.app_name, "docs": "/docs", "health": f"{s.api_prefix}/health"}

    return app


app = create_app()
