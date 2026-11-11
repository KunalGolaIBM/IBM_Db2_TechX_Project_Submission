from fastapi import APIRouter, Query, Depends
from typing import Optional
from app.core.security import verify_internal_api_key
from app.schemas.search import SemanticSearchRequest, SemanticSearchResponse, SemanticSearchResultItem
from app.schemas.opportunity import OpportunityResponse
from app.services.haystack_service import haystack_db2_service
from app.repositories.opportunity_repository import opportunity_repo

router = APIRouter(prefix="/search", tags=["Semantic Search"])

@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    _auth: bool = Depends(verify_internal_api_key)
):
    """
    POST /api/v1/search/semantic
    Performs semantic opportunity retrieval over IBM Db2 & Haystack 384-dim dense vectors.
    Filters run inside Db2 when native store is active.
    """
    filters = None
    if request.kind and request.kind.lower() != "all":
        filters = {"field": "meta.kind", "operator": "==", "value": request.kind.lower()}

    raw_results = haystack_db2_service.search(
        query=request.query,
        filters=filters,
        top_k=request.top_k,
    )

    items = []
    for r in raw_results:
        opp_id = r["id"]
        opp_data = opportunity_repo.get_by_id(opp_id)
        if not opp_data:
            # Fall back to meta if relational row not yet cached
            meta = r.get("meta", {})
            opp_data = {
                "id": opp_id,
                "kind": meta.get("kind") or "job",
                "slug": meta.get("slug") or opp_id,
                "title": meta.get("title") or "Opportunity",
                "org": meta.get("org") or "Partner",
                "location": meta.get("location") or "India / Remote",
                "mode": meta.get("mode") or "onsite",
                "deadline": meta.get("deadline"),
                "apply_url": meta.get("apply_url") or "#",
                "source": meta.get("source") or "curated",
                "skills": [],
                "description": r.get("content", ""),
            }
        items.append(
            SemanticSearchResultItem(
                opportunity=OpportunityResponse(**opp_data),
                similarity_score=round(r.get("score", 0.0), 4),
            )
        )

    return SemanticSearchResponse(
        query=request.query,
        kind=request.kind,
        count=len(items),
        engine="IBM Db2 & Haystack 384-dim COSINE Vector Matcher",
        results=items,
    )

@router.get("", response_model=SemanticSearchResponse)
def get_search(
    q: str = Query(..., min_length=1, description="Natural language search query"),
    kind: Optional[str] = Query(None, description="Optional kind filter"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    _auth: bool = Depends(verify_internal_api_key),
):
    req = SemanticSearchRequest(query=q, kind=kind, top_k=limit)
    return semantic_search(req, _auth)
