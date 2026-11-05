"""Unit tests for Deterministic Waste Ranking Engine."""
from recipe_waste_optimizer.services.ranking_service import WasteRankingEngine


def test_ranking_prefers_near_expiry_ingredients():
    engine = WasteRankingEngine()

    recipe_spinach = {
        "recipe_id": 1,
        "name": "Spinach Sauté",
        "servings": 2,
        "dietary_tags": "vegetarian",
        "prep_minutes": 5,
        "cook_minutes": 5,
        "ingredients": [
            {"name": "spinach", "quantity": 100.0, "unit": "g", "is_optional": False},
            {"name": "garlic", "quantity": 2.0, "unit": "cloves", "is_optional": False}
        ]
    }

    recipe_potato = {
        "recipe_id": 2,
        "name": "Potato Fry",
        "servings": 2,
        "dietary_tags": "vegetarian",
        "prep_minutes": 5,
        "cook_minutes": 15,
        "ingredients": [
            {"name": "potato", "quantity": 2.0, "unit": "pieces", "is_optional": False},
            {"name": "garlic", "quantity": 2.0, "unit": "cloves", "is_optional": False}
        ]
    }

    # Inventory where spinach is urgent (expires in 1 day), potato is safe (expires in 14 days)
    inventory = [
        {"ingredient_name": "spinach", "quantity": 150.0, "unit": "g", "status": "available", "expiry_status": "urgent", "days_until_expiry": 1},
        {"ingredient_name": "potato", "quantity": 4.0, "unit": "pieces", "status": "available", "expiry_status": "safe", "days_until_expiry": 14},
        {"ingredient_name": "garlic", "quantity": 10.0, "unit": "cloves", "status": "available", "expiry_status": "safe", "days_until_expiry": 30},
    ]

    score_spinach, det_spinach = engine.evaluate_recipe(recipe_spinach, inventory, semantic_score=0.7)
    score_potato, det_potato = engine.evaluate_recipe(recipe_potato, inventory, semantic_score=0.7)

    # Both have 100% coverage, but spinach MUST rank higher due to urgent expiry date!
    assert score_spinach > score_potato
    assert det_spinach["expiry_score"] > det_potato["expiry_score"]
    assert any("spinach" in item for item in det_spinach["expiring_ingredients_used"])


def test_ranking_hard_filters_dietary():
    engine = WasteRankingEngine()
    meat_recipe = {
        "recipe_id": 99,
        "name": "Chicken Curry",
        "servings": 2,
        "dietary_tags": "non-vegetarian",
        "ingredients": [{"name": "chicken", "quantity": 250, "unit": "g"}]
    }
    inventory = [{"ingredient_name": "chicken", "quantity": 500, "unit": "g", "status": "available"}]

    score, det = engine.evaluate_recipe(meat_recipe, inventory, semantic_score=0.9, dietary_preferences=["vegetarian"])
    assert score < 0
    assert "Violates dietary preference" in det["reason"]


def test_ranking_missing_ingredient_penalty():
    engine = WasteRankingEngine()
    recipe_full = {
        "recipe_id": 10,
        "name": "Simple Dish",
        "servings": 2,
        "dietary_tags": "vegetarian",
        "ingredients": [
            {"name": "tomato", "quantity": 2.0, "unit": "pieces", "is_optional": False}
        ]
    }
    recipe_missing = {
        "recipe_id": 11,
        "name": "Complex Dish",
        "servings": 2,
        "dietary_tags": "vegetarian",
        "ingredients": [
            {"name": "tomato", "quantity": 2.0, "unit": "pieces", "is_optional": False},
            {"name": "truffle oil", "quantity": 10.0, "unit": "ml", "is_optional": False},
            {"name": "saffron", "quantity": 1.0, "unit": "g", "is_optional": False}
        ]
    }
    inventory = [{"ingredient_name": "tomato", "quantity": 5.0, "unit": "pieces", "status": "available", "expiry_status": "safe"}]

    score_full, _ = engine.evaluate_recipe(recipe_full, inventory, semantic_score=0.6)
    score_missing, _ = engine.evaluate_recipe(recipe_missing, inventory, semantic_score=0.6)

    assert score_full > score_missing
