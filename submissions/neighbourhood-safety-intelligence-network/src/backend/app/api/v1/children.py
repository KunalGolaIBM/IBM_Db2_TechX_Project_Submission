import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, ChildJourney
from backend.app.schemas.safety_schemas import ChildJourneyCreate, ChildJourneyResponse, ChildCheckInRequest
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/children/journeys", tags=["Child Safety"])

@router.post("", response_model=ChildJourneyResponse, status_code=status.HTTP_201_CREATED)
def create_child_journey(
    req: ChildJourneyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    expected_arrival = now + datetime.timedelta(minutes=req.expected_duration_minutes)

    journey = ChildJourney(
        guardian_id=current_user.id,
        child_name=req.child_name,
        origin=req.origin,
        destination=req.destination,
        expected_arrival_time=expected_arrival,
        status="active",
        notes=req.notes,
        created_at=now
    )
    db.add(journey)
    db.commit()
    db.refresh(journey)
    return journey

@router.get("", response_model=List[ChildJourneyResponse])
def list_child_journeys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Guardians see their children; Responders/Admins see active journeys for safe transit oversight
    if current_user.role in ["responder", "admin"]:
        journeys = db.query(ChildJourney).order_by(ChildJourney.created_at.desc()).all()
    else:
        journeys = db.query(ChildJourney).filter(ChildJourney.guardian_id == current_user.id).order_by(ChildJourney.created_at.desc()).all()
    return journeys

@router.post("/{journey_id}/check-in", response_model=ChildJourneyResponse)
def check_in_child_journey(
    journey_id: int,
    req: ChildCheckInRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    journey = db.query(ChildJourney).filter(ChildJourney.id == journey_id).first()
    if not journey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child journey not found.")

    if current_user.role not in ["responder", "admin"] and journey.guardian_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to check in this journey.")

    now = datetime.datetime.utcnow()
    journey.status = req.status
    journey.last_check_in = now
    if req.status == "completed":
        journey.actual_arrival_time = now
    if req.notes:
        existing_notes = journey.notes or ""
        journey.notes = f"{existing_notes}\n[{now.strftime('%H:%M')}] {req.notes}".strip()

    db.commit()
    db.refresh(journey)
    return journey
