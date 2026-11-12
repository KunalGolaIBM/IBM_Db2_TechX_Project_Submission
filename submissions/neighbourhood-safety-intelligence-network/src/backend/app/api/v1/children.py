import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, is_staff
from backend.app.core.audit import record_audit
from backend.app.database.base import get_db
from backend.app.models.entities import ChildJourney, User
from backend.app.schemas.safety_schemas import ChildCheckInRequest, ChildJourneyCreate, ChildJourneyResponse

router = APIRouter(prefix="/children/journeys", tags=["Child Safety"])


def flag_overdue_journeys(db: Session) -> int:
    """Mark active journeys past their expected arrival as 'delayed' with one set-based UPDATE."""
    now = datetime.datetime.utcnow()
    result = db.execute(
        update(ChildJourney)
        .where(ChildJourney.status == "active", ChildJourney.expected_arrival_time < now)
        .values(status="delayed")
        .execution_options(synchronize_session=False)
    )
    if result.rowcount:
        db.commit()
    return result.rowcount or 0


@router.post("", response_model=ChildJourneyResponse, status_code=status.HTTP_201_CREATED)
def create_child_journey(
    req: ChildJourneyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.datetime.utcnow()
    journey = ChildJourney(
        guardian_id=current_user.id,
        child_name=req.child_name.strip(),
        origin=req.origin.strip(),
        destination=req.destination.strip(),
        expected_arrival_time=now + datetime.timedelta(minutes=req.expected_duration_minutes),
        status="active",
        notes=req.notes,
        created_at=now,
    )
    db.add(journey)
    db.flush()
    record_audit(db, "child_journey_started", "child_journey", journey.id, user_id=current_user.id, request=request)
    db.commit()
    db.refresh(journey)
    return journey


@router.get("", response_model=List[ChildJourneyResponse])
def list_child_journeys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    flag_overdue_journeys(db)
    query = db.query(ChildJourney)
    # Guardians see their own children; staff see all journeys for safe-transit oversight.
    if not is_staff(current_user):
        query = query.filter(ChildJourney.guardian_id == current_user.id)
    return query.order_by(ChildJourney.created_at.desc()).limit(200).all()


@router.post("/{journey_id}/check-in", response_model=ChildJourneyResponse)
def check_in_child_journey(
    journey_id: int,
    req: ChildCheckInRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    journey = db.query(ChildJourney).filter(ChildJourney.id == journey_id).first()
    if not journey or (not is_staff(current_user) and journey.guardian_id != current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Child journey not found.")
    if journey.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This journey has already been completed.")

    now = datetime.datetime.utcnow()
    journey.status = req.status
    journey.last_check_in = now
    if req.status == "completed":
        journey.actual_arrival_time = now
    if req.notes:
        journey.notes = f"{journey.notes or ''}\n[{now:%H:%M}] {req.notes.strip()}".strip()[:2000]
    record_audit(db, "child_journey_check_in", "child_journey", journey.id, user_id=current_user.id,
                 request=request, details={"status": req.status})
    db.commit()
    db.refresh(journey)
    return journey
