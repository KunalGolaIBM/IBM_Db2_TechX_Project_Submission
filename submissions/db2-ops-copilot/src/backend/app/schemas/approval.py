"""Request and response models for deterministic action proposals and approvals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from app.schemas.common import StrictModel


class ActionProposal(StrictModel):
    action_type: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(max_length=3)
    rationale: str = Field(min_length=1, max_length=1000)


class AgentProposalRequest(StrictModel):
    actions: list[ActionProposal] = Field(min_length=1, max_length=16)
    session_id: str | None = Field(default=None, max_length=64)


class ApprovalDecisionRequest(StrictModel):
    decision: str = Field(min_length=1, max_length=32)
    actor: str | None = Field(default=None, max_length=256)
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalExecution(StrictModel):
    status: str
    simulated: bool
    detail: str
    reason: str | None = None
    code: str | None = None
    latency_ms: int | None = None
    executed_at: str | None = None


class ApprovalModel(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    status: str
    action_type: str
    params: dict[str, str]
    statement: str
    title: str
    rationale: str
    risk: str
    created_at: datetime
    expires_at: datetime
    request_id: str | None
    session_id: str | None
    decided_by: str | None
    decided_at: datetime | None
    decision_reason: str | None
    execution: ApprovalExecution | None


class ApprovalListResponse(StrictModel):
    approvals: list[ApprovalModel]
    total: int
    mock: bool
    execution_mode: Literal[
        "mock_simulated", "disabled", "admin_not_configured", "enabled_unverified"
    ]


class ApprovalDecisionResponse(StrictModel):
    approval: ApprovalModel
    mock: bool


class AgentProposalResponse(StrictModel):
    approvals: list[ApprovalModel]
    tool_calls: int
    max_tool_calls: int
    mock: bool
