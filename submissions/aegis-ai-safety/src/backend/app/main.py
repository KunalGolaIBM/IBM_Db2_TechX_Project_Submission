"""AEGIS API entry point."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import documents, evaluation, health, verifications
from app.core.config import get_settings
from app.core.errors import AegisError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("aegis")

VERSION = "0.2.0"


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Bound the total wall-clock time of an API request."""

    def __init__(self, app, timeout_seconds: float) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "request_timeout",
                        "message": "The request exceeded the configured time limit.",
                    }
                },
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info(
        "AEGIS API starting (env=%s, db=%s@%s:%s, llm=%s/%s)",
        settings.aegis_env,
        settings.db2_database,
        settings.db2_host,
        settings.db2_port,
        settings.llm_provider,
        settings.llm_model,
    )
    yield
    logger.info("AEGIS API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AEGIS API",
        version=VERSION,
        description=(
            "Independent AI research verification. Extracts atomic claims, retrieves "
            "evidence from IBM Db2, and records evidence-linked LangChain assessments."
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    application.add_middleware(RequestTimeoutMiddleware, timeout_seconds=settings.aegis_request_timeout_seconds)

    @application.exception_handler(AegisError)
    async def aegis_error_handler(_: Request, exc: AegisError):
        body = {"error": {"code": exc.code, "message": exc.message}}
        if exc.detail:
            body["error"]["detail"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=body)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        issues = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            issues.append(f"{location}: {error.get('msg', 'invalid value')}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request payload is invalid.",
                    "detail": "; ".join(issues)[:1000],
                }
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception):
        logger.exception("Unhandled API error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected internal error occurred.",
                }
            },
        )

    application.include_router(health.router)
    application.include_router(documents.router)
    application.include_router(verifications.router)
    application.include_router(evaluation.router)
    return application


app = create_app()
