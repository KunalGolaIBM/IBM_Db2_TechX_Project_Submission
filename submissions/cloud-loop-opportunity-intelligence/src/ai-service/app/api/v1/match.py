from fastapi import APIRouter, Depends
from app.core.security import verify_internal_api_key
from app.schemas.match import MatchRequest, MatchResponse, MatchResultItem
from app.schemas.opportunity import OpportunityResponse
from app.services.match_service import match_service

router = APIRouter(prefix="/match", tags=["Opportunity Matching"])

@router.post("", response_model=MatchResponse)
async def match_student(
    request: MatchRequest,
    _auth: bool = Depends(verify_internal_api_key)
):
    """
    POST /api/v1/match
    Calculates multi-factor candidate match percentage (vector similarity + skills overlap)
    and produces an explanation ('why') line.
    With LLM: generated via local Ollama.
    Without LLM: deterministically composed from overlapping competencies.
    """
    result = await match_service.match_opportunities(
        skills=request.skills,
        interests=request.interests,
        year=request.year,
        limit=request.limit,
    )

    items = [
        MatchResultItem(
            opportunity=OpportunityResponse(**m["opportunity"]),
            match_percentage=m["match_percentage"],
            why=m["why"],
            explanation_mode=m["explanation_mode"],
            matched_skills=m["matched_skills"],
        )
        for m in result["matches"]
    ]

    return MatchResponse(
        total_matches=result["total_matches"],
        explanation_mode=result["explanation_mode"],
        matches=items,
    )
