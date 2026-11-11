import datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.app.ai.semantic.db2_vector_store import vector_store
from backend.app.api.deps import get_current_user
from backend.app.api.v1.incidents import _format_incident_response, _get_visible_incident, assign_reference_code
from backend.app.core.audit import record_audit
from backend.app.database.base import get_db
from backend.app.models.entities import (
    Incident, IncidentStatusHistory, LocationEvent, Responder, TrustedContact, User,
)
from backend.app.schemas.safety_schemas import IncidentResponse, SOSCreate

router = APIRouter(prefix="/sos", tags=["Emergency SOS"])


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def trigger_sos(
    req: SOSCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a P1_CRITICAL incident, its GPS location event, the first status entry and an
    audit row in a single transaction, and record who the alert reaches."""
    now = datetime.datetime.utcnow()

    description = (req.description or "").strip() or f"EMERGENCY SOS triggered by {current_user.full_name}."
    if current_user.emergency_notes:
        description += f" [Medical Notes: {current_user.emergency_notes}]"

    incident = Incident(
        reporter_id=current_user.id,
        title=f"EMERGENCY SOS - {current_user.full_name}",
        description=description[:4000],
        incident_type="sos",
        priority="P1_CRITICAL",
        status="reported",
        location_address=req.location_address or "Current Device GPS Coordinates",
        latitude=req.latitude,
        longitude=req.longitude,
        created_at=now,
        updated_at=now,
    )
    assign_reference_code(db, incident, "SOS")

    if req.latitude is not None and req.longitude is not None:
        db.add(LocationEvent(incident_id=incident.id, user_id=current_user.id, latitude=req.latitude,
                             longitude=req.longitude, event_type="sos_trigger_point", timestamp=now))

    # Boolean filters use "== True" (rendered as "= 1" on Db2); ".is_(True)" renders "IS 1", which Db2 rejects.
    contacts = db.query(TrustedContact).filter(
        TrustedContact.user_id == current_user.id, TrustedContact.can_receive_sos == True,  # noqa: E712
    ).count()
    on_duty = db.query(Responder).join(User, Responder.user_id == User.id).filter(
        Responder.is_available == True, User.is_verified == True, User.is_active == True,  # noqa: E712
    ).count()

    db.add(IncidentStatusHistory(
        incident_id=incident.id,
        status="reported",
        notes=(f"SOS ({req.emergency_type}) raised. Alert routed to {contacts} trusted contact(s) "
               f"and {on_duty} on-duty verified responder(s)."),
        updated_by_id=current_user.id,
        created_at=now,
    ))
    record_audit(db, "sos_triggered", "incident", incident.id, user_id=current_user.id, request=request,
                 details={"emergency_type": req.emergency_type, "contacts": contacts, "on_duty_responders": on_duty,
                          "has_gps": req.latitude is not None})
    db.commit()

    vector_store.index_incident(incident.id, incident.title, incident.description)
    return _format_incident_response(_get_visible_incident(db, incident.id, current_user), current_user)
