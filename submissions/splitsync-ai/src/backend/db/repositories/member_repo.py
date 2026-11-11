"""Repository for GROUP_MEMBERS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class MemberRepository(BaseRepository):
    """Handles all Db2 operations for the GROUP_MEMBERS table."""

    table_name = "GROUP_MEMBERS"

    def add_member(self, group_id: str, user_id: str, role: str = "MEMBER") -> dict:
        """Add a member to a group."""
        member_id = str(uuid.uuid4())
        sql = """
            INSERT INTO GROUP_MEMBERS (GROUP_MEMBER_ID, GROUP_ID, USER_ID, ROLE, STATUS)
            VALUES (?, ?, ?, ?, 'ACTIVE')
        """
        self._insert(sql, (member_id, group_id, user_id, role))
        return self.get_by_id(member_id)

    def get_by_id(self, member_id: str) -> Optional[dict]:
        """Fetch a member record by GROUP_MEMBER_ID."""
        sql = """
            SELECT gm.GROUP_MEMBER_ID, gm.GROUP_ID, gm.USER_ID, gm.ROLE, gm.STATUS, gm.JOINED_AT,
                   u.DISPLAY_NAME, u.EMAIL
            FROM GROUP_MEMBERS gm
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE gm.GROUP_MEMBER_ID = ?
        """
        return self._fetch_one(sql, (member_id,))

    def get_members_of_group(self, group_id: str) -> list[dict]:
        """Fetch all active members of a group."""
        sql = """
            SELECT gm.GROUP_MEMBER_ID, gm.GROUP_ID, gm.USER_ID, gm.ROLE, gm.STATUS, gm.JOINED_AT,
                   u.DISPLAY_NAME, u.EMAIL
            FROM GROUP_MEMBERS gm
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE gm.GROUP_ID = ? AND gm.STATUS = 'ACTIVE'
            ORDER BY gm.JOINED_AT
        """
        return self._fetch_all(sql, (group_id,))

    def get_member_by_group_and_user(self, group_id: str, user_id: str) -> Optional[dict]:
        """Fetch a member record for a specific user in a specific group."""
        sql = """
            SELECT gm.GROUP_MEMBER_ID, gm.GROUP_ID, gm.USER_ID, gm.ROLE, gm.STATUS, gm.JOINED_AT,
                   u.DISPLAY_NAME, u.EMAIL
            FROM GROUP_MEMBERS gm
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE gm.GROUP_ID = ? AND gm.USER_ID = ? AND gm.STATUS = 'ACTIVE'
        """
        return self._fetch_one(sql, (group_id, user_id))

    def is_member(self, group_id: str, user_id: str) -> bool:
        """Check if a user is an active member of a group."""
        sql = """
            SELECT COUNT(*) AS CNT FROM GROUP_MEMBERS
            WHERE GROUP_ID = ? AND USER_ID = ? AND STATUS = 'ACTIVE'
        """
        row = self._fetch_one(sql, (group_id, user_id))
        return row is not None and row.get("CNT", 0) > 0

    def is_admin(self, group_id: str, user_id: str) -> bool:
        """Check if a user is an admin of a group."""
        sql = """
            SELECT COUNT(*) AS CNT FROM GROUP_MEMBERS
            WHERE GROUP_ID = ? AND USER_ID = ? AND ROLE = 'ADMIN' AND STATUS = 'ACTIVE'
        """
        row = self._fetch_one(sql, (group_id, user_id))
        return row is not None and row.get("CNT", 0) > 0

    def remove_member(self, member_id: str) -> None:
        """Soft-delete a member by setting status to INACTIVE."""
        sql = "UPDATE GROUP_MEMBERS SET STATUS = 'INACTIVE' WHERE GROUP_MEMBER_ID = ?"
        self._update(sql, (member_id,))

    def get_member_count(self, group_id: str) -> int:
        """Count active members in a group."""
        sql = "SELECT COUNT(*) AS CNT FROM GROUP_MEMBERS WHERE GROUP_ID = ? AND STATUS = 'ACTIVE'"
        row = self._fetch_one(sql, (group_id,))
        return row.get("CNT", 0) if row else 0


member_repo = MemberRepository()
