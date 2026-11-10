from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..database import db_manager
from ..schemas.models import EventCreate

router = APIRouter(tags=["Security Events"])

@router.get("/events")
def list_events(
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    username: Optional[str] = None,
    severity: Optional[str] = None
):
    """Retrieves normalized security events stored in IBM Db2."""
    limit_val = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    offset_val = int(getattr(offset, "default", offset)) if not isinstance(offset, int) else offset
    events = db_manager.get_events(limit=limit_val, offset=offset_val, event_type=event_type, username=username, severity=severity)
    return {"count": len(events), "events": events}

@router.get("/events/{event_id}")
def get_event(event_id: int):
    """Retrieves a single security event by its unique ID."""
    event = db_manager.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found")
    return event

@router.post("/events", status_code=201)
def create_event(payload: EventCreate):
    """Ingests a new normalized security event into IBM Db2."""
    new_id = db_manager.insert_event(payload.dict())
    return {"message": "Security event recorded", "event_id": new_id}
