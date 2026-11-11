"""Repository for GROUPS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class GroupRepository(BaseRepository):
    """Handles all Db2 operations for the GROUPS table."""

    table_name = "GROUPS"

    def create_group(
        self,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        currency: str = "INR",
        split_method: str = "EQUAL",
        accounting_mode: str = "DIRECT",
    ) -> dict:
        """Create a new group and return it."""
        group_id = str(uuid.uuid4())
        sql = """
            INSERT INTO GROUPS (GROUP_ID, NAME, DESCRIPTION, CURRENCY, SPLIT_METHOD, ACCOUNTING_MODE, STATUS, CREATED_BY)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
        """
        self._insert(sql, (group_id, name, description, currency, split_method, accounting_mode, created_by))
        return self.get_by_id(group_id)

    def get_by_id(self, group_id: str) -> Optional[dict]:
        """Fetch a group by GROUP_ID."""
        sql = """
            SELECT GROUP_ID, NAME, DESCRIPTION, CURRENCY, SPLIT_METHOD, ACCOUNTING_MODE,
                   STATUS, CREATED_BY, CREATED_AT
            FROM GROUPS WHERE GROUP_ID = ?
        """
        return self._fetch_one(sql, (group_id,))

    def get_groups_for_user(self, user_id: str) -> list[dict]:
        """Fetch all groups a user belongs to."""
        sql = """
            SELECT g.GROUP_ID, g.NAME, g.DESCRIPTION, g.CURRENCY, g.SPLIT_METHOD,
                   g.ACCOUNTING_MODE, g.STATUS, g.CREATED_BY, g.CREATED_AT
            FROM GROUPS g
            INNER JOIN GROUP_MEMBERS gm ON g.GROUP_ID = gm.GROUP_ID
            WHERE gm.USER_ID = ? AND gm.STATUS = 'ACTIVE' AND g.STATUS = 'ACTIVE'
            ORDER BY g.CREATED_AT DESC
        """
        return self._fetch_all(sql, (user_id,))

    def update_group(self, group_id: str, name: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None) -> Optional[dict]:
        """Update group fields that are provided (not None)."""
        updates = []
        params = []
        if name is not None:
            updates.append("NAME = ?")
            params.append(name)
        if description is not None:
            updates.append("DESCRIPTION = ?")
            params.append(description)
        if status is not None:
            updates.append("STATUS = ?")
            params.append(status)
        if not updates:
            return self.get_by_id(group_id)
        params.append(group_id)
        sql = f"UPDATE GROUPS SET {', '.join(updates)} WHERE GROUP_ID = ?"
        self._update(sql, tuple(params))
        return self.get_by_id(group_id)


group_repo = GroupRepository()
