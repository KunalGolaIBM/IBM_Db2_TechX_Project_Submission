"""Recommendation and Cooking Confirmation API routes."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from recipe_waste_optimizer.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    CookedConfirmationRequest,
    CookedConfirmationResponse
)
from recipe_waste_optimizer.services.recommendation_service import recommendation_service
from recipe_waste_optimizer.db.repositories.event_repo import EventRepository
from recipe_waste_optimizer.config import settings

router = APIRouter(tags=["AI Recipe Recommendation & Consumption"])
event_repo = EventRepository()


@router.post("/recipes/recommend", response_model=RecommendationResponse)
def recommend_recipes(request: RecommendationRequest):
    """Hybrid retrieval and grounded AI generation endpoint."""
    try:
        return recommendation_service.get_recommendations(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {e}")


@router.post("/recipes/{recipe_id}/cooked", response_model=CookedConfirmationResponse)
def confirm_recipe_cooked(recipe_id: int, request: CookedConfirmationRequest):
    """Confirm a recipe was cooked, deduct inventory, and write history to Db2."""
    try:
        return recommendation_service.confirm_cooked(
            recipe_id=recipe_id,
            household_id=request.household_id,
            servings=request.servings_prepared
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm cooked recipe: {e}")


@router.get("/history")
def get_cooking_history(household_id: Optional[str] = Query(None)):
    """Fetch cooking history and consumption events."""
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    history = event_repo.get_history(hid)
    summary = event_repo.get_waste_summary(hid)
    return {
        "household_id": hid,
        "cooking_events": history,
        "event_summary": summary
    }
