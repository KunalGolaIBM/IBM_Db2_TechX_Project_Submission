"""Impact Finding Domain Models."""

from enum import Enum
from pydantic import BaseModel, Field


class ImpactCategory(str, Enum):
    """Core deterministic impact categories."""
    COST = "COST"
    SECURITY = "SECURITY"
    AVAILABILITY = "AVAILABILITY"
    DATA = "DATA"
    PERFORMANCE = "PERFORMANCE"
    DEPENDENCY = "DEPENDENCY"


class Severity(str, Enum):
    """Deterministic severity levels. (Note: CRITICAL is out of scope for Phase 1)."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImpactFinding(BaseModel):
    """Explains why an infrastructure change matters."""
    rule_id: str = Field(..., description="Unique rule identifier (e.g. CC-EC2-COST-001)")
    rule_version: str = Field(default="1.0.0", description="Semantic rule version")
    resource_address: str = Field(..., description="Target Terraform resource address")
    category: ImpactCategory = Field(..., description="Impact category")
    severity: Severity = Field(..., description="Rule-defined severity level")
    title: str = Field(..., description="Concise finding headline")
    explanation: str = Field(..., description="Concrete, auditable explanation of the configuration shift")
