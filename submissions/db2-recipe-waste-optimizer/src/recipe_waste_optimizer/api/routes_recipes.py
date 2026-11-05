"""Recipe Catalogue API routes."""
from typing import List
from fastapi import APIRouter, HTTPException, Query
from recipe_waste_optimizer.schemas.recipe import RecipeResponse, RecipeListResponse
from recipe_waste_optimizer.db.repositories.recipe_repo import RecipeRepository

router = APIRouter(prefix="/recipes", tags=["Recipe Catalogue"])
repo = RecipeRepository()


@router.get("", response_model=List[RecipeListResponse])
def list_recipes(limit: int = Query(50, ge=1, le=200)):
    """Browse stored recipes in the Db2 cookbook catalogue."""
    return repo.list_recipes(limit=limit)


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe_detail(recipe_id: int):
    """Retrieve full details of a recipe including ingredients and instructions."""
    recipe = repo.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe
