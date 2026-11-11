"""Expense service managing expense creation, equal splits, and ledger postings."""

import logging
from typing import Optional

from db.repositories.expense_repo import expense_repo
from db.repositories.member_repo import member_repo
from ledger.service import ledger_service
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class ExpenseService:
    """Handles expense tracking, split allocations, and ledger entries."""

    def _require_membership(self, group_id: str, user_id: str) -> dict:
        """Verify user is an active member of group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")
        return member

    def create_expense(
        self,
        group_id: str,
        user_id: str,
        amount_minor: int,
        description: str,
        category: str = "OTHER",
        payment_method: str = "DIGITAL",
        participant_member_ids: Optional[list[str]] = None,
        expense_date: Optional[str] = None,
    ) -> dict:
        """Create a new expense with exact integer paise splits and ledger journal posting."""
        payer = self._require_membership(group_id, user_id)
        payer_member_id = payer["GROUP_MEMBER_ID"]

        if amount_minor <= 0:
            raise AppError(400, "Expense amount must be greater than zero")
        if not description or not description.strip():
            raise AppError(400, "Expense description is required")

        # Resolve participants: if not provided or empty, default to all active group members
        if not participant_member_ids:
            all_members = member_repo.get_members_of_group(group_id)
            participant_member_ids = [m["GROUP_MEMBER_ID"] for m in all_members]

        if not participant_member_ids:
            raise AppError(400, "Expense must have at least one participant")

        # Calculate exact integer paise equal split with remainder preservation
        num_participants = len(participant_member_ids)
        base_share = amount_minor // num_participants
        remainder = amount_minor % num_participants

        splits = []
        for idx, mid in enumerate(participant_member_ids):
            share = base_share + (remainder if idx == 0 else 0)
            splits.append({"member_id": mid, "share_minor": share})

        method_upper = payment_method.strip().upper()
        status = "PENDING_APPROVAL" if method_upper == "CASH" else "VERIFIED"

        expense = expense_repo.create_expense(
            group_id=group_id,
            paid_by_member_id=payer_member_id,
            amount_minor=amount_minor,
            description=description.strip(),
            category=category.strip().upper() if category else "OTHER",
            payment_method=method_upper,
            status=status,
            expense_date=expense_date,
        )

        expense_id = expense["EXPENSE_ID"]
        expense_repo.create_splits(expense_id, splits)

        # Post ledger entries immediately if verified (digital payment)
        if status == "VERIFIED":
            # Credit the payer for the full expense amount
            ledger_service.record_entry(
                group_id=group_id,
                member_id=payer_member_id,
                entity_type="EXPENSE",
                entity_id=expense_id,
                entry_type="CREDIT",
                amount_minor=amount_minor,
            )
            # Debit each participant for their exact allocated share
            persisted_splits = expense_repo.get_splits(expense_id)
            for s in persisted_splits:
                ledger_service.record_entry(
                    group_id=group_id,
                    member_id=s["MEMBER_ID"],
                    entity_type="EXPENSE_SPLIT",
                    entity_id=s["SPLIT_ID"],
                    entry_type="DEBIT",
                    amount_minor=int(s["SHARE_MINOR"]),
                )

        audit_service.log(
            event_type="EXPENSE_CREATED",
            group_id=group_id,
            actor_id=user_id,
            entity_type="EXPENSE",
            entity_id=expense_id,
            details={
                "amount_minor": amount_minor,
                "description": description,
                "category": category,
                "payment_method": method_upper,
                "status": status,
                "participant_count": num_participants,
            },
        )

        return self.get_expense_details(group_id, expense_id, user_id)

    def list_expenses(self, group_id: str, user_id: str) -> list[dict]:
        """Fetch all expenses recorded for a group."""
        self._require_membership(group_id, user_id)
        expenses = expense_repo.get_by_group(group_id)
        return [self._format_expense(e) for e in expenses]

    def get_expense_details(self, group_id: str, expense_id: str, user_id: str) -> dict:
        """Fetch full details and splits for a single expense."""
        self._require_membership(group_id, user_id)
        expense = expense_repo.get_by_id(expense_id)
        if not expense or expense.get("GROUP_ID") != group_id:
            raise AppError(404, "Expense not found")

        splits = expense_repo.get_splits(expense_id)
        formatted_splits = [
            {
                "split_id": s.get("SPLIT_ID"),
                "member_id": s.get("MEMBER_ID"),
                "share_minor": int(s.get("SHARE_MINOR", 0) or 0),
                "display_name": s.get("DISPLAY_NAME"),
                "email": s.get("EMAIL"),
            }
            for s in splits
        ]

        result = self._format_expense(expense)
        result["splits"] = formatted_splits
        return result

    @staticmethod
    def _format_expense(e: dict) -> dict:
        """Format raw DB expense into clean dictionary response."""
        return {
            "expense_id": e.get("EXPENSE_ID"),
            "group_id": e.get("GROUP_ID"),
            "paid_by_member_id": e.get("PAID_BY_MEMBER_ID"),
            "amount_minor": int(e.get("AMOUNT_MINOR", 0) or 0),
            "description": e.get("DESCRIPTION"),
            "category": e.get("CATEGORY"),
            "payment_method": e.get("PAYMENT_METHOD"),
            "status": e.get("STATUS"),
            "expense_date": str(e.get("EXPENSE_DATE", "")) if e.get("EXPENSE_DATE") else None,
            "created_at": str(e.get("CREATED_AT", "")),
            "payer_name": e.get("PAYER_NAME"),
            "payer_email": e.get("PAYER_EMAIL"),
        }


expense_service = ExpenseService()
