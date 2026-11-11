from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User
from backend.app.schemas.safety_schemas import UserProfile, UserUpdate
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("/me", response_model=UserProfile)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=UserProfile)
def update_my_profile(
    req: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.full_name is not None:
        current_user.full_name = req.full_name
    if req.phone is not None:
        current_user.phone = req.phone
    if req.emergency_notes is not None:
        current_user.emergency_notes = req.emergency_notes
    if req.address is not None:
        current_user.address = req.address

    db.commit()
    db.refresh(current_user)
    return current_user
