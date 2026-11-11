from fastapi import APIRouter
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import recommendation_service

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.post("", response_model=RecommendationResponse)
@router.post("/", response_model=RecommendationResponse)
def get_recommendations(req: RecommendationRequest):
    recs = recommendation_service.get_recommendations(
        user_id=req.user_id,
        limit=req.limit,
    )
    return {
        "count": len(recs),
        "recommendations": recs,
        "model_used": "IBM Db2 Academic Eligibility + 384-dim Vector Matcher",
    }

