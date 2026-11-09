from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional
from backend.app.schemas.opportunity import OpportunityResponse, OpportunityListResponse
from backend.app.services.opportunity_service import opportunity_service

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    type: Optional[str] = Query(None, description="Opportunity type: job, internship, event, program, certification"),
    category: Optional[str] = Query(None, description="Category filter"),
    search: Optional[str] = Query(None, description="Keyword search term"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    items, total = opportunity_service.list_opportunities(
        opp_type=type,
        category=category,
        search=search,
        page=page,
        limit=limit,
    )
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [OpportunityResponse(**item) for item in items],
    }

@router.get("/{id_or_slug}", response_model=OpportunityResponse)
def get_opportunity(id_or_slug: str):
    opp = opportunity_service.get_opportunity(id_or_slug)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity '{id_or_slug}' not found.",
        )
    return OpportunityResponse(**opp)

