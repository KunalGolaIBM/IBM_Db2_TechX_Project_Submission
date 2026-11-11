import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, ElderCheckIn, AssistanceRequest
from backend.app.schemas.safety_schemas import (
    ElderCheckInCreate, ElderCheckInResponse, AssistanceRequestCreate, AssistanceRequestResponse
)
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/elder-care", tags=["Elder Care"])

@router.post("/checkins", response_model=ElderCheckInResponse, status_code=status.HTTP_201_CREATED)
def submit_elder_checkin(
    req: ElderCheckInCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    checkin = ElderCheckIn(
        user_id=current_user.id,
        scheduled_time=now,
        checked_in_at=now,
        status="completed",
        wellness_status=req.wellness_status,
        notes=req.notes,
        created_at=now
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    return ElderCheckInResponse(
        id=checkin.id,
        user_id=checkin.user_id,
        user_name=current_user.full_name,
        scheduled_time=checkin.scheduled_time,
        checked_in_at=checkin.checked_in_at,
        status=checkin.status,
        wellness_status=checkin.wellness_status,
        notes=checkin.notes,
        created_at=checkin.created_at
    )

@router.get("/checkins", response_model=List[ElderCheckInResponse])
def list_elder_checkins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role in ["responder", "admin"]:
        records = db.query(ElderCheckIn).order_by(ElderCheckIn.created_at.desc()).limit(50).all()
    else:
        records = db.query(ElderCheckIn).filter(ElderCheckIn.user_id == current_user.id).order_by(ElderCheckIn.created_at.desc()).all()

    return [
        ElderCheckInResponse(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user.full_name if r.user else "Senior Citizen",
            scheduled_time=r.scheduled_time,
            checked_in_at=r.checked_in_at,
            status=r.status,
            wellness_status=r.wellness_status,
            notes=r.notes,
            created_at=r.created_at
        )
        for r in records
    ]

@router.post("/assistance-requests", response_model=AssistanceRequestResponse, status_code=status.HTTP_201_CREATED)
def create_assistance_request(
    req: AssistanceRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    assist = AssistanceRequest(
        user_id=current_user.id,
        request_type=req.request_type,
        description=req.description,
        urgency=req.urgency,
        status="open",
        created_at=now
    )
    db.add(assist)
    db.commit()
    db.refresh(assist)

    return AssistanceRequestResponse(
        id=assist.id,
        user_id=assist.user_id,
        user_name=current_user.full_name,
        request_type=assist.request_type,
        description=assist.description,
        urgency=assist.urgency,
        status=assist.status,
        assigned_to_name=None,
        created_at=assist.created_at,
        resolved_at=None
    )

@router.get("/assistance-requests", response_model=List[AssistanceRequestResponse])
def list_assistance_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role in ["responder", "admin"]:
        records = db.query(AssistanceRequest).order_by(AssistanceRequest.created_at.desc()).all()
    else:
        records = db.query(AssistanceRequest).filter(AssistanceRequest.user_id == current_user.id).order_by(AssistanceRequest.created_at.desc()).all()

    return [
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
        for r in records
    ]
