"""AWS Evidence Layer Exceptions.

Defines domain-specific exceptions for AWS evidence collection to isolate
boto3-specific error handling from the verification engine.
"""

from typing import Any, Optional


class AWSEvidenceError(Exception):
    """Base exception for all AWS Evidence collection errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ResourceNotFoundError(AWSEvidenceError):
    """Raised when an AWS resource does not exist in the target account/region."""

    def __init__(
        self,
        resource_id: str,
        resource_type: str,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.resource_id = resource_id
        self.resource_type = resource_type
        msg = message or f"{resource_type} '{resource_id}' was not found in AWS."
        super().__init__(msg, details=details)


class AWSAuthorizationError(AWSEvidenceError):
    """Raised when AWS API returns AccessDenied, AuthFailure, or credential errors."""
    pass


class AWSServiceError(AWSEvidenceError):
    """Raised when AWS API encounters service errors, throttling, or network failures."""
    pass


class UnsupportedFieldError(AWSEvidenceError):
    """Raised when a requested observation field is not supported for a resource type."""
    pass


class UnsupportedResourceTypeError(AWSEvidenceError):
    """Raised when a requested resource type has no registered collector."""
    pass
