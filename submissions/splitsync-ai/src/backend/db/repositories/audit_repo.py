"""Repository for AUDIT_EVENTS table operations."""

import json
import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    """Handles all Db2 operations for the AUDIT_EVENTS table."""

    table_name = "AUDIT_EVENTS"

    def log_event(
        self,
        event_type: str,
        group_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> str:
        """Record an audit event and return the event ID."""
        event_id = str(uuid.uuid4())
        details_json = json.dumps(details) if details else None
        sql = """
            INSERT INTO AUDIT_EVENTS
            (EVENT_ID, GROUP_ID, ACTOR_ID, EVENT_TYPE, ENTITY_TYPE, ENTITY_ID, DETAILS_JSON)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self._insert(sql, (event_id, group_id, actor_id, event_type, entity_type, entity_id, details_json))
        return event_id

    def get_by_group(self, group_id: str, limit: int = 50) -> list[dict]:
        """Fetch recent audit events for a group."""
        sql = """
            SELECT EVENT_ID, GROUP_ID, ACTOR_ID, EVENT_TYPE, ENTITY_TYPE, ENTITY_ID,
                   DETAILS_JSON, CREATED_AT
            FROM AUDIT_EVENTS
            WHERE GROUP_ID = ?
            ORDER BY CREATED_AT DESC
            FETCH FIRST ? ROWS ONLY
        """
        return self._fetch_all(sql, (group_id, limit))


audit_repo = AuditRepository()
