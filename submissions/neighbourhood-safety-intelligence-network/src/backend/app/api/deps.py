from typing import List

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.database.base import get_db
from backend.app.models.entities import User

STAFF_ROLES = ("responder", "admin")

_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization header missing. Please provide a Bearer token.", _UNAUTHORIZED)

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authorization format. Must be 'Bearer <token>'.", _UNAUTHORIZED)

    payload = decode_access_token(token.strip())
    email = payload.get("sub") if payload else None
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalid or expired. Please sign in again.", _UNAUTHORIZED)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists. Please sign in again.", _UNAUTHORIZED)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated. Contact community administrators.")
    return user


def is_staff(user: User) -> bool:
    return user.role in STAFF_ROLES


def ensure_verified_staff(user: User) -> None:
    """Responders must be verified by an admin before they can act on incidents."""
    if not is_staff(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only verified responders or admins can perform this action.")
    if user.role == "responder" and not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your responder account is awaiting admin verification.")


def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to access this resource.")
        return current_user
    return role_checker
