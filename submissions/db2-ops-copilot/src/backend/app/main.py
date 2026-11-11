"""FastAPI application entry point.

Run (from ``backend/``):

    python -m uvicorn app.main:app --reload --port 8000

Startup behaviour:
- Logging configured first (centralized, request-id aware).
- Adapter registry built from settings (mock by default — no services needed).
- Shutdown closes all adapters gracefully.

CORS: explicit origin allow-list (no wildcard) driven by ``CORS_ORIGINS``.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.registry import AdapterRegistry
from app.agent.approvals import ApprovalStore
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import error_payload, register_exception_handlers
from app.core.logging import configure_logging, set_request_id

logger = logging.getLogger(__name__)

# backend/app/main.py -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def _asgi_middleware_factory(app):
    """ASGI factory wrapping the request-context logic (Starlette compatible)."""

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        request_id = "-"
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                request_id = value.decode("latin-1")[:64]
                break
        if request_id == "-":
            request_id = uuid.uuid4().hex[:16]

        scope.setdefault("state", {})["request_id"] = request_id
        set_request_id(request_id)
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)",
                scope.get("method", "?"),
                scope.get("path", "?"),
                status_holder["status"],
                duration_ms,
            )

    return middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)
    registry = AdapterRegistry.from_settings(settings)
    app.state.registry = registry
    app.state.started_at = time.time()
    logger.info(
        "Db2 Ops Copilot %s starting (env=%s, adapter_mode=%s)",
        settings.app_version,
        settings.environment,
        settings.adapter_mode,
    )
    try:
        yield
    finally:
        registry.close_all()
        logger.info("Db2 Ops Copilot shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Portable Db2 Ops Copilot — hybrid RAG + guardrailed text-to-SQL "
            "over IBM Db2. M1 foundation: adapters + mocks; real integrations in M2."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.approval_store = ApprovalStore()

    # Order matters: CORS first, then request context, then handlers/routes.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.add_middleware(_asgi_middleware_factory)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "api": settings.api_v1_prefix,
            "docs": "/docs",
            "frontend": "build with `npm run build` in frontend/ (served at / when present)",
        }

    @app.get("/api/{unmatched:path}", include_in_schema=False)
    async def api_not_found(unmatched: str) -> JSONResponse:
        """Keep API 404s in the JSON envelope even when static files are mounted."""
        from app.core.errors import NotFoundError

        raise NotFoundError(f"Unknown API route: /api/{unmatched}")

    # Serve the built frontend (if present) AFTER all API routes so /api/*
    # always wins. Absent dist/ is fine: the Vite dev server is the M1 path.
    if settings.serve_frontend and FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
        logger.info("Serving built frontend from %s", FRONTEND_DIST)

    return app


app = create_app()
