"""API Error Domain Models."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Structured client-facing error description."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of error")
    details: Optional[Any] = Field(default=None, description="Optional diagnostic context")


class ErrorResponse(BaseModel):
    """Standardized API error envelope."""
    error: ErrorDetail


class APIError(Exception):
    """Application-level HTTP exception with standardized code and message."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)
