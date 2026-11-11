import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from . import db

ZERO_HASH = "0" * 64


def record_event(conn, entity_type: str, entity_id: str, event_type: str, actor_id: str,
                 event_data: dict[str, Any]) -> None:
    head = db.row("SELECT LAST_HASH FROM AUDIT_HEAD WHERE HEAD_ID = 1 FOR UPDATE", conn=conn)
    previous_hash = head["last_hash"].strip() if head else ZERO_HASH
    created = datetime.now(timezone.utc).isoformat()
    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "created_at": created,
        "data": event_data,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(f"{previous_hash}:{canonical}".encode("utf-8")).hexdigest()
    db.execute(
        """INSERT INTO AUDIT_EVENTS
           (ENTITY_TYPE,ENTITY_ID,EVENT_TYPE,ACTOR_ID,EVENT_DATA,PREVIOUS_HASH,EVENT_HASH)
           VALUES (?,?,?,?,?,?,?)""",
        (entity_type, entity_id, event_type, actor_id, canonical, previous_hash, digest), conn,
    )
    db.execute("UPDATE AUDIT_HEAD SET LAST_HASH=? WHERE HEAD_ID=1", (digest,), conn)


def verify_chain() -> dict[str, Any]:
    events = db.rows("SELECT EVENT_ID,PREVIOUS_HASH,EVENT_HASH,EVENT_DATA FROM AUDIT_EVENTS ORDER BY EVENT_ID")
    previous = ZERO_HASH
    for event in events:
        stored_prev = event["previous_hash"].strip()
        if stored_prev != previous:
            return {"valid": False, "checked_events": len(events), "broken_event_id": event["event_id"]}
        expected = hashlib.sha256(f"{previous}:{event['event_data']}".encode("utf-8")).hexdigest()
        if not hmac_compare(expected, event["event_hash"].strip()):
            return {"valid": False, "checked_events": len(events), "broken_event_id": event["event_id"]}
        previous = event["event_hash"].strip()
    head = db.row("SELECT LAST_HASH FROM AUDIT_HEAD WHERE HEAD_ID=1")
    valid = (head["last_hash"].strip() if head else ZERO_HASH) == previous
    return {"valid": valid, "checked_events": len(events), "broken_event_id": None if valid else "head"}


def hmac_compare(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(left, right)
