"""Repository for PAYMENT_EVENTS table operations."""

from datetime import datetime
from typing import Optional

from db.repositories.base import BaseRepository


class PaymentRepository(BaseRepository):
    """Handles all Db2 operations for the PAYMENT_EVENTS table."""

    table_name = "PAYMENT_EVENTS"

    def create_payment(
        self,
        payment_id: str,
        group_id: str,
        member_id: Optional[str],
        provider: str,
        provider_txn_id: Optional[str],
        amount_minor: int,
        currency: str,
        status: str,
        source: str,
        idempotency_key: str,
        paid_at: Optional[datetime] = None,
    ) -> dict:
        """Insert a payment event record and return it."""
        sql = """
            INSERT INTO PAYMENT_EVENTS
            (PAYMENT_ID, GROUP_ID, MEMBER_ID, PROVIDER, PROVIDER_TXN_ID, AMOUNT_MINOR,
             CURRENCY, STATUS, SOURCE, IDEMPOTENCY_KEY, PAID_AT)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._insert(
            sql,
            (
                payment_id,
                group_id,
                member_id,
                provider,
                provider_txn_id,
                amount_minor,
                currency,
                status,
                source,
                idempotency_key,
                paid_at,
            ),
        )
        return self.get_by_id(payment_id) or {}

    def get_by_id(self, payment_id: str) -> Optional[dict]:
        """Fetch payment event by PAYMENT_ID."""
        sql = """
            SELECT p.PAYMENT_ID, p.GROUP_ID, p.MEMBER_ID, p.PROVIDER, p.PROVIDER_TXN_ID,
                   p.AMOUNT_MINOR, p.CURRENCY, p.STATUS, p.SOURCE, p.IDEMPOTENCY_KEY,
                   p.PAID_AT, p.CREATED_AT, u.DISPLAY_NAME, u.EMAIL
            FROM PAYMENT_EVENTS p
            LEFT JOIN GROUP_MEMBERS gm ON p.MEMBER_ID = gm.GROUP_MEMBER_ID
            LEFT JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE p.PAYMENT_ID = ?
        """
        return self._fetch_one(sql, (payment_id,))

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[dict]:
        """Fetch payment event by IDEMPOTENCY_KEY."""
        sql = """
            SELECT PAYMENT_ID, GROUP_ID, MEMBER_ID, PROVIDER, PROVIDER_TXN_ID,
                   AMOUNT_MINOR, CURRENCY, STATUS, SOURCE, IDEMPOTENCY_KEY,
                   PAID_AT, CREATED_AT
            FROM PAYMENT_EVENTS
            WHERE IDEMPOTENCY_KEY = ?
        """
        return self._fetch_one(sql, (idempotency_key,))

    def get_by_group(self, group_id: str, limit: int = 50) -> list[dict]:
        """Fetch payment events for a group."""
        sql = """
            SELECT p.PAYMENT_ID, p.GROUP_ID, p.MEMBER_ID, p.PROVIDER, p.PROVIDER_TXN_ID,
                   p.AMOUNT_MINOR, p.CURRENCY, p.STATUS, p.SOURCE, p.IDEMPOTENCY_KEY,
                   p.PAID_AT, p.CREATED_AT, u.DISPLAY_NAME, u.EMAIL
            FROM PAYMENT_EVENTS p
            LEFT JOIN GROUP_MEMBERS gm ON p.MEMBER_ID = gm.GROUP_MEMBER_ID
            LEFT JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE p.GROUP_ID = ?
            ORDER BY p.CREATED_AT DESC
            FETCH FIRST ? ROWS ONLY
        """
        return self._fetch_all(sql, (group_id, limit))

    def update_status(self, payment_id: str, status: str) -> None:
        """Update payment event status."""
        sql = "UPDATE PAYMENT_EVENTS SET STATUS = ? WHERE PAYMENT_ID = ?"
        self._update(sql, (status, payment_id))


payment_repo = PaymentRepository()
