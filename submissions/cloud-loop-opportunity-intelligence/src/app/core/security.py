from fastapi import Header, HTTPException, status
from backend.app.core.config import settings
import re

def verify_admin_key(x_admin_key: str = Header(..., description="Admin API Key for protected ingestion routes")):
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid administrative credentials. Ingestion endpoint is protected.",
        )
    return True

def get_current_user_id(x_user_id: str = Header(..., description="Authenticated Clerk User ID")):
    if not x_user_id or len(x_user_id.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid authenticated user context required.",
        )
    # Sanitize user ID to prevent header injection
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", x_user_id.strip())
    return cleaned

