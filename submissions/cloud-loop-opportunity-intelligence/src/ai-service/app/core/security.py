from fastapi import Header, HTTPException, status
from typing import Optional
from app.core.config import settings
import re

def verify_internal_api_key(
    x_internal_key: Optional[str] = Header(None, alias="x-internal-key", description="Shared internal secret key"),
    authorization: Optional[str] = Header(None, description="Bearer token fallback"),
):
    """
    Validates shared secret key between Next.js server handlers and ai-service.
    Never exposed to the client browser.
    """
    key = x_internal_key
    if not key and authorization and authorization.startswith("Bearer "):
        key = authorization[7:].strip()

    expected_key = settings.INTERNAL_API_KEY
    if key == expected_key:
        return True

    if settings.DEBUG and (not key or key == "dev_internal_key"):
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing internal service API key (x-internal-key).",
    )

def verify_admin_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key", description="Admin API Key for protected ingestion routes")
):
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid administrative credentials. Ingestion endpoint is protected.",
        )
    return True

def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="x-user-id", description="Authenticated Clerk or Demo User ID")
) -> str:
    """
    Extracts authenticated user context passed from Next.js server handler.
    Falls back to settings.DEMO_USER_ID if in demo mode.
    """
    if x_user_id and x_user_id.strip():
        cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", x_user_id.strip())
        if cleaned:
            return cleaned

    if settings.AUTH_MODE == "demo":
        return settings.DEMO_USER_ID

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authenticated user header (x-user-id).",
    )
