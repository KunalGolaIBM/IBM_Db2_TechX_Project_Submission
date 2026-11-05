"""Deterministic Waste Optimizer and Candidate Re-Ranking Service.

Applies multi-signal scoring in Python without delegating arithmetic to LLMs.
"""
from typing import List, Dict, Any, Tuple
from recipe_waste_optimizer.services.normalization import (
    normalize_ingredient_name,
    are_units_compatible,
    convert_quantity
)


class WasteRankingEngine:
    """Computes deterministic coverage, sufficiency, and expiry-priority scores."""

    def __init__(
        self,
        weight_semantic: float = 0.20,
        weight_coverage: float = 0.30,
        weight_sufficiency: float = 0.20,
        weight_expiry: float = 0.20,
        weight_preference: float = 0.10,
        missing_penalty_per_item: float = 0.08,
    ):
        self.w_semantic = weight_semantic
        self.w_coverage = weight_coverage
        self.w_sufficiency = weight_sufficiency
        self.w_expiry = weight_expiry
        self.w_preference = weight_preference
        self.penalty_missing = missing_penalty_per_item

    def evaluate_recipe(
        self,
        recipe: Dict[str, Any],
        inventory: List[Dict[str, Any]],
        semantic_score: float,
        servings: int = 2,
        dietary_preferences: List[str] = None,
        max_cooking_minutes: int = None
    ) -> Tuple[float, Dict[str, Any]]:
        """Evaluate and rank a single recipe candidate against household inventory."""
        dietary_preferences = dietary_preferences or []
        recipe_tags = (recipe.get("dietary_tags") or "").lower()

        # Hard Filter 1: Dietary exclusions
        tag_tokens = [t.strip().lower() for t in recipe_tags.replace(";", ",").split(",") if t.strip()]
        for pref in dietary_preferences:
            pref_lower = pref.lower()
            if pref_lower == "vegetarian":
                if "vegetarian" not in tag_tokens and "vegan" not in tag_tokens or "non-vegetarian" in tag_tokens:
                    return -1.0, {"reason": "Violates dietary preference 'vegetarian'"}
            elif pref_lower == "vegan":
                if "vegan" not in tag_tokens:
                    return -1.0, {"reason": "Violates dietary preference 'vegan'"}
            elif pref_lower == "gluten-free":
                if "gluten-free" not in tag_tokens:
                    return -1.0, {"reason": "Violates dietary preference 'gluten-free'"}
            elif pref_lower not in tag_tokens:
                return -1.0, {"reason": f"Violates dietary preference '{pref}'"}

        # Hard Filter 2: Max cooking time
        total_time = recipe.get("prep_minutes", 0) + recipe.get("cook_minutes", 0)
        if max_cooking_minutes and total_time > max_cooking_minutes:
            return -1.0, {"reason": f"Total time {total_time}m exceeds maximum {max_cooking_minutes}m"}

        # Build inventory lookup map by canonical name
        inv_map = {}
        for item in inventory:
            if item.get("status") == "available" and item.get("expiry_status") != "expired":
                canon = normalize_ingredient_name(item["ingredient_name"])
                inv_map[canon] = item

        recipe_ingredients = recipe.get("ingredients", [])
        required_ingredients = [ing for ing in recipe_ingredients if not ing.get("is_optional")]

        if not required_ingredients:
            required_ingredients = recipe_ingredients

        matched_names = []
        missing_names = []
        expiring_used = []
        sufficiency_ratios = []
        expiry_scores = []

        scale = servings / max(1, recipe.get("servings", 2))

        for ing in required_ingredients:
            ing_name = normalize_ingredient_name(ing["name"])
            req_qty = ing.get("quantity")
            req_unit = ing.get("unit", "pieces")

            if ing_name in inv_map:
                matched_names.append(ing_name)
                inv_item = inv_map[ing_name]
                inv_qty = inv_item.get("quantity", 0.0)
                inv_unit = inv_item.get("unit", "pieces")

                # Expiry signal calculation
                exp_status = inv_item.get("expiry_status", "unknown")
                if exp_status == "urgent":
                    expiry_scores.append(1.0)
                    expiring_used.append(f"{ing_name} (expires in {inv_item.get('days_until_expiry')}d)")
                elif exp_status == "approaching":
                    expiry_scores.append(0.6)
                    expiring_used.append(f"{ing_name} (expires in {inv_item.get('days_until_expiry')}d)")
                elif exp_status == "safe":
                    expiry_scores.append(0.2)
                else:
                    expiry_scores.append(0.1)

                # Quantity sufficiency calculation
                if req_qty is not None:
                    scaled_req = req_qty * scale
                    if are_units_compatible(inv_unit, req_unit):
                        converted_inv = convert_quantity(inv_qty, inv_unit, req_unit)
                        if converted_inv is not None:
                            ratio = min(1.0, converted_inv / max(0.001, scaled_req))
                            sufficiency_ratios.append(ratio)
                        else:
                            sufficiency_ratios.append(0.5)
                    else:
                        sufficiency_ratios.append(0.5)
                else:
                    sufficiency_ratios.append(0.5)
            else:
                missing_names.append(ing_name)

        # Coverage: fraction of required ingredients present
        coverage = len(matched_names) / max(1, len(required_ingredients))

        # Quantity sufficiency average
        sufficiency = sum(sufficiency_ratios) / max(1, len(sufficiency_ratios)) if sufficiency_ratios else 0.0

        # Expiry priority average
        expiry_priority = sum(expiry_scores) / max(1, len(expiry_scores)) if expiry_scores else 0.0

        # Preference match
        pref_match = 1.0 if not dietary_preferences else 0.8

        # Penalty for missing ingredients
        missing_penalty = min(0.40, len(missing_names) * self.penalty_missing)

        total_score = (
            self.w_semantic * semantic_score
            + self.w_coverage * coverage
            + self.w_sufficiency * sufficiency
            + self.w_expiry * expiry_priority
            + self.w_preference * pref_match
            - missing_penalty
        )
        total_score = max(0.0, min(1.0, total_score))

        # Build transparent explanation
        explanation_parts = []
        if expiring_used:
            explanation_parts.append(f"Prioritizes items near expiry: {', '.join(expiring_used)}.")
        if coverage >= 0.8:
            explanation_parts.append(f"Excellent coverage ({int(coverage * 100)}% of ingredients in stock).")
        elif coverage >= 0.5:
            explanation_parts.append(f"Moderate coverage ({int(coverage * 100)}% in stock).")
        else:
            explanation_parts.append(f"Low coverage ({len(missing_names)} missing items).")

        if missing_names:
            explanation_parts.append(f"Needs: {', '.join(missing_names)}.")
        else:
            explanation_parts.append("Ready to cook with 100% available pantry ingredients!")

        details = {
            "total_score": round(total_score, 4),
            "semantic_score": round(semantic_score, 4),
            "coverage_score": round(coverage, 4),
            "sufficiency_score": round(sufficiency, 4),
            "expiry_score": round(expiry_priority, 4),
            "matching_ingredients": matched_names,
            "missing_ingredients": missing_names,
            "expiring_ingredients_used": expiring_used,
            "explanation": " ".join(explanation_parts)
        }

        return total_score, details


ranking_engine = WasteRankingEngine()
