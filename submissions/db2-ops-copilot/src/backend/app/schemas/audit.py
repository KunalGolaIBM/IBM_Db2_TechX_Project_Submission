"""Audit log schemas."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import StrictModel


class AuditEntryModel(StrictModel):
    id: int
    timestamp: str
    operation: str = "chat"  # chat | sql_execute | sql_validate | ...
    intent: str
    question: str
    status: str
    latency_ms: int
    detail: str | None = None
    request_id: str | None = None


class AuditResponse(StrictModel):
    entries: list[AuditEntryModel] = Field(default_factory=list)
    total: int = 0
    mock: bool
