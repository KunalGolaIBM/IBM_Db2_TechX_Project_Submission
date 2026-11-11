"""Repository for APP_USERS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Handles all Db2 operations for the APP_USERS table."""

    table_name = "APP_USERS"

    def create_user(self, display_name: str, email: str, password_hash: str) -> dict:
        """Insert a new user and return the created record."""
        user_id = str(uuid.uuid4())
        sql = """
            INSERT INTO APP_USERS (USER_ID, DISPLAY_NAME, EMAIL, PASSWORD_HASH, STATUS)
            VALUES (?, ?, ?, ?, 'ACTIVE')
        """
        self._insert(sql, (user_id, display_name, email, password_hash))
        return self.get_by_id(user_id)

    def get_by_id(self, user_id: str) -> Optional[dict]:
        """Fetch a user by USER_ID."""
        sql = "SELECT USER_ID, DISPLAY_NAME, EMAIL, STATUS, CREATED_AT FROM APP_USERS WHERE USER_ID = ?"
        return self._fetch_one(sql, (user_id,))

    def get_by_email(self, email: str) -> Optional[dict]:
        """Fetch a user by EMAIL (includes password hash for auth)."""
        sql = "SELECT USER_ID, DISPLAY_NAME, EMAIL, PASSWORD_HASH, STATUS, CREATED_AT FROM APP_USERS WHERE EMAIL = ?"
        return self._fetch_one(sql, (email,))

    def email_exists(self, email: str) -> bool:
        """Check if an email is already registered."""
        sql = "SELECT COUNT(*) AS CNT FROM APP_USERS WHERE EMAIL = ?"
        row = self._fetch_one(sql, (email,))
        return row is not None and row.get("CNT", 0) > 0

    def update_status(self, user_id: str, status: str) -> None:
        """Update user account status."""
        sql = "UPDATE APP_USERS SET STATUS = ? WHERE USER_ID = ?"
        self._update(sql, (status, user_id))


user_repo = UserRepository()
