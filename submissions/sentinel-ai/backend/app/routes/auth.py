from fastapi import APIRouter, HTTPException, status
from app.models.schemas import LoginRequest, LoginResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=LoginResponse)
def login(creds: LoginRequest):
    if creds.username == settings.ADMIN_USERNAME and creds.password == settings.ADMIN_PASSWORD:
        return LoginResponse(
            access_token="sentinel-admin-jwt-token-verified",
            token_type="bearer",
            user={
                "username": creds.username,
                "role": "Chief Information Security Officer (CISO)",
                "clearance": "TOP_SECRET / SCI",
                "org": "Joint Defence Cyber Command"
            }
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials. Contact Joint Cyber Command Administrator."
    )

