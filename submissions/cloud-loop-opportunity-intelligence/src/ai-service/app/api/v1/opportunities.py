from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional
from app.core.security import verify_internal_api_key
from app.schemas.opportunity import OpportunityListResponse, OpportunityResponse
from app.repositories.opportunity_repository import opportunity_repo

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    kind: Optional[str] = Query(None, description="Filter by kind: job, internship, event, program, certification"),
    search: Optional[str] = Query(None, description="Search keyword"),
    page: int = Query(1, ge=1, description="Page index"),
    limit: int = Query(20, ge=1, le=50, description="Items per page (max 50)"),
    _auth: bool = Depends(verify_internal_api_key),
):
    """
    GET /api/v1/opportunities
    Paginated opportunity listing using Db2 FETCH FIRST n ROWS ONLY and OFFSET.
    """
    items_data, total = opportunity_repo.list_opportunities(
        kind=kind,
        search=search,
        page=page,
        limit=limit,
    )
    return OpportunityListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[OpportunityResponse(**it) for it in items_data],
    )

@router.get("/{slug}", response_model=OpportunityResponse)
def get_opportunity(
    slug: str,
    _auth: bool = Depends(verify_internal_api_key),
):
    """
    GET /api/v1/opportunities/{slug}
    Retrieves full opportunity details by unique slug or ID.
    """
    opp = opportunity_repo.get_by_slug(slug) or opportunity_repo.get_by_id(slug)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity with slug '{slug}' not found",
        )
    return OpportunityResponse(**opp)
