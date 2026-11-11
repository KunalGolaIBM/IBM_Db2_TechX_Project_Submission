"""Double-entry ledger service."""

import logging
from typing import Optional

from db.repositories.ledger_repo import ledger_repo
from db.repositories.member_repo import member_repo
from api.middleware import AppError

logger = logging.getLogger(__name__)


class LedgerService:
    """Provides business logic for double-entry bookkeeping."""

    def _require_membership(self, group_id: str, user_id: str) -> dict:
        """Ensure requesting user is an active member of the group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")
        return member

    def record_entry(
        self,
        group_id: str,
        member_id: Optional[str],
        entity_type: str,
        entity_id: str,
        entry_type: str,
        amount_minor: int,
        currency: str = "INR",
    ) -> dict:
        """Record a single ledger entry."""
        if entry_type.upper() not in ("CREDIT", "DEBIT"):
            raise AppError(400, "Entry type must be CREDIT or DEBIT")
        if amount_minor <= 0:
            raise AppError(400, "Ledger entry amount must be positive")

        entry = ledger_repo.create_entry(
            group_id=group_id,
            member_id=member_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entry_type=entry_type.upper(),
            amount_minor=amount_minor,
            currency=currency,
        )
        logger.info(
            "Ledger entry posted: %s [%s %s] for member %s (%s paise)",
            entry.get("LEDGER_ENTRY_ID"),
            entry_type.upper(),
            entity_type,
            member_id,
            amount_minor,
        )
        return self._format_entry(entry)

    def get_entries(self, group_id: str, user_id: str, limit: int = 100) -> list[dict]:
        """Fetch ledger entries for a group."""
        self._require_membership(group_id, user_id)
        entries = ledger_repo.get_entries_by_group(group_id, limit)
        return [self._format_entry(e) for e in entries]

    def get_balances(self, group_id: str, user_id: str) -> list[dict]:
        """Fetch member net balances for a group."""
        self._require_membership(group_id, user_id)
        balances = ledger_repo.get_member_balances(group_id)
        return [
            {
                "member_id": b.get("MEMBER_ID"),
                "display_name": b.get("DISPLAY_NAME"),
                "email": b.get("EMAIL"),
                "total_credit_minor": int(b.get("TOTAL_CREDIT_MINOR", 0) or 0),
                "total_debit_minor": int(b.get("TOTAL_DEBIT_MINOR", 0) or 0),
                "net_balance_minor": int(b.get("NET_BALANCE_MINOR", 0) or 0),
            }
            for b in balances
        ]

    def get_totals(self, group_id: str, user_id: str) -> dict:
        """Fetch aggregated financial totals for a group."""
        self._require_membership(group_id, user_id)
        totals = ledger_repo.get_group_totals(group_id)
        return {
            "total_contributions_minor": int(totals.get("total_contributions_minor", 0) or 0),
            "total_expenses_minor": int(totals.get("total_expenses_minor", 0) or 0),
        }

    @staticmethod
    def _format_entry(entry: dict) -> dict:
        """Format raw DB entry to clean dictionary."""
        return {
            "ledger_entry_id": entry.get("LEDGER_ENTRY_ID"),
            "group_id": entry.get("GROUP_ID"),
            "member_id": entry.get("MEMBER_ID"),
            "entity_type": entry.get("ENTITY_TYPE"),
            "entity_id": entry.get("ENTITY_ID"),
            "entry_type": entry.get("ENTRY_TYPE"),
            "amount_minor": int(entry.get("AMOUNT_MINOR", 0) or 0),
            "currency": entry.get("CURRENCY", "INR"),
            "status": entry.get("STATUS"),
            "created_at": str(entry.get("CREATED_AT", "")),
            "display_name": entry.get("DISPLAY_NAME"),
            "email": entry.get("EMAIL"),
        }


ledger_service = LedgerService()
