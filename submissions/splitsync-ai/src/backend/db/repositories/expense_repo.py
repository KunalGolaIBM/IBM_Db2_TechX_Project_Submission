"""Repository for EXPENSES and EXPENSE_SPLITS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class ExpenseRepository(BaseRepository):
    """Handles all Db2 operations for EXPENSES and EXPENSE_SPLITS tables."""

    table_name = "EXPENSES"

    def create_expense(
        self,
        group_id: str,
        paid_by_member_id: str,
        amount_minor: int,
        description: str,
        category: str = "OTHER",
        payment_method: str = "DIGITAL",
        status: str = "VERIFIED",
        expense_date: Optional[str] = None,
    ) -> dict:
        """Create an expense record."""
        expense_id = str(uuid.uuid4())
        sql = """
            INSERT INTO EXPENSES
            (EXPENSE_ID, GROUP_ID, PAID_BY_MEMBER_ID, AMOUNT_MINOR, DESCRIPTION,
             CATEGORY, PAYMENT_METHOD, STATUS, EXPENSE_DATE)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._insert(
            sql,
            (
                expense_id,
                group_id,
                paid_by_member_id,
                amount_minor,
                description,
                category,
                payment_method,
                status,
                expense_date,
            ),
        )
        return self.get_by_id(expense_id) or {}

    def create_splits(self, expense_id: str, splits: list[dict]) -> None:
        """Batch-insert expense split allocations."""
        operations = []
        for s in splits:
            split_id = str(uuid.uuid4())
            member_id = s["member_id"]
            share_minor = s["share_minor"]
            sql = """
                INSERT INTO EXPENSE_SPLITS (SPLIT_ID, EXPENSE_ID, MEMBER_ID, SHARE_MINOR)
                VALUES (?, ?, ?, ?)
            """
            operations.append((sql, (split_id, expense_id, member_id, share_minor)))
        self._execute_in_transaction(operations)

    def get_by_id(self, expense_id: str) -> Optional[dict]:
        """Fetch expense by ID with payer information."""
        sql = """
            SELECT e.EXPENSE_ID, e.GROUP_ID, e.PAID_BY_MEMBER_ID, e.AMOUNT_MINOR,
                   e.DESCRIPTION, e.CATEGORY, e.PAYMENT_METHOD, e.STATUS,
                   e.EXPENSE_DATE, e.CREATED_AT, u.DISPLAY_NAME AS PAYER_NAME, u.EMAIL AS PAYER_EMAIL
            FROM EXPENSES e
            INNER JOIN GROUP_MEMBERS gm ON e.PAID_BY_MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE e.EXPENSE_ID = ?
        """
        return self._fetch_one(sql, (expense_id,))

    def get_by_group(self, group_id: str) -> list[dict]:
        """Fetch all expenses for a group sorted by newest first."""
        sql = """
            SELECT e.EXPENSE_ID, e.GROUP_ID, e.PAID_BY_MEMBER_ID, e.AMOUNT_MINOR,
                   e.DESCRIPTION, e.CATEGORY, e.PAYMENT_METHOD, e.STATUS,
                   e.EXPENSE_DATE, e.CREATED_AT, u.DISPLAY_NAME AS PAYER_NAME, u.EMAIL AS PAYER_EMAIL
            FROM EXPENSES e
            INNER JOIN GROUP_MEMBERS gm ON e.PAID_BY_MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE e.GROUP_ID = ?
            ORDER BY e.CREATED_AT DESC
        """
        return self._fetch_all(sql, (group_id,))

    def get_splits(self, expense_id: str) -> list[dict]:
        """Fetch all member split allocations for an expense."""
        sql = """
            SELECT es.SPLIT_ID, es.EXPENSE_ID, es.MEMBER_ID, es.SHARE_MINOR,
                   u.DISPLAY_NAME, u.EMAIL
            FROM EXPENSE_SPLITS es
            INNER JOIN GROUP_MEMBERS gm ON es.MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE es.EXPENSE_ID = ?
        """
        return self._fetch_all(sql, (expense_id,))

    def update_status(self, expense_id: str, status: str) -> None:
        """Update expense approval status."""
        sql = "UPDATE EXPENSES SET STATUS = ? WHERE EXPENSE_ID = ?"
        self._update(sql, (status, expense_id))


expense_repo = ExpenseRepository()
