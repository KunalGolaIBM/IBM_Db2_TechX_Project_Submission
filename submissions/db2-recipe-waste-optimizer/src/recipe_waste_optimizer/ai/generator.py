"""AI Recipe Instruction Generator with Pydantic Validation."""
import json
import logging
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from recipe_waste_optimizer.schemas.recommendation import (
    GeneratedRecipe,
    GeneratedRecipeIngredient,
    RankedRecipeCandidate
)
from recipe_waste_optimizer.ai.provider import get_chat_model
from recipe_waste_optimizer.services.normalization import normalize_ingredient_name

logger = logging.getLogger("recipe_generator")

SYSTEM_PROMPT = """You are a Michelin-star Chef and Household Food Waste Optimizer assistant.
Your task is to take a verified candidate recipe and the user's available household inventory,
and produce clear, customized step-by-step cooking instructions that prioritize expiring ingredients.

NON-NEGOTIABLE SAFETY & ACCURACY RULES:
1. ONLY use the supplied candidate recipe facts and inventory list.
2. NEVER claim unavailable ingredients are in inventory. If an ingredient is missing, mark its source as "additional".
3. Mark ingredients actually present in the user's inventory with source="inventory".
4. Do NOT state that food is safe solely based on dates.
5. Return ONLY a single valid JSON object adhering to the specified schema, without markdown formatting or commentary.

JSON Schema:
{
  "recipe_id": int,
  "recipe_name": string,
  "servings": int,
  "preparation_minutes": int,
  "cooking_minutes": int,
  "ingredients": [
    {"name": string, "quantity": float or null, "unit": string or null, "source": "inventory" or "additional", "note": string or null}
  ],
  "instructions": [string],
  "missing_ingredients": [string],
  "inventory_ingredients_used": [string],
  "waste_reduction_explanation": string,
  "safety_notes": [string]
}
"""


class RecipeGenerator:
    """Orchestrates LLM prompt assembly and schema validation."""

    def __init__(self):
        self.llm = get_chat_model()

    def generate(
        self,
        candidate: RankedRecipeCandidate,
        full_recipe: Dict[str, Any],
        inventory: List[Dict[str, Any]],
        servings: int = 2
    ) -> GeneratedRecipe:
        """Generate validated recipe instructions tailored to inventory."""
        available_names = {
            normalize_ingredient_name(item["ingredient_name"]): item
            for item in inventory
            if item.get("status") == "available" and item.get("expiry_status") != "expired"
        }

        # Try LLM generation if available
        if self.llm is not None:
            try:
                user_content = json.dumps({
                    "candidate_recipe": {
                        "id": candidate.recipe_id,
                        "name": candidate.name,
                        "description": candidate.description,
                        "cuisine": candidate.cuisine,
                        "prep_minutes": candidate.prep_minutes,
                        "cook_minutes": candidate.cook_minutes,
                        "servings": servings,
                        "base_ingredients": full_recipe.get("ingredients", []),
                        "base_instructions": full_recipe.get("instructions", [])
                    },
                    "inventory_available": [
                        {
                            "name": i["ingredient_name"],
                            "quantity": i["quantity"],
                            "unit": i["unit"],
                            "expiry_status": i.get("expiry_status"),
                            "days_until_expiry": i.get("days_until_expiry")
                        }
                        for i in inventory if i.get("status") == "available"
                    ],
                    "matched_ingredients": candidate.matching_ingredients,
                    "missing_ingredients": candidate.missing_ingredients,
                    "expiring_prioritized": candidate.expiring_ingredients_used
                }, indent=2)

                response = self.llm.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_content)
                ])

                content = response.content.strip()
                # Remove markdown fences if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                parsed = json.loads(content)

                # Validate using Pydantic
                recipe_obj = GeneratedRecipe(**parsed)

                # Post-validation check: enforce no fake inventory claims
                for ing in recipe_obj.ingredients:
                    norm_name = normalize_ingredient_name(ing.name)
                    if ing.source == "inventory" and norm_name not in available_names:
                        # Reclassify hallucinated inventory item to additional
                        ing.source = "additional"

                return recipe_obj
            except Exception as e:
                logger.warning(f"LLM generation failed or returned invalid JSON ({e}). Using deterministic fallback.")

        # Deterministic Grounded Generation Fallback
        return self._generate_deterministic(candidate, full_recipe, inventory, servings)

    def _generate_deterministic(
        self,
        candidate: RankedRecipeCandidate,
        full_recipe: Dict[str, Any],
        inventory: List[Dict[str, Any]],
        servings: int
    ) -> GeneratedRecipe:
        """Guaranteed deterministic recipe generator requiring zero external network calls."""
        available_names = {
            normalize_ingredient_name(item["ingredient_name"]): item
            for item in inventory
            if item.get("status") == "available" and item.get("expiry_status") != "expired"
        }

        scale = servings / max(1, full_recipe.get("servings", 2))
        ingredients_out = []
        inv_used = []
        missing = []

        for ing in full_recipe.get("ingredients", []):
            norm = normalize_ingredient_name(ing["name"])
            qty = round(ing["quantity"] * scale, 2) if ing.get("quantity") is not None else None
            unit = ing.get("unit", "pieces")

            if norm in available_names:
                inv_item = available_names[norm]
                inv_used.append(norm)
                exp_msg = f" (expires in {inv_item.get('days_until_expiry')}d)" if inv_item.get("days_until_expiry") is not None else ""
                ingredients_out.append(GeneratedRecipeIngredient(
                    name=ing["name"],
                    quantity=qty,
                    unit=unit,
                    source="inventory",
                    note=f"Available in stock{exp_msg}"
                ))
            else:
                missing.append(norm)
                ingredients_out.append(GeneratedRecipeIngredient(
                    name=ing["name"],
                    quantity=qty,
                    unit=unit,
                    source="additional",
                    note="Required from store / shopping list"
                ))

        waste_exp = candidate.explanation or "Optimized to prioritize available household ingredients."

        return GeneratedRecipe(
            recipe_id=candidate.recipe_id,
            recipe_name=candidate.name,
            servings=servings,
            preparation_minutes=candidate.prep_minutes,
            cooking_minutes=candidate.cook_minutes,
            ingredients=ingredients_out,
            instructions=full_recipe.get("instructions", [
                "Prepare all listed ingredients.",
                "Combine according to recipe steps.",
                "Cook thoroughly and serve hot."
            ]),
            missing_ingredients=missing,
            inventory_ingredients_used=inv_used,
            waste_reduction_explanation=waste_exp,
            safety_notes=[
                "Always inspect food appearance and aroma before consumption regardless of entered expiry date.",
                "Ensure perishables like eggs, dairy, and poultry are cooked to safe internal temperatures."
            ]
        )


recipe_generator = RecipeGenerator()
