"""Error handling middleware and custom exception classes."""

import logging
from typing import Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("splitsync")


class AppError(Exception):
    """Custom application exception for controlled domain and HTTP errors."""

    def __init__(
        self,
        status_code_or_message: int | str = 400,
        message_or_status_code: int | str = "Application error",
        detail: Optional[Any] = None,
    ) -> None:
        if isinstance(status_code_or_message, int):
            self.status_code = status_code_or_message
            self.message = str(message_or_status_code)
        else:
            self.message = str(status_code_or_message)
            self.status_code = (
                message_or_status_code
                if isinstance(message_or_status_code, int)
                else 400
            )
        self.detail = detail
        super().__init__(self.message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError exceptions with structured JSON error response."""
    content: dict[str, Any] = {"message": exc.message}
    if exc.detail is not None:
        content["detail"] = exc.detail

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": content},
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions with 422 Unprocessable Entity status."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": str(exc),
                "detail": None,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions without exposing internal stack traces."""
    logger.error(
        "Unhandled exception during %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
            }
        },
    )
