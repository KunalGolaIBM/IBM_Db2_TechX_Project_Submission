from fastapi import APIRouter, Query, Depends, HTTPException, status
from app.core.security import verify_internal_api_key, get_current_user_id
from app.schemas.tracking import TrackRequest, TrackingListResponse, TrackedOpportunityItem
from app.schemas.opportunity import OpportunityResponse
from app.repositories.tracking_repository import tracking_repo

router = APIRouter(prefix="/tracking", tags=["Application Tracking"])

@router.get("", response_model=TrackingListResponse)
def get_user_tracking(
    user_id: str = Query(..., description="Target user ID"),
    _auth: bool = Depends(verify_internal_api_key),
):
    """
    GET /api/v1/tracking
    Retrieves all tracked opportunities and application pipeline status for a user.
    """
    items_data = tracking_repo.get_user_tracking(user_id)
    items = []
    for it in items_data:
        opp_model = None
        if it.get("opportunity"):
            try:
                opp_model = OpportunityResponse(**it["opportunity"])
            except Exception:
                pass
        items.append(
            TrackedOpportunityItem(
                user_id=it["user_id"],
                opportunity_id=it["opportunity_id"],
                status=it["status"],
                bookmarked=it["bookmarked"],
                updated_at=it["updated_at"],
                opportunity=opp_model,
            )
        )
    return TrackingListResponse(
        user_id=user_id,
        total=len(items),
        items=items,
    )

@router.put("")
def upsert_tracking(
    payload: TrackRequest,
    _auth: bool = Depends(verify_internal_api_key),
):
    """
    PUT /api/v1/tracking
    Executes a high-performance MERGE upsert into CLOUDLOOP.TRACKED_OPPORTUNITIES.
    """
    success = tracking_repo.set_tracking(
        user_id=payload.user_id,
        opportunity_id=payload.opportunity_id,
        status=payload.status,
        bookmarked=payload.bookmarked,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity {payload.opportunity_id} not found",
        )
    return {
        "ok": True,
        "user_id": payload.user_id,
        "opportunity_id": payload.opportunity_id,
        "status": payload.status,
        "bookmarked": payload.bookmarked,
    }
