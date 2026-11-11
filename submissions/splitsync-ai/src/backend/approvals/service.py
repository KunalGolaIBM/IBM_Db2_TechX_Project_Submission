"""Cash and expense approval service implementing peer verification."""

import logging
from typing import Optional

from db.repositories.approval_repo import approval_repo
from db.repositories.cash_repo import cash_repo
from db.repositories.expense_repo import expense_repo
from db.repositories.member_repo import member_repo
from ledger.service import ledger_service
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class ApprovalService:
    """Handles dual-control approval workflows for cash transactions."""

    def _require_membership(self, group_id: str, user_id: str) -> dict:
        """Verify user is an active member of group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")
        return member

    def get_pending(self, group_id: str, user_id: str) -> list[dict]:
        """Fetch all pending cash contributions and cash expenses requiring approval."""
        self._require_membership(group_id, user_id)
        items = approval_repo.get_pending_approvals(group_id)
        return [
            {
                "entity_type": item.get("ENTITY_TYPE"),
                "entity_id": item.get("ENTITY_ID"),
                "group_id": item.get("GROUP_ID"),
                "submitter_member_id": item.get("SUBMITTER_MEMBER_ID"),
                "submitter_name": item.get("SUBMITTER_NAME"),
                "amount_minor": int(item.get("AMOUNT_MINOR", 0) or 0),
                "description": item.get("DESCRIPTION"),
                "status": item.get("STATUS"),
                "created_at": str(item.get("CREATED_AT", "")),
            }
            for item in items
        ]

    def decide(
        self,
        group_id: str,
        user_id: str,
        entity_type: str,
        entity_id: str,
        decision: str,
        comment: Optional[str] = None,
    ) -> dict:
        """Record an approval or rejection decision with segregation of duties."""
        approver = self._require_membership(group_id, user_id)
        approver_member_id = approver["GROUP_MEMBER_ID"]

        clean_decision = decision.strip().upper()
        if clean_decision not in ("APPROVED", "REJECTED"):
            raise AppError(400, "Decision must be APPROVED or REJECTED")

        clean_type = entity_type.strip().upper()
        if clean_type == "CASH_CONTRIBUTION":
            item = cash_repo.get_by_id(entity_id)
            if not item or item.get("GROUP_ID") != group_id:
                raise AppError(404, "Cash contribution not found")
            if item.get("STATUS") != "PENDING_APPROVAL":
                raise AppError(400, f"Item is already {item.get('STATUS')}")

            submitter_member_id = item["MEMBER_ID"]
            if approver_member_id == submitter_member_id:
                raise AppError(403, "You cannot approve your own submission")

            if clean_decision == "APPROVED":
                cash_repo.update_status(entity_id, "APPROVED")
                ledger_service.record_entry(
                    group_id=group_id,
                    member_id=submitter_member_id,
                    entity_type="CASH_CONTRIBUTION",
                    entity_id=entity_id,
                    entry_type="CREDIT",
                    amount_minor=int(item["AMOUNT_MINOR"]),
                )
            else:
                cash_repo.update_status(entity_id, "REJECTED")

        elif clean_type == "EXPENSE":
            expense = expense_repo.get_by_id(entity_id)
            if not expense or expense.get("GROUP_ID") != group_id:
                raise AppError(404, "Expense not found")
            if expense.get("STATUS") != "PENDING_APPROVAL":
                raise AppError(400, f"Expense is already {expense.get('STATUS')}")

            submitter_member_id = expense["PAID_BY_MEMBER_ID"]
            if approver_member_id == submitter_member_id:
                raise AppError(403, "You cannot approve your own submission")

            if clean_decision == "APPROVED":
                expense_repo.update_status(entity_id, "VERIFIED")
                # Credit the payer
                ledger_service.record_entry(
                    group_id=group_id,
                    member_id=submitter_member_id,
                    entity_type="EXPENSE",
                    entity_id=entity_id,
                    entry_type="CREDIT",
                    amount_minor=int(expense["AMOUNT_MINOR"]),
                )
                # Debit each participant
                splits = expense_repo.get_splits(entity_id)
                for s in splits:
                    ledger_service.record_entry(
                        group_id=group_id,
                        member_id=s["MEMBER_ID"],
                        entity_type="EXPENSE_SPLIT",
                        entity_id=s["SPLIT_ID"],
                        entry_type="DEBIT",
                        amount_minor=int(s["SHARE_MINOR"]),
                    )
            else:
                expense_repo.update_status(entity_id, "REJECTED")

        else:
            raise AppError(400, f"Unsupported entity type: {entity_type}")

        approval = approval_repo.record_approval(
            entity_type=clean_type,
            entity_id=entity_id,
            approver_member_id=approver_member_id,
            decision=clean_decision,
            comment=comment,
        )

        audit_service.log(
            event_type="APPROVAL_DECIDED",
            group_id=group_id,
            actor_id=user_id,
            entity_type=clean_type,
            entity_id=entity_id,
            details={
                "decision": clean_decision,
                "approver_member_id": approver_member_id,
                "comment": comment,
            },
        )

        return {
            "approval_id": approval.get("APPROVAL_ID"),
            "entity_type": clean_type,
            "entity_id": entity_id,
            "decision": clean_decision,
            "comment": comment,
            "decided_at": str(approval.get("DECIDED_AT", "")),
        }


approval_service = ApprovalService()
