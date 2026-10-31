"""Run Domain Models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from backend.app.models.change import CanonicalChange, UnsupportedResourceWarning
from backend.app.models.impact import ImpactFinding
from backend.app.models.prediction import Prediction
from backend.app.models.verification import VerificationResult, VerificationStatus


class RunStatus(str, Enum):
    """Lifecycle statuses for a CloudChange run."""
    ANALYZING = "ANALYZING"
    PREDICTED = "PREDICTED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class ActionCounts(BaseModel):
    """Counts of canonical actionable changes by normalized action type."""
    CREATE: int = Field(default=0, description="Count of CREATE actions")
    UPDATE: int = Field(default=0, description="Count of UPDATE actions")
    DELETE: int = Field(default=0, description="Count of DELETE actions")
    REPLACE: int = Field(default=0, description="Count of REPLACE actions (counted as single action)")


class SeverityCounts(BaseModel):
    """Counts of rule-generated findings by severity level."""
    HIGH: int = Field(default=0, description="Count of HIGH severity findings")
    MEDIUM: int = Field(default=0, description="Count of MEDIUM severity findings")
    LOW: int = Field(default=0, description="Count of LOW severity findings")
    INFO: int = Field(default=0, description="Count of INFO severity findings")


class RunSummary(BaseModel):
    """Aggregated deterministic summary statistics for a CloudChange run."""
    total_changes: int = Field(..., description="Count of actionable canonical changes (len(changes))")
    actions: ActionCounts = Field(..., description="Counts of normalized actions (a replacement is one REPLACE)")
    findings_count: int = Field(..., description="Total count of deterministic impact findings (len(findings))")
    findings_by_severity: SeverityCounts = Field(
        ...,
        description="Counts of findings by severity (HIGH, MEDIUM, LOW, INFO), zero when absent"
    )
    unsupported_count: int = Field(..., description="Count of preserved unsupported resource warnings")
    noop_count: int = Field(..., description="Count of preserved unchanged (no-op) resource addresses")
    read_count: int = Field(..., description="Count of preserved data source read entry addresses")


def build_run_summary(
    changes: list[CanonicalChange],
    findings: list[ImpactFinding],
    unsupported_resources: list[UnsupportedResourceWarning],
    ignored_noops: list[str],
    ignored_reads: list[str],
) -> RunSummary:
    """Build deterministic summary counters strictly adhering to domain semantics."""
    actions_dict = {"CREATE": 0, "UPDATE": 0, "DELETE": 0, "REPLACE": 0}
    for c in changes:
        act = c.action.value if hasattr(c.action, "value") else str(c.action)
        if act in actions_dict:
            actions_dict[act] += 1

    sev_dict = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        if sev in sev_dict:
            sev_dict[sev] += 1

    return RunSummary(
        total_changes=len(changes),
        actions=ActionCounts(**actions_dict),
        findings_count=len(findings),
        findings_by_severity=SeverityCounts(**sev_dict),
        unsupported_count=len(unsupported_resources),
        noop_count=len(ignored_noops),
        read_count=len(ignored_reads),
    )


class Run(BaseModel):
    """Represents a complete CloudChange analysis and verification lifecycle."""
    run_id: str = Field(..., description="Unique run identifier (UUID)")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    status: RunStatus = Field(default=RunStatus.PREDICTED, description="Current run status")
    summary: RunSummary = Field(..., description="Aggregated deterministic statistics")
    changes: list[CanonicalChange] = Field(default_factory=list, description="Extracted canonical changes")
    findings: list[ImpactFinding] = Field(default_factory=list, description="Rule-generated impact findings")
    predictions: list[Prediction] = Field(default_factory=list, description="Expected post-deployment states")
    unsupported_resources: list[UnsupportedResourceWarning] = Field(
        default_factory=list,
        description="Structured warnings for resources outside Phase 1 scope"
    )
    ignored_noops: list[str] = Field(
        default_factory=list,
        description="Preserved addresses of unchanged (no-op) resources"
    )
    ignored_reads: list[str] = Field(
        default_factory=list,
        description="Preserved addresses of data source read entries"
    )
    verification_results: list[VerificationResult] = Field(
        default_factory=list,
        description="Verification outcomes"
    )

    @model_validator(mode="after")
    def validate_verified_status(self) -> "Run":
        """Enforce domain rule: Run must not be VERIFIED if any prediction is unresolved or mismatched."""
        if self.status == RunStatus.VERIFIED:
            if not self.predictions:
                return self
            if not self.verification_results or len(self.verification_results) != len(self.predictions):
                raise ValueError("Run cannot be VERIFIED when predictions remain unresolved.")
            for res in self.verification_results:
                if res.status != VerificationStatus.VERIFIED:
                    raise ValueError(f"Run cannot be VERIFIED when result {res.prediction_id} has status {res.status.value}.")
        return self
