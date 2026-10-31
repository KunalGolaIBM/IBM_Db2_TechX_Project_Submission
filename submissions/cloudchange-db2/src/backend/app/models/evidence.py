"""Evidence and Resource Identity Domain Models."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class EvidenceRequirement(BaseModel):
    """Specifies an empirical observation required from AWS."""
    provider: str = Field(default="aws", description="Cloud provider identifier")
    service: str = Field(..., description="Target service (e.g. ec2, rds)")
    resource_type: str = Field(..., description="Target AWS resource type (e.g. instance, security_group)")
    field: str = Field(..., description="Target configuration field to extract")


class Evidence(BaseModel):
    """Empirical observation retrieved from AWS APIs."""
    source: str = Field(..., description="Source system/API (e.g. aws.ec2)")
    resource_id: str = Field(..., description="Physical AWS resource ID (e.g. i-0123456789)")
    field: str = Field(..., description="Configuration attribute or metric observed")
    observed_value: Any = Field(..., description="Observed value returned by AWS")
    observed_at: str = Field(..., description="ISO 8601 observation timestamp")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Supplemental context")


class ResourceIdentity(BaseModel):
    """Bridges a Terraform address to a physical AWS resource ID via Terraform state."""
    terraform_address: str = Field(..., description="Terraform address (e.g. aws_instance.web)")
    resource_type: str = Field(..., description="Terraform resource type (e.g. aws_instance)")
    provider: str = Field(default="aws", description="Target provider")
    resource_id: str = Field(..., description="Physical AWS resource ID (e.g. i-0123456789)")
