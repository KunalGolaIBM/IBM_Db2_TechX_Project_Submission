"""Approval API routes."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from approvals.service import approval_service

router = APIRouter(prefix="/groups/{group_id}/approvals", tags=["Approvals"])


class ApprovalDecisionRequest(BaseModel):
    """Payload for submitting an approval decision."""

    decision: str = Field(..., description="Decision must be APPROVED or REJECTED")
    comment: Optional[str] = Field(None, max_length=500, description="Optional remark")


@router.get("/pending")
def get_pending_approvals(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fetch pending cash items requiring approval for a group."""
    return approval_service.get_pending(
        group_id=group_id,
        user_id=current_user["user_id"],
    )


@router.post("/{entity_type}/{entity_id}")
def decide_approval(
    group_id: str,
    entity_type: str,
    entity_id: str,
    body: ApprovalDecisionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Decide on a pending cash contribution or expense."""
    return approval_service.decide(
        group_id=group_id,
        user_id=current_user["user_id"],
        entity_type=entity_type,
        entity_id=entity_id,
        decision=body.decision,
        comment=body.comment,
    )
