"""Repository for LEDGER_ENTRIES table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class LedgerRepository(BaseRepository):
    """Handles all Db2 operations for the LEDGER_ENTRIES table."""

    table_name = "LEDGER_ENTRIES"

    def create_entry(
        self,
        group_id: str,
        member_id: Optional[str],
        entity_type: str,
        entity_id: str,
        entry_type: str,
        amount_minor: int,
        currency: str = "INR",
    ) -> dict:
        """Insert a double-entry ledger line item."""
        ledger_entry_id = str(uuid.uuid4())
        sql = """
            INSERT INTO LEDGER_ENTRIES
            (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'POSTED')
        """
        self._insert(
            sql,
            (
                ledger_entry_id,
                group_id,
                member_id,
                entity_type.upper(),
                entity_id,
                entry_type.upper(),
                amount_minor,
                currency,
            ),
        )
        return self.get_by_id(ledger_entry_id) or {}

    def get_by_id(self, ledger_entry_id: str) -> Optional[dict]:
        """Fetch a single ledger entry by primary key."""
        sql = """
            SELECT LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID,
                   ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS, CREATED_AT
            FROM LEDGER_ENTRIES
            WHERE LEDGER_ENTRY_ID = ?
        """
        return self._fetch_one(sql, (ledger_entry_id,))

    def get_entries_by_group(self, group_id: str, limit: int = 100) -> list[dict]:
        """Fetch recent ledger entries for a group."""
        sql = """
            SELECT le.LEDGER_ENTRY_ID, le.GROUP_ID, le.MEMBER_ID, le.ENTITY_TYPE, le.ENTITY_ID,
                   le.ENTRY_TYPE, le.AMOUNT_MINOR, le.CURRENCY, le.STATUS, le.CREATED_AT,
                   u.DISPLAY_NAME, u.EMAIL
            FROM LEDGER_ENTRIES le
            LEFT JOIN GROUP_MEMBERS gm ON le.MEMBER_ID = gm.GROUP_MEMBER_ID
            LEFT JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE le.GROUP_ID = ?
            ORDER BY le.CREATED_AT DESC
            FETCH FIRST ? ROWS ONLY
        """
        return self._fetch_all(sql, (group_id, limit))

    def get_member_balances(self, group_id: str) -> list[dict]:
        """Fetch net balances and aggregates for all active members in a group."""
        sql = """
            SELECT gm.GROUP_MEMBER_ID AS MEMBER_ID,
                   u.DISPLAY_NAME,
                   u.EMAIL,
                   COALESCE(SUM(CASE WHEN le.ENTRY_TYPE = 'CREDIT' THEN le.AMOUNT_MINOR ELSE 0 END), 0) AS TOTAL_CREDIT_MINOR,
                   COALESCE(SUM(CASE WHEN le.ENTRY_TYPE = 'DEBIT' THEN le.AMOUNT_MINOR ELSE 0 END), 0) AS TOTAL_DEBIT_MINOR,
                   COALESCE(SUM(CASE WHEN le.ENTRY_TYPE = 'CREDIT' THEN le.AMOUNT_MINOR ELSE -le.AMOUNT_MINOR END), 0) AS NET_BALANCE_MINOR
            FROM GROUP_MEMBERS gm
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            LEFT JOIN LEDGER_ENTRIES le ON gm.GROUP_MEMBER_ID = le.MEMBER_ID AND le.STATUS = 'POSTED' AND le.GROUP_ID = ?
            WHERE gm.GROUP_ID = ? AND gm.STATUS = 'ACTIVE'
            GROUP BY gm.GROUP_MEMBER_ID, u.DISPLAY_NAME, u.EMAIL, gm.JOINED_AT
            ORDER BY gm.JOINED_AT ASC
        """
        return self._fetch_all(sql, (group_id, group_id))

    def get_group_totals(self, group_id: str) -> dict:
        """Fetch aggregated group totals for contributions and expenses."""
        sql = """
            SELECT
                COALESCE(SUM(CASE WHEN ENTRY_TYPE = 'CREDIT' THEN AMOUNT_MINOR ELSE 0 END), 0) AS TOTAL_CONTRIBUTIONS_MINOR,
                COALESCE(SUM(CASE WHEN ENTRY_TYPE = 'DEBIT' THEN AMOUNT_MINOR ELSE 0 END), 0) AS TOTAL_EXPENSES_MINOR
            FROM LEDGER_ENTRIES
            WHERE GROUP_ID = ? AND STATUS = 'POSTED'
        """
        row = self._fetch_one(sql, (group_id,))
        if not row:
            return {"total_contributions_minor": 0, "total_expenses_minor": 0}
        return {
            "total_contributions_minor": row.get("TOTAL_CONTRIBUTIONS_MINOR", 0) or 0,
            "total_expenses_minor": row.get("TOTAL_EXPENSES_MINOR", 0) or 0,
        }


ledger_repo = LedgerRepository()
