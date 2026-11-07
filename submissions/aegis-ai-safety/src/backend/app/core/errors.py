"""Typed application errors that map to safe HTTP responses."""

from __future__ import annotations


class AegisError(Exception):
    """Base class for expected, user-facing errors."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ConfigurationError(AegisError):
    status_code = 500
    code = "configuration_error"


class DatabaseUnavailableError(AegisError):
    status_code = 503
    code = "database_unavailable"


class DatabaseOperationError(AegisError):
    status_code = 500
    code = "database_operation_failed"


class NotFoundError(AegisError):
    status_code = 404
    code = "not_found"


class UploadValidationError(AegisError):
    status_code = 400
    code = "invalid_upload"


class DocumentProcessingError(AegisError):
    status_code = 422
    code = "document_processing_failed"


class PipelineError(AegisError):
    status_code = 502
    code = "verification_pipeline_failed"


class LLMUnavailableError(AegisError):
    status_code = 503
    code = "llm_unavailable"
