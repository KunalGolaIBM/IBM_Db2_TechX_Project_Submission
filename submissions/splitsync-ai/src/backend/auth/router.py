"""Authentication API routes."""

from fastapi import APIRouter, Depends

from auth.schemas import RegisterRequest, LoginRequest
from auth.service import auth_service
from auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register(body: RegisterRequest):
    """Register a new user account."""
    result = auth_service.register(
        display_name=body.display_name,
        email=body.email,
        password=body.password,
    )
    return result


@router.post("/login")
def login(body: LoginRequest):
    """Authenticate and receive a JWT token."""
    result = auth_service.login(email=body.email, password=body.password)
    return result


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get the current authenticated user."""
    return current_user


@router.post("/logout")
def logout():
    """Logout (client-side token removal)."""
    return {"message": "Logged out successfully"}
