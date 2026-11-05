"""Pydantic schemas for Recommendations and AI Generation."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    message: str = Field(..., description="User's meal query or craving (e.g. 'Quick vegetarian dinner using spinach')")
    household_id: Optional[str] = None
    servings: int = Field(2, ge=1, le=10)
    max_cooking_minutes: Optional[int] = Field(None, ge=5, le=180)
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)


class RankedRecipeCandidate(BaseModel):
    recipe_id: int
    name: str
    description: str
    cuisine: str
    prep_minutes: int
    cook_minutes: int
    servings: int
    dietary_tags: Optional[str]
    total_score: float
    semantic_score: float
    coverage_score: float
    sufficiency_score: float
    expiry_score: float
    matching_ingredients: List[str]
    missing_ingredients: List[str]
    expiring_ingredients_used: List[str]
    explanation: str


class GeneratedRecipeIngredient(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    source: Literal["inventory", "additional"]
    note: Optional[str] = None


class GeneratedRecipe(BaseModel):
    recipe_id: int
    recipe_name: str
    servings: int
    preparation_minutes: Optional[int] = None
    cooking_minutes: Optional[int] = None
    ingredients: List[GeneratedRecipeIngredient]
    instructions: List[str]
    missing_ingredients: List[str]
    inventory_ingredients_used: List[str]
    waste_reduction_explanation: str
    safety_notes: List[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    query: str
    top_candidates: List[RankedRecipeCandidate]
    selected_recipe: Optional[GeneratedRecipe] = None


class CookedConfirmationRequest(BaseModel):
    household_id: Optional[str] = None
    servings_prepared: int = Field(2, ge=1, le=10)
    custom_deductions: Optional[dict] = None  # optional custom ingredient overrides


class CookedConfirmationResponse(BaseModel):
    success: bool
    message: str
    recipe_id: int
    servings_prepared: int
    inventory_deductions: List[dict]
    history_id: int
