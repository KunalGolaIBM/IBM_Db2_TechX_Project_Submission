"""Application error hierarchy and consistent JSON error handling.

Every error response uses the same envelope:

    {"error": {"code": "...", "message": "...", "detail": ..., "request_id": "..."}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all domain errors surfaced by the API."""

    code: str = "APP_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.detail = detail


class AdapterUnavailableError(AppError):
    """A real adapter cannot reach its backing service (Db2/Ollama/...)."""

    code = "ADAPTER_UNAVAILABLE"
    status_code = 503


class ConfigurationError(AppError):
    code = "CONFIGURATION_ERROR"
    status_code = 500


class PromptInjectionBlockedError(AppError):
    code = "PROMPT_INJECTION_BLOCKED"
    status_code = 400


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404


class SqlRejectedError(AppError):
    """The SQL validation gate rejected a statement before execution.

    Raised by ``POST /api/v1/sql/execute`` — the rejection is persisted to
    APP.QUERY_EXECUTIONS and APP_AUDIT before raising.
    """

    code = "SQL_REJECTED"
    status_code = 422


class UpstreamTimeoutError(AppError):
    code = "UPSTREAM_TIMEOUT"
    status_code = 504


# -- Db2 error taxonomy (SQLSTATE -> HTTP), see Db2DatabaseAdapter ----------
class DbPermissionError(AppError):
    """The Db2 account lacks a privilege (SQLSTATE 42501 / class 425)."""

    code = "DB_PERMISSION_DENIED"
    status_code = 403


class DbObjectNotFoundError(AppError):
    """A referenced table/column/function does not exist (SQLSTATE class 427)."""

    code = "DB_OBJECT_NOT_FOUND"
    status_code = 404


class DbSqlError(AppError):
    """The statement is syntactically/semantically invalid (class 426/428)."""

    code = "DB_SQL_ERROR"
    status_code = 422


class DbError(AppError):
    """Unclassified database failure (bad gateway)."""

    code = "DB_ERROR"
    status_code = 502


def error_payload(
    code: str, message: str, request_id: str, detail: Any = None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if detail is not None:
        body["detail"] = detail
    return {"error": body}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        level = logging.WARNING if exc.status_code < 500 else logging.ERROR
        logger.log(
            level,
            "app error %s (%s): %s",
            exc.code,
            exc.status_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, _request_id(request), exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "VALIDATION_ERROR",
                "Request validation failed",
                _request_id(request),
                detail=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
        }.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                code, str(exc.detail), _request_id(request)
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "INTERNAL_ERROR",
                "An unexpected internal error occurred",
                _request_id(request),
            ),
        )
