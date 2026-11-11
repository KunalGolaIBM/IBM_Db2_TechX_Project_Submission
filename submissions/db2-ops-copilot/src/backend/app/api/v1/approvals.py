"""Human approval and deterministic action-proposal routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Path, Query, Request

from app.agent.actions import PreparedAction, prepare_action
from app.api.deps import build_approval_service, get_app_settings
from app.core.errors import AppError
from app.schemas.approval import (
    AgentProposalRequest,
    AgentProposalResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalModel,
)

router = APIRouter(tags=["approvals"])
_APPROVAL_ID = r"apr_[0-9a-f]{12}"


def _execution_mode(settings) -> str:
    if settings.is_mock:
        return "mock_simulated"
    if not settings.agent_actions_enabled:
        return "disabled"
    if not settings.db2_admin_user or not settings.db2_admin_password.get_secret_value():
        return "admin_not_configured"
    return "enabled_unverified"


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
) -> ApprovalListResponse:
    service = build_approval_service(request)
    all_pending = service.list(status="PENDING", limit=500)
    approvals = all_pending[:limit]
    settings = get_app_settings()
    return ApprovalListResponse(
        approvals=approvals,
        total=len(all_pending),
        mock=settings.is_mock,
        execution_mode=_execution_mode(settings),
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalModel)
def get_approval(
    request: Request,
    approval_id: str = Path(pattern=_APPROVAL_ID),
) -> ApprovalModel:
    return build_approval_service(request).get(approval_id)


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalDecisionResponse)
def decide_approval(
    payload: ApprovalDecisionRequest,
    request: Request,
    approval_id: str = Path(pattern=_APPROVAL_ID),
) -> ApprovalDecisionResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    approval = build_approval_service(request).decide(
        approval_id,
        payload.decision,
        decided_by=payload.actor,
        reason=payload.reason,
        request_id=request_id,
    )
    return ApprovalDecisionResponse(approval=approval, mock=get_app_settings().is_mock)


@router.post("/agent/propose", response_model=AgentProposalResponse)
def propose_actions(
    payload: AgentProposalRequest, request: Request
) -> AgentProposalResponse:
    """Validate bounded action proposals and create pending approvals only."""
    settings = get_app_settings()
    max_tool_calls = settings.agent_max_tool_calls
    requested = len(payload.actions)
    if requested > max_tool_calls:
        raise AppError(
            f"Proposal exceeds the configured tool-call limit ({max_tool_calls}).",
            code="AGENT_TOOL_LIMIT",
            status_code=422,
            detail={"requested": requested, "max_tool_calls": max_tool_calls},
        )

    # Prepare the complete batch first, so an invalid item cannot leave a
    # partial set of approvals behind.
    prepared: list[tuple[PreparedAction, str]] = [
        (prepare_action(item.action_type, item.params), item.rationale)
        for item in payload.actions
    ]
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    service = build_approval_service(request)
    approvals = [
        service.propose(
            action,
            rationale=rationale,
            request_id=request_id,
            session_id=payload.session_id,
        )
        for action, rationale in prepared
    ]
    return AgentProposalResponse(
        approvals=approvals,
        tool_calls=requested,
        max_tool_calls=max_tool_calls,
        mock=settings.is_mock,
    )
