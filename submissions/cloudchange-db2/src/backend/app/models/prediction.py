"""Prediction Domain Models."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from backend.app.models.evidence import EvidenceRequirement


class VerificationApproach(str, Enum):
    """Declared verification methodology for post-deployment observation.
    
    Semantic distinctions:
    - EXACT_MATCH: Direct scalar equality comparison between observed AWS state and expected value
      (e.g., observed instance_type == "t3.large").
    - CONFIG_MATCH: Key-value dictionary comparison where observed resource configuration must match
      all expected operational attribute keys and values (e.g., ebs_optimized, monitoring flags).
    - SET_CONTAINS: Target collection comparison ensuring expected elements are contained within
      observed AWS collection (e.g., security group ingress CIDRs or exposed sensitive ports).
    - IDENTITY_REPLACED: Physical resource identity comparison requiring pre-apply and post-apply physical
      resource IDs to both exist and differ (ensuring replacement actually happened and identity is not fabricated).
    - RESOURCE_DELETED: Confirmed absence in AWS API (distinguishing 404/NotFound from auth or throttling errors).
    """
    EXACT_MATCH = "EXACT_MATCH"
    CONFIG_MATCH = "CONFIG_MATCH"
    SET_CONTAINS = "SET_CONTAINS"
    IDENTITY_REPLACED = "IDENTITY_REPLACED"
    RESOURCE_DELETED = "RESOURCE_DELETED"


class Prediction(BaseModel):
    """Represents an expected observable post-deployment state in AWS."""
    prediction_id: str = Field(..., description="Unique prediction identifier")
    resource_address: Optional[str] = Field(
        default=None,
        description="Explicit target Terraform resource address (e.g. aws_instance.api)"
    )
    metric: str = Field(..., description="Observable AWS metric or configuration field")
    expected_value: Any = Field(..., description="Target machine-readable value expected in AWS")
    direction: Optional[str] = Field(default=None, description="Optional directional summary (e.g. SCALE_UP, REPLACED, OPEN)")
    verification_approach: VerificationApproach = Field(
        ...,
        description="Declared verification approach (EXACT_MATCH, CONFIG_MATCH, SET_CONTAINS, IDENTITY_REPLACED, RESOURCE_DELETED)"
    )
    rationale: str = Field(..., description="Deterministic reasoning for the prediction")
    evidence_requirement: EvidenceRequirement = Field(
        ...,
        description="Mandatory declared AWS evidence needed to verify this prediction in Phase 1"
    )
