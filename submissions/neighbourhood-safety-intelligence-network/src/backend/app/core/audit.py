"""Append-only audit trail stored in the audit_events table."""
import datetime
import json
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.models.entities import AuditEvent


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host[:50]


def record_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[Any] = None,
    user_id: Optional[int] = None,
    request: Optional[Request] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Add an audit row to the current transaction. The caller's commit persists it
    together with the change it describes, so the audit trail cannot drift from the data."""
    db.add(AuditEvent(
        user_id=user_id,
        action=action[:100],
        resource_type=resource_type[:100],
        resource_id=None if resource_id is None else str(resource_id)[:100],
        ip_address=client_ip(request),
        details_json=json.dumps(details, default=str) if details else None,
        timestamp=datetime.datetime.utcnow(),
    ))
