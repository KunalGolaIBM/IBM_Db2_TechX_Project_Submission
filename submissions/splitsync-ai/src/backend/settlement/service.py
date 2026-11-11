"""Settlement service managing debt calculation, run history, and transfer confirmations."""

import logging
from typing import Optional

from db.repositories.member_repo import member_repo
from db.repositories.ledger_repo import ledger_repo
from db.repositories.settlement_repo import settlement_repo
from settlement.engine import settlement_engine
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class SettlementService:
    """Coordinates debt simplification runs and status updates."""

    def _require_membership(self, group_id: str, user_id: str) -> dict:
        """Verify user is an active member of group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")
        return member

    def calculate_settlement(self, group_id: str, user_id: str) -> dict:
        """Calculate and persist an optimal settlement plan using minimum cash-flow graph algorithm."""
        self._require_membership(group_id, user_id)

        balances = ledger_repo.get_member_balances(group_id)
        balance_inputs = [
            {
                "member_id": b.get("MEMBER_ID"),
                "net_balance_minor": int(b.get("NET_BALANCE_MINOR", 0) or 0),
            }
            for b in balances
        ]

        calc_result = settlement_engine.calculate_transfers(balance_inputs)
        transfers = calc_result["transfers"]
        total_minor = calc_result["total_settled_minor"]

        run = settlement_repo.create_run(
            group_id=group_id,
            total_minor=total_minor,
            calculated_by=user_id,
            currency="INR",
        )
        run_id = run["RUN_ID"]

        if transfers:
            settlement_repo.create_items(run_id, transfers)

        audit_service.log(
            event_type="SETTLEMENT_CALCULATED",
            group_id=group_id,
            actor_id=user_id,
            entity_type="SETTLEMENT_RUN",
            entity_id=run_id,
            details={
                "total_minor": total_minor,
                "transfers_count": len(transfers),
            },
        )

        return self._format_run_with_items(run_id)

    def get_latest_settlement(self, group_id: str, user_id: str) -> Optional[dict]:
        """Fetch the most recent settlement run for a group."""
        self._require_membership(group_id, user_id)
        runs = settlement_repo.get_runs_by_group(group_id)
        if not runs:
            return None
        return self._format_run_with_items(runs[0]["RUN_ID"])

    def list_settlement_runs(self, group_id: str, user_id: str) -> list[dict]:
        """List historical settlement runs for a group."""
        self._require_membership(group_id, user_id)
        runs = settlement_repo.get_runs_by_group(group_id)
        return [self._format_run(r) for r in runs]

    def mark_item_settled(
        self,
        group_id: str,
        run_id: str,
        item_id: str,
        user_id: str,
        status: str = "SETTLED",
    ) -> dict:
        """Mark an individual recommended transfer item as settled or pending."""
        self._require_membership(group_id, user_id)
        run = settlement_repo.get_run_by_id(run_id)
        if not run or run.get("GROUP_ID") != group_id:
            raise AppError(404, "Settlement run not found")

        clean_status = status.strip().upper()
        settlement_repo.update_item_status(item_id, clean_status)

        audit_service.log(
            event_type="SETTLEMENT_ITEM_UPDATED",
            group_id=group_id,
            actor_id=user_id,
            entity_type="SETTLEMENT_ITEM",
            entity_id=item_id,
            details={"status": clean_status, "run_id": run_id},
        )

        return {
            "item_id": item_id,
            "run_id": run_id,
            "status": clean_status,
        }

    def _format_run_with_items(self, run_id: str) -> dict:
        """Fetch run and assemble its items with display names."""
        run = settlement_repo.get_run_by_id(run_id)
        if not run:
            raise AppError(404, "Settlement run not found")

        items = settlement_repo.get_items_by_run(run_id)
        formatted_items = [
            {
                "item_id": i.get("ITEM_ID"),
                "run_id": i.get("RUN_ID"),
                "from_member_id": i.get("FROM_MEMBER_ID"),
                "to_member_id": i.get("TO_MEMBER_ID"),
                "amount_minor": int(i.get("AMOUNT_MINOR", 0) or 0),
                "status": i.get("STATUS"),
                "from_name": i.get("FROM_NAME"),
                "from_email": i.get("FROM_EMAIL"),
                "to_name": i.get("TO_NAME"),
                "to_email": i.get("TO_EMAIL"),
            }
            for i in items
        ]

        formatted = self._format_run(run)
        formatted["items"] = formatted_items
        return formatted

    @staticmethod
    def _format_run(r: dict) -> dict:
        """Format raw DB settlement run dictionary."""
        return {
            "run_id": r.get("RUN_ID"),
            "group_id": r.get("GROUP_ID"),
            "total_minor": int(r.get("TOTAL_MINOR", 0) or 0),
            "currency": r.get("CURRENCY", "INR"),
            "status": r.get("STATUS"),
            "calculated_at": str(r.get("CALCULATED_AT", "")),
            "calculated_by": r.get("CALCULATED_BY"),
            "calculated_by_name": r.get("CALCULATED_BY_NAME"),
        }


settlement_service = SettlementService()
