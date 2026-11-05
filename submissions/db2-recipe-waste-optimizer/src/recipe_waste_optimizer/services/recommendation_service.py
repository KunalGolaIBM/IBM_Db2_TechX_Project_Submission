"""Unified Recommendation Service Coordinating Retrieval, Ranking, and Generation."""
import logging
from typing import Dict, Any, List, Optional
from recipe_waste_optimizer.db.connection import db_manager
from recipe_waste_optimizer.db.repositories.inventory_repo import InventoryRepository
from recipe_waste_optimizer.db.repositories.recipe_repo import RecipeRepository
from recipe_waste_optimizer.db.repositories.event_repo import EventRepository
from recipe_waste_optimizer.services.embedding_service import embedding_service
from recipe_waste_optimizer.services.ranking_service import ranking_engine
from recipe_waste_optimizer.ai.generator import recipe_generator
from recipe_waste_optimizer.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RankedRecipeCandidate,
    CookedConfirmationResponse
)
from recipe_waste_optimizer.services.normalization import (
    normalize_ingredient_name,
    are_units_compatible,
    convert_quantity
)
from recipe_waste_optimizer.config import settings

logger = logging.getLogger("recommendation_service")


class RecommendationService:
    """End-to-end recommendation workflow orchestrator."""

    def __init__(self, manager=None):
        self.manager = manager or db_manager
        self.inv_repo = InventoryRepository(self.manager)
        self.recipe_repo = RecipeRepository(self.manager)
        self.event_repo = EventRepository(self.manager)

    def get_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        """Execute two-stage hybrid retrieval and grounded generation."""
        household_id = request.household_id or settings.DEFAULT_HOUSEHOLD_ID

        # 1. Fetch current available inventory from Db2
        inventory = self.inv_repo.list_inventory(household_id, status="available")

        # 2. Stage A: Semantic retrieval against Db2 embeddings
        query_vector = embedding_service.generate_embedding(request.message)
        stored_embeddings = self.recipe_repo.get_all_embeddings()

        candidates = []
        if stored_embeddings:
            for item in stored_embeddings:
                sim = embedding_service.cosine_similarity(query_vector, item["embedding"])
                candidates.append((item["recipe_id"], sim))
            candidates.sort(key=lambda x: x[1], reverse=True)
        else:
            # Fallback: if no embeddings seeded yet, retrieve all recipes
            all_recipes = self.recipe_repo.list_recipes()
            candidates = [(r["recipe_id"], 0.5) for r in all_recipes]

        # 3. Stage B: Deterministic multi-signal evaluation
        ranked_candidates = []
        full_recipe_cache = {}

        for recipe_id, sem_score in candidates:
            recipe = self.recipe_repo.get_recipe(recipe_id)
            if not recipe:
                continue
            full_recipe_cache[recipe_id] = recipe

            score, details = ranking_engine.evaluate_recipe(
                recipe=recipe,
                inventory=inventory,
                semantic_score=sem_score,
                servings=request.servings,
                dietary_preferences=request.dietary_preferences,
                max_cooking_minutes=request.max_cooking_minutes
            )

            # Skip candidates rejected by hard filters
            if score < 0:
                continue

            ranked_candidates.append(RankedRecipeCandidate(
                recipe_id=recipe_id,
                name=recipe["name"],
                description=recipe.get("description", ""),
                cuisine=recipe.get("cuisine", "General"),
                prep_minutes=recipe.get("prep_minutes", 15),
                cook_minutes=recipe.get("cook_minutes", 20),
                servings=request.servings,
                dietary_tags=recipe.get("dietary_tags"),
                total_score=details["total_score"],
                semantic_score=details["semantic_score"],
                coverage_score=details["coverage_score"],
                sufficiency_score=details["sufficiency_score"],
                expiry_score=details["expiry_score"],
                matching_ingredients=details["matching_ingredients"],
                missing_ingredients=details["missing_ingredients"],
                expiring_ingredients_used=details["expiring_ingredients_used"],
                explanation=details["explanation"]
            ))

        # Sort by total deterministic score descending
        ranked_candidates.sort(key=lambda c: c.total_score, reverse=True)

        # 4. Generate structured recipe instructions for the top candidate
        selected_recipe = None
        if ranked_candidates:
            top_candidate = ranked_candidates[0]
            full_recipe = full_recipe_cache.get(top_candidate.recipe_id)
            if full_recipe:
                selected_recipe = recipe_generator.generate(
                    candidate=top_candidate,
                    full_recipe=full_recipe,
                    inventory=inventory,
                    servings=request.servings
                )

        return RecommendationResponse(
            query=request.message,
            top_candidates=ranked_candidates[:5],
            selected_recipe=selected_recipe
        )

    def confirm_cooked(
        self,
        recipe_id: int,
        household_id: Optional[str] = None,
        servings: int = 2
    ) -> CookedConfirmationResponse:
        """Confirm that a recipe was cooked and deduct inventory within a Db2 transaction."""
        household_id = household_id or settings.DEFAULT_HOUSEHOLD_ID
        recipe = self.recipe_repo.get_recipe(recipe_id)
        if not recipe:
            raise ValueError(f"Recipe with ID {recipe_id} not found.")

        scale = servings / max(1, recipe.get("servings", 2))
        inventory = self.inv_repo.list_inventory(household_id, status="available")
        inv_map = {normalize_ingredient_name(item["ingredient_name"]): item for item in inventory}

        deductions = []

        # Atomic transaction across inventory and cooking history
        with self.manager.cursor() as cur:
            for ing in recipe.get("ingredients", []):
                norm = normalize_ingredient_name(ing["name"])
                if norm in inv_map and ing.get("quantity") is not None:
                    inv_item = inv_map[norm]
                    inv_unit = inv_item["unit"]
                    req_unit = ing.get("unit", "pieces")
                    req_qty = ing["quantity"] * scale

                    # Convert quantity if units are compatible
                    if are_units_compatible(inv_unit, req_unit):
                        deduct_in_inv_units = convert_quantity(req_qty, req_unit, inv_unit)
                    else:
                        deduct_in_inv_units = req_qty

                    if deduct_in_inv_units is not None:
                        new_qty = max(0.0, round(inv_item["quantity"] - deduct_in_inv_units, 2))
                        new_status = "consumed" if new_qty == 0 else "available"

                        cur.execute(
                            """
                            UPDATE USER_INVENTORY
                            SET quantity = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE inventory_id = ? AND household_id = ?
                            """,
                            (new_qty, new_status, inv_item["inventory_id"], household_id)
                        )

                        cur.execute(
                            """
                            INSERT INTO INVENTORY_EVENTS (household_id, ingredient_id, event_type, quantity_delta, unit, reason)
                            VALUES (?, ?, 'consumed', ?, ?, ?)
                            """,
                            (household_id, inv_item["ingredient_id"], -deduct_in_inv_units, inv_unit, f"Cooked recipe '{recipe['name']}'")
                        )

                        deductions.append({
                            "ingredient": norm,
                            "deducted": deduct_in_inv_units,
                            "remaining": new_qty,
                            "unit": inv_unit,
                            "status": new_status
                        })

            # Record cooking history
            cur.execute(
                """
                INSERT INTO COOKING_HISTORY (household_id, recipe_id, servings_prepared)
                VALUES (?, ?, ?)
                """,
                (household_id, recipe_id, servings)
            )
            cur.execute(
                """
                SELECT history_id FROM COOKING_HISTORY
                WHERE household_id = ? AND recipe_id = ?
                ORDER BY cooked_at DESC FETCH FIRST 1 ROWS ONLY
                """,
                (household_id, recipe_id)
            )
            history_id = cur.fetchone()[0]

        return CookedConfirmationResponse(
            success=True,
            message=f"Successfully logged cooking for '{recipe['name']}'. Updated stock for {len(deductions)} ingredients.",
            recipe_id=recipe_id,
            servings_prepared=servings,
            inventory_deductions=deductions,
            history_id=history_id
        )


recommendation_service = RecommendationService()
