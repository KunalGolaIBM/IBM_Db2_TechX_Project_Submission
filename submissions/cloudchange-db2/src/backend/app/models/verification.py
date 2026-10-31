"""Verification Domain Models."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Outcomes of comparing a prediction with empirical AWS evidence."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    NOT_OBSERVABLE = "NOT_OBSERVABLE"


class VerificationResult(BaseModel):
    """Result of evaluating a single prediction against observed evidence."""
    prediction_id: str = Field(..., description="Target prediction identifier")
    status: VerificationStatus = Field(..., description="Verification outcome")
    expected_value: Any = Field(..., description="Target machine-readable value expected")
    observed_value: Optional[Any] = Field(default=None, description="Actual value retrieved from AWS")
    explanation: str = Field(..., description="Detailed explanation of verification outcome")
    evidence_reference: Optional[dict[str, Any]] = Field(default=None, description="Pointer to source evidence")
