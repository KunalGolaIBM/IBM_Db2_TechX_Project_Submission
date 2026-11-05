"""Pydantic schemas for Recipes."""
from typing import List, Optional
from pydantic import BaseModel, Field


class RecipeIngredientItem(BaseModel):
    ingredient_id: Optional[int] = None
    name: str
    category: Optional[str] = "general"
    quantity: Optional[float] = None
    unit: Optional[str] = None
    is_optional: bool = False


class RecipeBase(BaseModel):
    name: str
    description: Optional[str] = None
    cuisine: Optional[str] = "General"
    prep_minutes: int = 15
    cook_minutes: int = 20
    servings: int = 2
    dietary_tags: Optional[str] = None
    source_name: Optional[str] = "Curated Home Kitchen"
    source_url: Optional[str] = None
    license_notes: Optional[str] = "CC-BY-4.0"
    instructions: List[str]
    ingredients: List[RecipeIngredientItem]


class RecipeResponse(RecipeBase):
    recipe_id: int


class RecipeListResponse(BaseModel):
    recipe_id: int
    name: str
    description: Optional[str]
    cuisine: Optional[str]
    prep_minutes: int
    cook_minutes: int
    servings: int
    dietary_tags: Optional[str]
    ingredient_count: int
