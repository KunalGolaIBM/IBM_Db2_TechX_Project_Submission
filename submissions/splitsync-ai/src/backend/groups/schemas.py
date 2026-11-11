"""Group management schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class CreateGroupRequest(BaseModel):
    """Request to create a new group."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    currency: str = Field("INR", max_length=10)
    split_method: str = Field("EQUAL", max_length=20)


class UpdateGroupRequest(BaseModel):
    """Request to update a group."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = None


class AddMemberRequest(BaseModel):
    """Request to add a member to a group."""
    email: str = Field(..., description="Email of user to add")
    role: str = Field("MEMBER", description="Role: ADMIN or MEMBER")


class GroupResponse(BaseModel):
    """Group details response."""
    group_id: str
    name: str
    description: Optional[str] = None
    currency: str
    split_method: str
    accounting_mode: str
    status: str
    created_by: str
    created_at: str
    member_count: Optional[int] = None


class MemberResponse(BaseModel):
    """Group member response."""
    group_member_id: str
    group_id: str
    user_id: str
    display_name: str
    email: str
    role: str
    status: str
    joined_at: str
