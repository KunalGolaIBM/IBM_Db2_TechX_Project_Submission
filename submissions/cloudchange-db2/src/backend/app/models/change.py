"""Canonical Change Domain Models."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Normalized action types for infrastructure changes."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REPLACE = "REPLACE"


class AttributeDiff(BaseModel):
    """Structured attribute delta between before and after states."""
    path: str = Field(..., description="Dot or bracket notation path to attribute (e.g. ingress[0].cidr_blocks)")
    before: Optional[Any] = Field(None, description="Value prior to change")
    after: Optional[Any] = Field(None, description="Intended value after change")


class CanonicalChange(BaseModel):
    """Internal canonical representation of a Terraform resource change."""
    resource_address: str = Field(..., description="Terraform address (e.g. aws_instance.web)")
    resource_type: str = Field(..., description="Terraform resource type (e.g. aws_instance)")
    action: ActionType = Field(..., description="Normalized action (CREATE, UPDATE, DELETE, REPLACE)")
    before: Optional[dict[str, Any]] = Field(default=None, description="Resource attributes before change")
    after: Optional[dict[str, Any]] = Field(default=None, description="Resource attributes after change")
    requires_replacement: bool = Field(default=False, description="True if change triggers resource recreation")
    diffs: list[AttributeDiff] = Field(default_factory=list, description="Structured attribute-level differences")


class UnsupportedResourceWarning(BaseModel):
    """Structured notification for resources outside the Phase 1 supported scope."""
    resource_address: str = Field(..., description="Terraform address of unsupported resource")
    resource_type: str = Field(..., description="Unsupported Terraform resource type")
    reason: str = Field(..., description="Explanation of why this resource is outside Phase 1 scope")


class PlanNormalizationResult(BaseModel):
    """Result of plan ingestion, parsing, and normalization."""
    changes: list[CanonicalChange] = Field(default_factory=list, description="Actionable canonical changes")
    unsupported_resources: list[UnsupportedResourceWarning] = Field(
        default_factory=list,
        description="Structured warnings for resources outside Phase 1 scope"
    )
    ignored_noops: list[str] = Field(
        default_factory=list,
        description="Addresses of unchanged (no-op) resources"
    )
    ignored_reads: list[str] = Field(
        default_factory=list,
        description="Addresses of data source read entries"
    )

    def __iter__(self):
        """Allow iterating directly over actionable changes."""
        return iter(self.changes)

    def __len__(self):
        """Allow checking len() of actionable changes."""
        return len(self.changes)

    def __getitem__(self, idx):
        """Allow indexing directly into actionable changes."""
        return self.changes[idx]
