"""Audit service for recording application events."""

import logging
from typing import Optional

from db.repositories.audit_repo import audit_repo

logger = logging.getLogger(__name__)


class AuditService:
    """Centralized audit logging service."""

    def log(
        self,
        event_type: str,
        group_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> str:
        """Record an audit event."""
        try:
            event_id = audit_repo.log_event(
                event_type=event_type,
                group_id=group_id,
                actor_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
            logger.info("Audit event recorded: %s (type=%s)", event_id, event_type)
            return event_id
        except Exception as exc:
            logger.error("Failed to record audit event: %s", exc)
            return ""

    def get_group_events(self, group_id: str, limit: int = 50) -> list[dict]:
        """Retrieve audit events for a group."""
        return audit_repo.get_by_group(group_id, limit)


audit_service = AuditService()
