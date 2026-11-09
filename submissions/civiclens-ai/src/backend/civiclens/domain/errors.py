"""Domain errors carrying a stable machine-readable code and an HTTP status."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details

    def to_detail(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


class NotFoundError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(DomainError):
    status_code = 409
    code = "CONFLICT"


class ForbiddenError(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class InvalidEvidenceError(DomainError):
    status_code = 422
    code = "INVALID_EVIDENCE"


class AgentError(DomainError):
    """The investigation agent could not produce a trustworthy result."""

    status_code = 502
    code = "AGENT_ERROR"


class AgentTimeoutError(AgentError):
    status_code = 504
    code = "AGENT_TIMEOUT"


class AgentStepLimitError(AgentError):
    status_code = 422
    code = "AGENT_STEP_LIMIT"


class LlmNotConfiguredError(DomainError):
    status_code = 409
    code = "LLM_NOT_CONFIGURED"
