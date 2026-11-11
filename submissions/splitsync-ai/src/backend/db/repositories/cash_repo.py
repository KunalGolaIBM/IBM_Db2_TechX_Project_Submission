"""Repository for CASH_CONTRIBUTIONS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class CashRepository(BaseRepository):
    """Handles all Db2 operations for the CASH_CONTRIBUTIONS table."""

    table_name = "CASH_CONTRIBUTIONS"

    def create_cash_contribution(
        self,
        group_id: str,
        member_id: str,
        amount_minor: int,
        description: Optional[str] = None,
    ) -> dict:
        """Insert a pending cash contribution record."""
        cash_id = str(uuid.uuid4())
        sql = """
            INSERT INTO CASH_CONTRIBUTIONS
            (CASH_CONTRIBUTION_ID, GROUP_ID, MEMBER_ID, AMOUNT_MINOR, DESCRIPTION, STATUS)
            VALUES (?, ?, ?, ?, ?, 'PENDING_APPROVAL')
        """
        self._insert(sql, (cash_id, group_id, member_id, amount_minor, description))
        return self.get_by_id(cash_id) or {}

    def get_by_id(self, cash_contribution_id: str) -> Optional[dict]:
        """Fetch cash contribution by ID."""
        sql = """
            SELECT c.CASH_CONTRIBUTION_ID, c.GROUP_ID, c.MEMBER_ID, c.AMOUNT_MINOR,
                   c.DESCRIPTION, c.STATUS, c.CREATED_AT, u.DISPLAY_NAME, u.EMAIL
            FROM CASH_CONTRIBUTIONS c
            INNER JOIN GROUP_MEMBERS gm ON c.MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE c.CASH_CONTRIBUTION_ID = ?
        """
        return self._fetch_one(sql, (cash_contribution_id,))

    def get_by_group(self, group_id: str, status: Optional[str] = None) -> list[dict]:
        """Fetch cash contributions for a group with optional status filtering."""
        if status:
            sql = """
                SELECT c.CASH_CONTRIBUTION_ID, c.GROUP_ID, c.MEMBER_ID, c.AMOUNT_MINOR,
                       c.DESCRIPTION, c.STATUS, c.CREATED_AT, u.DISPLAY_NAME, u.EMAIL
                FROM CASH_CONTRIBUTIONS c
                INNER JOIN GROUP_MEMBERS gm ON c.MEMBER_ID = gm.GROUP_MEMBER_ID
                INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
                WHERE c.GROUP_ID = ? AND c.STATUS = ?
                ORDER BY c.CREATED_AT DESC
            """
            return self._fetch_all(sql, (group_id, status))
        else:
            sql = """
                SELECT c.CASH_CONTRIBUTION_ID, c.GROUP_ID, c.MEMBER_ID, c.AMOUNT_MINOR,
                       c.DESCRIPTION, c.STATUS, c.CREATED_AT, u.DISPLAY_NAME, u.EMAIL
                FROM CASH_CONTRIBUTIONS c
                INNER JOIN GROUP_MEMBERS gm ON c.MEMBER_ID = gm.GROUP_MEMBER_ID
                INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
                WHERE c.GROUP_ID = ?
                ORDER BY c.CREATED_AT DESC
            """
            return self._fetch_all(sql, (group_id,))

    def update_status(self, cash_contribution_id: str, status: str) -> None:
        """Update contribution status (e.g. APPROVED, REJECTED)."""
        sql = "UPDATE CASH_CONTRIBUTIONS SET STATUS = ? WHERE CASH_CONTRIBUTION_ID = ?"
        self._update(sql, (status, cash_contribution_id))


cash_repo = CashRepository()
