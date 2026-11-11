import datetime
import uuid
from typing import Dict, FrozenSet, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, selectinload

from backend.app.ai.semantic.db2_vector_store import vector_store
from backend.app.api.deps import ensure_verified_staff, get_current_user, is_staff
from backend.app.core.audit import record_audit
from backend.app.database.base import get_db
from backend.app.models.entities import Incident, IncidentStatusHistory, LocationEvent, User
from backend.app.schemas.safety_schemas import (
    IncidentCreate, IncidentResponse, IncidentStatus, IncidentStatusHistoryItem, IncidentStatusUpdate,
    IncidentType, SimilarIncident,
)

router = APIRouter(prefix="/incidents", tags=["Incidents"])

# Incident types every resident can see (community-wide alerts). Everything else is private
# to the reporter and to verified staff.
PUBLIC_INCIDENT_TYPES = ("hazard", "suspicious_activity")
ACTIVE_STATUSES = ("reported", "acknowledged", "responder_en_route", "on_scene", "resolving")
CLOSED_STATUSES = ("resolved", "false_alarm")

# The incident lifecycle. Closed incidents are final; any open incident can be closed.
ALLOWED_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "reported": frozenset({"acknowledged", "responder_en_route", "resolved", "false_alarm"}),
    "acknowledged": frozenset({"responder_en_route", "on_scene", "resolving", "resolved", "false_alarm"}),
    "responder_en_route": frozenset({"on_scene", "resolving", "resolved", "false_alarm"}),
    "on_scene": frozenset({"resolving", "resolved", "false_alarm"}),
    "resolving": frozenset({"resolved", "false_alarm"}),
    "resolved": frozenset(),
    "false_alarm": frozenset(),
}


def incident_query(db: Session):
    """Incident query with its related rows loaded in a few batched SELECTs instead of one per incident."""
    return db.query(Incident).options(
        selectinload(Incident.reporter),
        selectinload(Incident.assigned_responder),
        selectinload(Incident.status_history).selectinload(IncidentStatusHistory.updated_by),
    )


def assign_reference_code(db: Session, incident: Incident, prefix: str) -> None:
    """Derive the public reference code from the Db2 identity value, so codes never collide."""
    incident.reference_code = f"TMP-{uuid.uuid4().hex[:24]}"
    db.add(incident)
    db.flush()
    incident.reference_code = f"{prefix}-{incident.created_at:%Y%m}-{incident.id:05d}"


def _format_incident_response(incident: Incident, viewer: Optional[User] = None) -> IncidentResponse:
    # Residents viewing someone else's public alert do not see who reported it or the exact coordinates.
    masked = viewer is not None and not is_staff(viewer) and incident.reporter_id != viewer.id

    history = [
        IncidentStatusHistoryItem(
            id=h.id,
            status=h.status,
            notes=h.notes,
            updated_by_name=None if masked else (h.updated_by.full_name if h.updated_by else "System"),
            created_at=h.created_at,
        )
        for h in sorted(incident.status_history, key=lambda h: (h.created_at, h.id))
    ]
    return IncidentResponse(
        id=incident.id,
        reference_code=incident.reference_code,
        reporter_id=incident.reporter_id,
        reporter_name=None if masked else (incident.reporter.full_name if incident.reporter else None),
        title=incident.title,
        description=incident.description,
        incident_type=incident.incident_type,
        priority=incident.priority,
        status=incident.status,
        location_address=incident.location_address,
        latitude=None if masked else incident.latitude,
        longitude=None if masked else incident.longitude,
        assigned_responder_id=incident.assigned_responder_id,
        assigned_responder_name=incident.assigned_responder.full_name if incident.assigned_responder else None,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        resolved_at=incident.resolved_at,
        status_history=history,
    )


def _get_visible_incident(db: Session, incident_id: int, user: User) -> Incident:
    incident = incident_query(db).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found.")
    if not is_staff(user) and incident.reporter_id != user.id and incident.incident_type not in PUBLIC_INCIDENT_TYPES:
        # 404 rather than 403, so private incident ids cannot be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found.")
    return incident


def _apply_status(db: Session, incident: Incident, new_status: str, user: User, notes: str, request: Optional[Request]) -> None:
    if new_status == incident.status:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Incident is already '{new_status}'.")
    allowed = ALLOWED_TRANSITIONS.get(incident.status, frozenset())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move an incident from '{incident.status}' to '{new_status}'. Allowed: {sorted(allowed) or 'none (closed)'}.",
        )

    now = datetime.datetime.utcnow()
    previous = incident.status
    incident.status = new_status
    incident.updated_at = now
    if new_status in CLOSED_STATUSES:
        incident.resolved_at = now
    db.add(IncidentStatusHistory(incident_id=incident.id, status=new_status, notes=notes, updated_by_id=user.id, created_at=now))
    record_audit(db, "incident_status_changed", "incident", incident.id, user_id=user.id, request=request,
                 details={"from": previous, "to": new_status})


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    req: IncidentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.datetime.utcnow()
    incident = Incident(
        reporter_id=current_user.id,
        title=req.title.strip(),
        description=req.description.strip(),
        incident_type=req.incident_type,
        priority=req.priority or "P2_HIGH",
        status="reported",
        location_address=req.location_address,
        latitude=req.latitude,
        longitude=req.longitude,
        created_at=now,
        updated_at=now,
    )
    assign_reference_code(db, incident, "INC")

    if req.latitude is not None and req.longitude is not None:
        db.add(LocationEvent(incident_id=incident.id, user_id=current_user.id, latitude=req.latitude,
                             longitude=req.longitude, event_type="incident_report_origin", timestamp=now))
    db.add(IncidentStatusHistory(incident_id=incident.id, status="reported", notes="Citizen incident report logged.",
                                 updated_by_id=current_user.id, created_at=now))
    record_audit(db, "incident_reported", "incident", incident.id, user_id=current_user.id, request=request,
                 details={"type": incident.incident_type, "priority": incident.priority})
    db.commit()  # incident, location, first history entry and audit row commit together

    vector_store.index_incident(incident.id, incident.title, incident.description)
    return _format_incident_response(_get_visible_incident(db, incident.id, current_user), current_user)


@router.get("", response_model=List[IncidentResponse])
def list_incidents(
    status_filter: Optional[IncidentStatus] = Query(None, alias="status"),
    type_filter: Optional[IncidentType] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = incident_query(db)
    if not is_staff(current_user):
        query = query.filter(
            (Incident.reporter_id == current_user.id) | (Incident.incident_type.in_(PUBLIC_INCIDENT_TYPES))
        )
    if status_filter:
        query = query.filter(Incident.status == status_filter)
    if type_filter:
        query = query.filter(Incident.incident_type == type_filter)

    incidents = query.order_by(Incident.created_at.desc(), Incident.id.desc()).offset(offset).limit(limit).all()
    return [_format_incident_response(inc, current_user) for inc in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _format_incident_response(_get_visible_incident(db, incident_id, current_user), current_user)


@router.get("/{incident_id}/similar", response_model=List[SimilarIncident])
def similar_incidents(
    incident_id: int,
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Related reports found by Db2 VECTOR_DISTANCE over incident embeddings (staff only).
    Empty when vector search is not active (non-Db2 modes)."""
    ensure_verified_staff(current_user)
    _get_visible_incident(db, incident_id, current_user)
    hits = vector_store.similar_incidents(incident_id, k=limit)
    if not hits:
        return []
    by_id = {i.id: i for i in db.query(Incident).filter(Incident.id.in_([int(h.key) for h in hits])).all()}
    return [
        SimilarIncident(
            id=inc.id, reference_code=inc.reference_code, title=inc.title, incident_type=inc.incident_type,
            priority=inc.priority, status=inc.status, location_address=inc.location_address,
            created_at=inc.created_at, similarity=round(1.0 - h.distance, 4),
        )
        for h in hits if (inc := by_id.get(int(h.key)))
    ]


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    incident_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_verified_staff(current_user)
    incident = _get_visible_incident(db, incident_id, current_user)
    if incident.assigned_responder_id not in (None, current_user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "This incident has already been claimed by another responder.")

    _apply_status(db, incident, "acknowledged", current_user,
                  f"Acknowledged by responder {current_user.full_name}. Preparing deployment.", request)
    incident.assigned_responder_id = current_user.id
    db.commit()
    return _format_incident_response(_get_visible_incident(db, incident_id, current_user), current_user)


@router.post("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: int,
    req: IncidentStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = _get_visible_incident(db, incident_id, current_user)

    if is_staff(current_user):
        ensure_verified_staff(current_user)
    else:
        # Residents may only close their own report (resolved, or cancelled as a false alarm).
        if incident.reporter_id != current_user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot update another user's incident.")
        if req.status not in CLOSED_STATUSES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Residents can only mark their incidents as resolved or false alarm.")

    notes = (req.notes or "").strip() or f"Status changed to {req.status.replace('_', ' ').title()}."
    _apply_status(db, incident, req.status, current_user, notes, request)
    if is_staff(current_user) and incident.assigned_responder_id is None:
        incident.assigned_responder_id = current_user.id
    db.commit()
    return _format_incident_response(_get_visible_incident(db, incident_id, current_user), current_user)
