"""Audit trail API routes."""

from fastapi import APIRouter, Depends, Query

from auth.dependencies import get_current_user
from db.repositories.member_repo import member_repo
from audit.service import audit_service
from api.middleware import AppError

router = APIRouter(prefix="/groups/{group_id}/audit", tags=["Audit Log"])


@router.get("")
def get_group_audit_trail(
    group_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of audit events to retrieve"),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve immutable audit trail records for a group."""
    member = member_repo.get_member_by_group_and_user(group_id, current_user["user_id"])
    if not member:
        raise AppError(403, "Access denied. You are not a member of this group.")

    return audit_service.get_group_events(group_id=group_id, limit=limit)
