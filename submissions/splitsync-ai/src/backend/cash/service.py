"""Cash contribution service."""

import logging
from typing import Optional

from db.repositories.cash_repo import cash_repo
from db.repositories.member_repo import member_repo
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class CashService:
    """Handles submission and retrieval of cash contributions."""

    def _require_membership(self, group_id: str, user_id: str) -> dict:
        """Verify requesting user is an active member of group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")
        return member

    def submit_cash(
        self,
        group_id: str,
        user_id: str,
        amount_minor: int,
        description: Optional[str] = None,
    ) -> dict:
        """Submit a cash contribution requiring dual-control peer approval."""
        member = self._require_membership(group_id, user_id)
        if amount_minor <= 0:
            raise AppError(400, "Cash contribution amount must be greater than zero")

        contribution = cash_repo.create_cash_contribution(
            group_id=group_id,
            member_id=member["GROUP_MEMBER_ID"],
            amount_minor=amount_minor,
            description=description,
        )

        audit_service.log(
            event_type="CASH_SUBMITTED",
            group_id=group_id,
            actor_id=user_id,
            entity_type="CASH_CONTRIBUTION",
            entity_id=contribution.get("CASH_CONTRIBUTION_ID"),
            details={
                "amount_minor": amount_minor,
                "description": description,
                "status": "PENDING_APPROVAL",
            },
        )
        return self._format_cash(contribution)

    def list_cash(
        self, group_id: str, user_id: str, status: Optional[str] = None
    ) -> list[dict]:
        """List all cash contributions for a group."""
        self._require_membership(group_id, user_id)
        contributions = cash_repo.get_by_group(group_id, status)
        return [self._format_cash(c) for c in contributions]

    @staticmethod
    def _format_cash(c: dict) -> dict:
        """Format raw DB cash contribution into API response dictionary."""
        return {
            "cash_contribution_id": c.get("CASH_CONTRIBUTION_ID"),
            "group_id": c.get("GROUP_ID"),
            "member_id": c.get("MEMBER_ID"),
            "amount_minor": int(c.get("AMOUNT_MINOR", 0) or 0),
            "description": c.get("DESCRIPTION"),
            "status": c.get("STATUS"),
            "created_at": str(c.get("CREATED_AT", "")),
            "display_name": c.get("DISPLAY_NAME"),
            "email": c.get("EMAIL"),
        }


cash_service = CashService()
