from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schemas.tracking import TrackingCreate, TrackingResponse, TrackingItem
from backend.app.repositories.tracking_repository import tracking_repo
from backend.app.core.security import get_current_user_id

router = APIRouter(prefix="/tracking", tags=["User Opportunity Tracking"])

@router.get("", response_model=TrackingResponse)
def get_tracking(user_id: str = Depends(get_current_user_id)):
    items = tracking_repo.get_user_tracking(user_id)
    counts = tracking_repo.get_counts(user_id)
    return {
        "items": [TrackingItem(**i) for i in items],
        "total_saved": counts.get("saved", 0),
        "total_applied": counts.get("applied", 0),
        "total_review": counts.get("under_review", 0),
    }

@router.post("")
def update_tracking(
    req: TrackingCreate,
    user_id: str = Depends(get_current_user_id),
):
    valid_statuses = ["saved", "applied", "under_review", "not_interested"]
    if req.application_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid application status. Must be one of: {', '.join(valid_statuses)}",
        )

    success = tracking_repo.set_tracking(
        user_id=user_id,
        opportunity_id=req.opportunity_id,
        status=req.application_status,
        bookmarked=req.bookmarked,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity '{req.opportunity_id}' not found.",
        )
    return {"success": True, "message": "Tracking status updated."}

