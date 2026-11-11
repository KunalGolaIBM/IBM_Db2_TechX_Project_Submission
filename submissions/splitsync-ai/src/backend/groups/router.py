"""Group management API routes."""

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from groups.schemas import CreateGroupRequest, UpdateGroupRequest, AddMemberRequest
from groups.service import group_service

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post("")
def create_group(body: CreateGroupRequest, current_user: dict = Depends(get_current_user)):
    """Create a new group."""
    return group_service.create_group(
        name=body.name,
        user_id=current_user["user_id"],
        description=body.description,
        currency=body.currency,
        split_method=body.split_method,
    )


@router.get("")
def list_groups(current_user: dict = Depends(get_current_user)):
    """List all groups for the current user."""
    return group_service.get_user_groups(current_user["user_id"])


@router.get("/{group_id}")
def get_group(group_id: str, current_user: dict = Depends(get_current_user)):
    """Get group details."""
    return group_service.get_group(group_id, current_user["user_id"])


@router.patch("/{group_id}")
def update_group(group_id: str, body: UpdateGroupRequest, current_user: dict = Depends(get_current_user)):
    """Update group details."""
    return group_service.update_group(
        group_id=group_id,
        user_id=current_user["user_id"],
        name=body.name,
        description=body.description,
        status=body.status,
    )


@router.post("/{group_id}/members")
def add_member(group_id: str, body: AddMemberRequest, current_user: dict = Depends(get_current_user)):
    """Add a member to a group by email."""
    return group_service.add_member(
        group_id=group_id,
        admin_user_id=current_user["user_id"],
        member_email=body.email,
        role=body.role,
    )


@router.get("/{group_id}/members")
def list_members(group_id: str, current_user: dict = Depends(get_current_user)):
    """List all members of a group."""
    return group_service.get_members(group_id, current_user["user_id"])


@router.get("/{group_id}/members/me")
def get_my_membership(group_id: str, current_user: dict = Depends(get_current_user)):
    """Get the current user's membership in a group."""
    return group_service.get_current_member(group_id, current_user["user_id"])


@router.delete("/{group_id}/members/{member_id}")
def remove_member(group_id: str, member_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a member from a group."""
    group_service.remove_member(group_id, current_user["user_id"], member_id)
    return {"message": "Member removed successfully"}
