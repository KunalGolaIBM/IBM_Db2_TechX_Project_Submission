"""User service for profile operations."""

from db.repositories.user_repo import user_repo
from api.middleware import AppError


class UserService:
    """Handles user profile operations."""

    def get_profile(self, user_id: str) -> dict:
        """Get a user's public profile."""
        user = user_repo.get_by_id(user_id)
        if not user:
            raise AppError(404, "User not found")
        return {
            "user_id": user["USER_ID"],
            "display_name": user["DISPLAY_NAME"],
            "email": user["EMAIL"],
            "status": user["STATUS"],
            "created_at": str(user.get("CREATED_AT", "")),
        }


user_service = UserService()
