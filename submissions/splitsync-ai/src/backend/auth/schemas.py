"""Authentication request and response schemas."""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """User registration request."""

    display_name: str = Field(
        ..., min_length=1, max_length=255, description="User display name"
    )
    email: str = Field(
        ..., min_length=5, max_length=255, description="User email address"
    )
    password: str = Field(
        ..., min_length=8, max_length=128, description="User password"
    )


class LoginRequest(BaseModel):
    """User login request."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class AuthResponse(BaseModel):
    """Authentication response with JWT token."""

    token: str
    user: dict


class UserResponse(BaseModel):
    """Public user information."""

    user_id: str
    display_name: str
    email: str
    status: str
    created_at: str
