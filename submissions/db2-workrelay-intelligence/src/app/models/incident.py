from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    CLASSIFYING = "CLASSIFYING"
    INVESTIGATING = "INVESTIGATING"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class IncidentAction(BaseModel):
    name: str
    description: str = ""
    status: ActionStatus = ActionStatus.PENDING
    result: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class IncidentEvent(BaseModel):
    """A timestamped record of an incident lifecycle event in Db2."""

    event: str
    status: IncidentStatus
    step: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: f"INC-{uuid4().hex[:8].upper()}")
    title: str
    description: str
    service: str
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN

    current_step: str = "incident_received"
    workflow: str | None = None

    actions: list[IncidentAction] = Field(default_factory=list)
    history: list[IncidentEvent] = Field(default_factory=list)

    resolution: str | None = None
    escalation_reason: str | None = None

    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def touch(self) -> None:
        """Update the incident modification timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def record_event(
        self,
        event: str,
        *,
        step: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> IncidentEvent:
        """Append an observable lifecycle event to the incident history."""
        evt = IncidentEvent(
            event=event,
            status=self.status,
            step=step or self.current_step,
            details=details or {},
        )
        self.history.append(evt)
        self.touch()
        return evt


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Concise summary of the incident")
    description: str = Field(..., min_length=1, description="Detailed problem description")
    service: str = Field(..., min_length=1, description="Affected service or subsystem")
    severity: IncidentSeverity | None = Field(default=None, description="Optional explicit severity (auto-classified if omitted)")
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    resolution: str | None = None
    escalation_reason: str | None = None
    metadata: dict[str, Any] | None = None


class IncidentResponse(BaseModel):
    incident: Incident


class IncidentListResponse(BaseModel):
    items: list[Incident]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    db2_connected: bool
    db2_mode: str
    ai_status: dict[str, Any]
