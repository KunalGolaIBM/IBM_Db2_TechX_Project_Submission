"""
ClaimGuard AI - Authentication Router
Handles examiner and administrator login, JWT token issuance, and identity verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from ..database.repository import repository
from ..models.schemas import TokenResponse, UserLogin, UserResponse
from ..utils.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin):
    """Authenticates users against USERS table and returns a signed JWT."""
    user = repository.get_user_by_username(payload.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Verify username and password."
        )

    if not verify_password(payload.password, user.get("HASHED_PASSWORD", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Verify username and password."
        )

    token_data = {
        "sub": user["USER_ID"],
        "username": user["USERNAME"],
        "role": user["ROLE"],
        "name": user["FULL_NAME"]
    }
    token = create_access_token(token_data)

    user_info = {
        "user_id": user["USER_ID"],
        "username": user["USERNAME"],
        "email": user["EMAIL"],
        "full_name": user["FULL_NAME"],
        "role": user["ROLE"]
    }

    return TokenResponse(access_token=token, token_type="bearer", user=user_info)


@router.get("/me")
def get_current_profile(current_user: dict = Depends(get_current_user)):
    """Returns profile for currently logged in session."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide Bearer token."
        )
    return current_user
