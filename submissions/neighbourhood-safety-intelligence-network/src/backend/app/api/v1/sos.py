import datetime
import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, Incident, IncidentStatusHistory, LocationEvent
from backend.app.schemas.safety_schemas import SOSCreate, IncidentResponse, IncidentStatusHistoryItem
from backend.app.api.deps import get_current_user
from backend.app.ai.crewai.agents import crew_orchestrator

router = APIRouter(prefix="/sos", tags=["Emergency SOS"])

@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def trigger_sos(
    req: SOSCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    ref_code = f"SOS-{now.strftime('%Y%m')}-{random.randint(1000, 9999)}"

    description_text = req.description or f"EMERGENCY SOS triggered by {current_user.full_name}."
    if current_user.emergency_notes:
        description_text += f" [Medical Notes: {current_user.emergency_notes}]"

    incident = Incident(
        reference_code=ref_code,
        reporter_id=current_user.id,
        title=f"🚨 EMERGENCY SOS - {current_user.full_name}",
        description=description_text,
        incident_type="sos",
        priority="P1_CRITICAL",
        status="reported",
        location_address=req.location_address or "Current Device GPS Coordinates",
        latitude=req.latitude,
        longitude=req.longitude,
        created_at=now,
        updated_at=now
    )
    db.add(incident)
    db.flush()  # assign incident.id; incident, location and history commit together below

    # Record location event if coordinates present
    if req.latitude is not None and req.longitude is not None:
        loc_event = LocationEvent(
            incident_id=incident.id,
            user_id=current_user.id,
            latitude=req.latitude,
            longitude=req.longitude,
            event_type="sos_trigger_point",
            timestamp=now
        )
        db.add(loc_event)

    # Initial status log
    status_entry = IncidentStatusHistory(
        incident_id=incident.id,
        status="reported",
        notes=f"Emergency distress broadcast sent to nearby responders and trusted contacts.",
        updated_by_id=current_user.id,
        created_at=now
    )
    db.add(status_entry)
    db.commit()
    db.refresh(incident)

    return IncidentResponse(
        id=incident.id,
        reference_code=incident.reference_code,
        reporter_id=incident.reporter_id,
        reporter_name=current_user.full_name,
        title=incident.title,
        description=incident.description,
        incident_type=incident.incident_type,
        priority=incident.priority,
        status=incident.status,
        location_address=incident.location_address,
        latitude=incident.latitude,
        longitude=incident.longitude,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        status_history=[
            IncidentStatusHistoryItem(
                id=status_entry.id,
                status=status_entry.status,
                notes=status_entry.notes,
                updated_by_name=current_user.full_name,
                created_at=status_entry.created_at
            )
        ]
    )
