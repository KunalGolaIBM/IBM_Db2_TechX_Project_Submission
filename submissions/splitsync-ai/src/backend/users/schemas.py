"""User-related schemas."""

from pydantic import BaseModel


class UserProfile(BaseModel):
    """User profile response."""

    user_id: str
    display_name: str
    email: str
    status: str
    created_at: str
