from fastapi import APIRouter, Query
from typing import Optional, List
from backend.app.ai.vector_search import semantic_search_opportunities
from backend.app.schemas.opportunity import OpportunityResponse

router = APIRouter(prefix="/search", tags=["Semantic Search"])

@router.get("")
def search_opportunities(
    q: str = Query(..., min_length=2, description="Natural language search query"),
    type: Optional[str] = Query(None, description="Optional opportunity type filter"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    scored_results = semantic_search_opportunities(query=q, limit=limit, opp_type=type)
    return {
        "query": q,
        "count": len(scored_results),
        "engine": "IBM Db2 & Sentence-Transformers 384-dim Vector Matcher",
        "results": [
            {
                "opportunity": OpportunityResponse(**item),
                "similarity_score": round(score, 4),
            }
            for item, score in scored_results
        ]
    }

