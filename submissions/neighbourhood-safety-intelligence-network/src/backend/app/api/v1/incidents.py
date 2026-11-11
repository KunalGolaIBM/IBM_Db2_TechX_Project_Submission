import datetime
import random
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, Incident, IncidentStatusHistory, LocationEvent
from backend.app.schemas.safety_schemas import (
    IncidentCreate, IncidentResponse, IncidentStatusUpdate, IncidentStatusHistoryItem
)
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/incidents", tags=["Incidents"])

def _format_incident_response(incident: Incident) -> IncidentResponse:
    history_items = []
    for h in incident.status_history:
        history_items.append(IncidentStatusHistoryItem(
            id=h.id,
            status=h.status,
            notes=h.notes,
            updated_by_name=h.updated_by.full_name if h.updated_by else "System",
            created_at=h.created_at
        ))
    
    return IncidentResponse(
        id=incident.id,
        reference_code=incident.reference_code,
        reporter_id=incident.reporter_id,
        reporter_name=incident.reporter.full_name if incident.reporter else None,
        title=incident.title,
        description=incident.description,
        incident_type=incident.incident_type,
        priority=incident.priority,
        status=incident.status,
        location_address=incident.location_address,
        latitude=incident.latitude,
        longitude=incident.longitude,
        assigned_responder_id=incident.assigned_responder_id,
        assigned_responder_name=incident.assigned_responder.full_name if incident.assigned_responder else None,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        resolved_at=incident.resolved_at,
        status_history=history_items
    )

@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    req: IncidentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    ref_code = f"INC-{now.strftime('%Y%m')}-{random.randint(1000, 9999)}"

    incident = Incident(
        reference_code=ref_code,
        reporter_id=current_user.id,
        title=req.title,
        description=req.description,
        incident_type=req.incident_type,
        priority=req.priority or "P2_HIGH",
        status="reported",
        location_address=req.location_address,
        latitude=req.latitude,
        longitude=req.longitude,
        created_at=now,
        updated_at=now
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    if req.latitude is not None and req.longitude is not None:
        loc = LocationEvent(
            incident_id=incident.id,
            user_id=current_user.id,
            latitude=req.latitude,
            longitude=req.longitude,
            event_type="incident_report_origin",
            timestamp=now
        )
        db.add(loc)

    history = IncidentStatusHistory(
        incident_id=incident.id,
        status="reported",
        notes="Citizen incident report logged.",
        updated_by_id=current_user.id,
        created_at=now
    )
    db.add(history)
    db.commit()
    db.refresh(incident)

    return _format_incident_response(incident)

@router.get("", response_model=List[IncidentResponse])
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Incident)

    # RBAC filtering:
    # Responders and Admins see all incidents in their jurisdiction.
    # Residents see their own incidents + public community hazards/alerts.
    if current_user.role not in ["responder", "admin"]:
        query = query.filter(
            (Incident.reporter_id == current_user.id) |
            (Incident.incident_type.in_(["hazard", "suspicious_activity"]))
        )

    if status_filter:
        query = query.filter(Incident.status == status_filter)
    if type_filter:
        query = query.filter(Incident.incident_type == type_filter)

    incidents = query.order_by(Incident.created_at.desc()).all()
    return [_format_incident_response(inc) for inc in incidents]

@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    
    # Check access permission
    if current_user.role not in ["responder", "admin"] and incident.reporter_id != current_user.id:
        if incident.incident_type not in ["hazard", "suspicious_activity"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to private incident.")

    return _format_incident_response(incident)

@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    incident_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["responder", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only verified responders or admins can acknowledge incidents.")

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    now = datetime.datetime.utcnow()
    incident.status = "acknowledged"
    incident.assigned_responder_id = current_user.id
    incident.updated_at = now

    history = IncidentStatusHistory(
        incident_id=incident.id,
        status="acknowledged",
        notes=f"Acknowledged by responder {current_user.full_name}. Preparing deployment.",
        updated_by_id=current_user.id,
        created_at=now
    )
    db.add(history)
    db.commit()
    db.refresh(incident)

    return _format_incident_response(incident)

@router.post("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: int,
    req: IncidentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    valid_statuses = ["reported", "acknowledged", "responder_en_route", "on_scene", "resolving", "resolved", "false_alarm"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{req.status}'. Must be one of {valid_statuses}."
        )

    # Permission check:
    # A resident can only cancel their own reported incident (marking false_alarm or resolved if safe)
    if current_user.role not in ["responder", "admin"]:
        if incident.reporter_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another user's incident.")
        if req.status not in ["resolved", "false_alarm"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents can only mark incidents as resolved or false alarm.")

    now = datetime.datetime.utcnow()
    incident.status = req.status
    incident.updated_at = now
    if req.status in ["resolved", "false_alarm"]:
        incident.resolved_at = now

    history = IncidentStatusHistory(
        incident_id=incident.id,
        status=req.status,
        notes=req.notes or f"Status changed to {req.status.replace('_', ' ').title()}.",
        updated_by_id=current_user.id,
        created_at=now
    )
    db.add(history)
    db.commit()
    db.refresh(incident)

    return _format_incident_response(incident)
