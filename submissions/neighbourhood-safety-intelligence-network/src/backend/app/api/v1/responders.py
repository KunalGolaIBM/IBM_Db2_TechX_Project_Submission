from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, Responder, Incident, AssistanceRequest
from backend.app.schemas.safety_schemas import (
    ResponderAvailabilityUpdate, ResponderProfileResponse, IncidentResponse, AssistanceRequestResponse
)
from backend.app.api.deps import get_current_user
from backend.app.api.v1.incidents import _format_incident_response

router = APIRouter(prefix="/responders", tags=["Responders"])

@router.get("/assignments", response_model=Dict[str, Any])
def get_responder_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["responder", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only responders and admins can access assignments.")

    # Get active incidents assigned to this responder OR unassigned reported incidents
    assigned_incidents = db.query(Incident).filter(
        (Incident.assigned_responder_id == current_user.id) |
        ((Incident.assigned_responder_id == None) & (Incident.status.in_(["reported", "acknowledged"])))
    ).order_by(Incident.priority.asc(), Incident.created_at.desc()).all()

    # Get assistance requests
    assigned_requests = db.query(AssistanceRequest).filter(
        (AssistanceRequest.assigned_to_id == current_user.id) |
        ((AssistanceRequest.assigned_to_id == None) & (AssistanceRequest.status == "open"))
    ).order_by(AssistanceRequest.created_at.desc()).all()

    return {
        "responder_name": current_user.full_name,
        "is_available": current_user.responder_profile.is_available if current_user.responder_profile else True,
        "incidents": [_format_incident_response(inc) for inc in assigned_incidents],
        "assistance_requests": [
            AssistanceRequestResponse(
                id=r.id,
                user_id=r.user_id,
                user_name=r.user.full_name if r.user else "Resident",
                request_type=r.request_type,
                description=r.description,
                urgency=r.urgency,
                status=r.status,
                assigned_to_name=r.assigned_to.full_name if r.assigned_to else None,
                created_at=r.created_at,
                resolved_at=r.resolved_at
            )
            for r in assigned_requests
        ]
    }

@router.patch("/availability", response_model=Dict[str, Any])
def update_availability(
    req: ResponderAvailabilityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["responder", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only responders can update availability.")

    profile = db.query(Responder).filter(Responder.user_id == current_user.id).first()
    if not profile:
        profile = Responder(
            user_id=current_user.id,
            badge_number=f"VOL-{current_user.id:04d}",
            service_type="community_patrol"
        )
        db.add(profile)

    profile.is_available = req.is_available
    if req.current_lat is not None:
        profile.current_lat = req.current_lat
    if req.current_lng is not None:
        profile.current_lng = req.current_lng

    db.commit()
    db.refresh(profile)

    return {
        "status": "success",
        "is_available": profile.is_available,
        "current_lat": profile.current_lat,
        "current_lng": profile.current_lng,
        "updated_at": "Updated successfully"
    }

@router.get("/roster", response_model=List[ResponderProfileResponse])
def get_responder_roster(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    responders = db.query(Responder).join(User).all()
    return [
        ResponderProfileResponse(
            id=r.id,
            user_id=r.user_id,
            full_name=r.user.full_name if r.user else "Officer",
            badge_number=r.badge_number,
            service_type=r.service_type,
            is_available=r.is_available,
            current_lat=r.current_lat,
            current_lng=r.current_lng,
            rating=r.rating,
            is_verified_by_admin=r.is_verified_by_admin
        )
        for r in responders
    ]
