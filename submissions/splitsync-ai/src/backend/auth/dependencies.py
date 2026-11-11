"""FastAPI authentication dependencies."""

from fastapi import Request

from auth.service import auth_service
from api.middleware import AppError


def get_current_user(request: Request) -> dict:
    """Extract and validate JWT token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AppError(
            401, "Authentication required", "Missing or invalid Authorization header"
        )

    token = auth_header.split(" ", 1)[1]
    return auth_service.get_current_user(token)
