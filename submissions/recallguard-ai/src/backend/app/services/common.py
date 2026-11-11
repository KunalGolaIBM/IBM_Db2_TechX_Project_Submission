"""Shared helpers: identifiers, timestamps, audit trail, JSON columns."""
from __future__ import annotations

import datetime as dt
import json
import secrets
from typing import Any

from app.database import Database


class NotFound(LookupError):
    pass


class InvalidState(ValueError):
    pass


def now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


def ts(value: dt.datetime | None = None) -> str:
    """Timestamp literal accepted by both IBM Db2 and the dev engine."""
    return (value or now()).strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}-{now().year}-{secrets.token_hex(3).upper()}"


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def loads(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return default


def audit(db: Database, actor: str, role: str, action: str, entity_kind: str, entity_ref: str, details: Any = None) -> str:
    """Append-only audit log entry (every state change goes through here)."""
    aid = f"AUD-{secrets.token_hex(6).upper()}"
    text = details if isinstance(details, str) or details is None else dumps(details)
    db.execute(
        "INSERT INTO audit_logs (audit_id, occurred_at, actor, actor_role, action_name, entity_kind, entity_ref, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (aid, dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), actor[:80], role[:30], action[:60], entity_kind[:30], entity_ref[:40], (text or "")[:4000]),
    )
    return aid
