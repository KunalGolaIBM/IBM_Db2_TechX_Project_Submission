from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import ensure_verified_staff, get_current_user, is_staff, require_roles
from backend.app.api.v1.incidents import ACTIVE_STATUSES, _format_incident_response, incident_query
from backend.app.core.audit import record_audit
from backend.app.database.base import get_db
from backend.app.models.entities import AssistanceRequest, Incident, Responder, User
from backend.app.schemas.safety_schemas import (
    AssistanceRequestResponse, ResponderAvailabilityUpdate, ResponderProfileResponse,
)

router = APIRouter(prefix="/responders", tags=["Responders"])


@router.get("/assignments", response_model=Dict[str, Any])
def get_responder_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_verified_staff(current_user)

    # Incidents assigned to me that are still open, plus unclaimed new ones. P1 sorts before P2, etc.
    incidents = incident_query(db).filter(
        ((Incident.assigned_responder_id == current_user.id) & Incident.status.in_(ACTIVE_STATUSES))
        | ((Incident.assigned_responder_id.is_(None)) & Incident.status.in_(("reported", "acknowledged")))
    ).order_by(Incident.priority.asc(), Incident.created_at.desc()).all()

    requests = db.query(AssistanceRequest).options(
        selectinload(AssistanceRequest.user), selectinload(AssistanceRequest.assigned_to)
    ).filter(
        (AssistanceRequest.assigned_to_id == current_user.id)
        | ((AssistanceRequest.assigned_to_id.is_(None)) & (AssistanceRequest.status == "open"))
    ).order_by(AssistanceRequest.created_at.desc()).all()

    return {
        "responder_name": current_user.full_name,
        "is_available": current_user.responder_profile.is_available if current_user.responder_profile else True,
        "incidents": [_format_incident_response(inc, current_user) for inc in incidents],
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
                resolved_at=r.resolved_at,
            )
            for r in requests
        ],
    }


@router.patch("/availability", response_model=Dict[str, Any])
def update_availability(
    req: ResponderAvailabilityUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_verified_staff(current_user)

    profile = db.query(Responder).filter(Responder.user_id == current_user.id).first()
    if not profile:
        profile = Responder(user_id=current_user.id, badge_number=f"VOL-{current_user.id:04d}",
                            service_type="community_patrol")
        db.add(profile)
    profile.is_available = req.is_available
    if req.current_lat is not None:
        profile.current_lat = req.current_lat
    if req.current_lng is not None:
        profile.current_lng = req.current_lng
    record_audit(db, "responder_availability_changed", "responder", current_user.id, user_id=current_user.id,
                 request=request, details={"is_available": req.is_available})
    db.commit()
    db.refresh(profile)
    return {
        "status": "success",
        "is_available": profile.is_available,
        "current_lat": profile.current_lat,
        "current_lng": profile.current_lng,
    }


@router.get("/roster", response_model=List[ResponderProfileResponse])
def get_responder_roster(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    responders = (
        db.query(Responder).options(selectinload(Responder.user))
        .join(User, Responder.user_id == User.id)
        .filter(User.is_active == True)  # noqa: E712  ("= 1" on Db2; ".is_(True)" would render invalid "IS 1")
        .order_by(User.full_name).all()
    )
    show_location = is_staff(current_user)  # residents never see responders' live coordinates
    return [
        ResponderProfileResponse(
            id=r.id,
            user_id=r.user_id,
            full_name=r.user.full_name if r.user else "Officer",
            badge_number=r.badge_number,
            service_type=r.service_type,
            is_available=r.is_available,
            current_lat=r.current_lat if show_location else None,
            current_lng=r.current_lng if show_location else None,
            rating=r.rating,
            is_verified_by_admin=bool(r.is_verified_by_admin and r.user and r.user.is_verified),
        )
        for r in responders
    ]


@router.post("/{user_id}/verify", response_model=ResponderProfileResponse)
def verify_responder(
    user_id: int,
    request: Request,
    admin: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Admin approval for a self-registered responder."""
    profile = db.query(Responder).options(selectinload(Responder.user)).filter(Responder.user_id == user_id).first()
    if not profile or not profile.user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Responder not found.")
    profile.is_verified_by_admin = True
    profile.user.is_verified = True
    record_audit(db, "responder_verified", "user", user_id, user_id=admin.id, request=request)
    db.commit()
    db.refresh(profile)
    return ResponderProfileResponse(
        id=profile.id, user_id=profile.user_id, full_name=profile.user.full_name,
        badge_number=profile.badge_number, service_type=profile.service_type,
        is_available=profile.is_available, current_lat=profile.current_lat, current_lng=profile.current_lng,
        rating=profile.rating, is_verified_by_admin=True,
    )
