from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.profile import StudentProfileCreate, StudentProfileResponse
from app.repositories.profile_repository import profile_repo
from app.core.security import get_current_user_id

router = APIRouter(prefix="/profile", tags=["Student Profile"])

@router.get("", response_model=StudentProfileResponse)
def get_profile(user_id: str = Depends(get_current_user_id)):
    profile = profile_repo.get_by_user_id(user_id)
    if not profile:
        # Return default starter profile
        return StudentProfileResponse(
            user_id=user_id,
            education="Engineering Student",
            degree="B.Tech / B.E.",
            study_year=3,
            graduation_batch="2026",
            skills=["Python", "JavaScript", "Cloud Computing"],
            interests=["Software Engineering", "AI/ML"],
            preferred_domains=["Software", "Cloud", "Open Source"],
            preferred_locations=["Remote", "Pan-India"],
        )
    return StudentProfileResponse(**profile)

@router.post("", response_model=StudentProfileResponse)
def save_profile(
    data: StudentProfileCreate,
    user_id: str = Depends(get_current_user_id),
):
    updated = profile_repo.upsert(user_id, data.model_dump())
    return StudentProfileResponse(**updated)

