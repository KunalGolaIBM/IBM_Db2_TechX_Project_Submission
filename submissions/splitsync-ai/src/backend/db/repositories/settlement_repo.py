"""Repository for SETTLEMENT_RUNS and SETTLEMENT_ITEMS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class SettlementRepository(BaseRepository):
    """Handles all Db2 operations for SETTLEMENT_RUNS and SETTLEMENT_ITEMS."""

    table_name = "SETTLEMENT_RUNS"

    def create_run(
        self,
        group_id: str,
        total_minor: int,
        calculated_by: str,
        currency: str = "INR",
    ) -> dict:
        """Insert a new settlement run header."""
        run_id = str(uuid.uuid4())
        sql = """
            INSERT INTO SETTLEMENT_RUNS
            (RUN_ID, GROUP_ID, TOTAL_MINOR, CURRENCY, STATUS, CALCULATED_BY)
            VALUES (?, ?, ?, ?, 'CALCULATED', ?)
        """
        self._insert(sql, (run_id, group_id, total_minor, currency, calculated_by))
        return self.get_run_by_id(run_id) or {}

    def create_items(self, run_id: str, items: list[dict]) -> None:
        """Batch-insert recommended settlement item transfers."""
        operations = []
        for item in items:
            item_id = str(uuid.uuid4())
            sql = """
                INSERT INTO SETTLEMENT_ITEMS
                (ITEM_ID, RUN_ID, FROM_MEMBER_ID, TO_MEMBER_ID, AMOUNT_MINOR, STATUS)
                VALUES (?, ?, ?, ?, ?, 'RECOMMENDED')
            """
            operations.append(
                (
                    sql,
                    (
                        item_id,
                        run_id,
                        item["from_member_id"],
                        item["to_member_id"],
                        item["amount_minor"],
                    ),
                )
            )
        self._execute_in_transaction(operations)

    def get_runs_by_group(self, group_id: str) -> list[dict]:
        """Fetch all settlement runs for a group sorted by newest first."""
        sql = """
            SELECT sr.RUN_ID, sr.GROUP_ID, sr.TOTAL_MINOR, sr.CURRENCY, sr.STATUS,
                   sr.CALCULATED_AT, sr.CALCULATED_BY, u.DISPLAY_NAME AS CALCULATED_BY_NAME
            FROM SETTLEMENT_RUNS sr
            INNER JOIN APP_USERS u ON sr.CALCULATED_BY = u.USER_ID
            WHERE sr.GROUP_ID = ?
            ORDER BY sr.CALCULATED_AT DESC
        """
        return self._fetch_all(sql, (group_id,))

    def get_run_by_id(self, run_id: str) -> Optional[dict]:
        """Fetch a single settlement run header by RUN_ID."""
        sql = """
            SELECT sr.RUN_ID, sr.GROUP_ID, sr.TOTAL_MINOR, sr.CURRENCY, sr.STATUS,
                   sr.CALCULATED_AT, sr.CALCULATED_BY, u.DISPLAY_NAME AS CALCULATED_BY_NAME
            FROM SETTLEMENT_RUNS sr
            INNER JOIN APP_USERS u ON sr.CALCULATED_BY = u.USER_ID
            WHERE sr.RUN_ID = ?
        """
        return self._fetch_one(sql, (run_id,))

    def get_items_by_run(self, run_id: str) -> list[dict]:
        """Fetch all recommended transfers for a settlement run with member names."""
        sql = """
            SELECT si.ITEM_ID, si.RUN_ID, si.FROM_MEMBER_ID, si.TO_MEMBER_ID,
                   si.AMOUNT_MINOR, si.STATUS,
                   u_from.DISPLAY_NAME AS FROM_NAME, u_from.EMAIL AS FROM_EMAIL,
                   u_to.DISPLAY_NAME AS TO_NAME, u_to.EMAIL AS TO_EMAIL
            FROM SETTLEMENT_ITEMS si
            INNER JOIN GROUP_MEMBERS gm_from ON si.FROM_MEMBER_ID = gm_from.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u_from ON gm_from.USER_ID = u_from.USER_ID
            INNER JOIN GROUP_MEMBERS gm_to ON si.TO_MEMBER_ID = gm_to.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u_to ON gm_to.USER_ID = u_to.USER_ID
            WHERE si.RUN_ID = ?
            ORDER BY si.AMOUNT_MINOR DESC
        """
        return self._fetch_all(sql, (run_id,))

    def update_item_status(self, item_id: str, status: str) -> None:
        """Update settlement item status (e.g. SETTLED)."""
        sql = "UPDATE SETTLEMENT_ITEMS SET STATUS = ? WHERE ITEM_ID = ?"
        self._update(sql, (status, item_id))


settlement_repo = SettlementRepository()
