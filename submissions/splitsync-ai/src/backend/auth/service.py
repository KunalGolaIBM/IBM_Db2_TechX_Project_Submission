"""Authentication service handling JWT tokens and password verification."""

import logging
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt

from config import settings
from db.repositories.user_repo import user_repo
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class AuthService:
    """Handles user registration, login, and JWT token management."""

    def hash_password(self, password: str) -> str:
        """Hash a plain-text password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain-text password against a bcrypt hash."""
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    def create_token(self, user_id: str, email: str) -> str:
        """Create a JWT access token."""
        payload = {
            "sub": user_id,
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AppError(401, "Token has expired")
        except jwt.InvalidTokenError:
            raise AppError(401, "Invalid token")

    def register(self, display_name: str, email: str, password: str) -> dict:
        """Register a new user."""
        email_lower = email.lower().strip()

        if user_repo.email_exists(email_lower):
            raise AppError(409, "An account with this email already exists")

        password_hash = self.hash_password(password)
        user = user_repo.create_user(display_name, email_lower, password_hash)

        if not user:
            raise AppError(500, "Failed to create user account")

        token = self.create_token(user["USER_ID"], email_lower)

        audit_service.log(
            event_type="USER_REGISTERED",
            actor_id=user["USER_ID"],
            entity_type="USER",
            entity_id=user["USER_ID"],
            details={"email": email_lower},
        )

        return {
            "token": token,
            "user": {
                "user_id": user["USER_ID"],
                "display_name": user["DISPLAY_NAME"],
                "email": user["EMAIL"],
                "status": user["STATUS"],
                "created_at": str(user.get("CREATED_AT", "")),
            },
        }

    def login(self, email: str, password: str) -> dict:
        """Authenticate a user and return a JWT token."""
        email_lower = email.lower().strip()
        user = user_repo.get_by_email(email_lower)

        if not user:
            raise AppError(401, "Invalid email or password")

        if not self.verify_password(password, user["PASSWORD_HASH"]):
            raise AppError(401, "Invalid email or password")

        if user.get("STATUS") != "ACTIVE":
            raise AppError(403, "Account is not active")

        token = self.create_token(user["USER_ID"], email_lower)

        audit_service.log(
            event_type="USER_LOGIN",
            actor_id=user["USER_ID"],
            entity_type="USER",
            entity_id=user["USER_ID"],
        )

        return {
            "token": token,
            "user": {
                "user_id": user["USER_ID"],
                "display_name": user["DISPLAY_NAME"],
                "email": user["EMAIL"],
                "status": user["STATUS"],
                "created_at": str(user.get("CREATED_AT", "")),
            },
        }

    def get_current_user(self, token: str) -> dict:
        """Get the current user from a JWT token."""
        payload = self.decode_token(token)
        user = user_repo.get_by_id(payload["sub"])
        if not user:
            raise AppError(401, "User not found")
        return {
            "user_id": user["USER_ID"],
            "display_name": user["DISPLAY_NAME"],
            "email": user["EMAIL"],
            "status": user["STATUS"],
            "created_at": str(user.get("CREATED_AT", "")),
        }


auth_service = AuthService()
