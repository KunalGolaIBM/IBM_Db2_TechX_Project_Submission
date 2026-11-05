"""Unit tests for AI Recipe Generation and Hallucination Prevention."""
from recipe_waste_optimizer.ai.generator import RecipeGenerator
from recipe_waste_optimizer.schemas.recommendation import RankedRecipeCandidate


def test_generator_classifies_inventory_correctly():
    generator = RecipeGenerator()

    candidate = RankedRecipeCandidate(
        recipe_id=1,
        name="Spinach & Garlic Stir Fry",
        description="Fresh greens sautéed with garlic.",
        cuisine="Italian",
        prep_minutes=5,
        cook_minutes=5,
        servings=2,
        dietary_tags="vegan",
        total_score=0.88,
        semantic_score=0.85,
        coverage_score=0.75,
        sufficiency_score=1.0,
        expiry_score=0.9,
        matching_ingredients=["spinach", "garlic"],
        missing_ingredients=["olive oil"],
        expiring_ingredients_used=["spinach (expires in 1d)"],
        explanation="Uses urgent spinach."
    )

    full_recipe = {
        "recipe_id": 1,
        "name": "Spinach & Garlic Stir Fry",
        "servings": 2,
        "prep_minutes": 5,
        "cook_minutes": 5,
        "ingredients": [
            {"name": "spinach", "quantity": 150.0, "unit": "g"},
            {"name": "garlic", "quantity": 3.0, "unit": "cloves"},
            {"name": "olive oil", "quantity": 10.0, "unit": "ml"}
        ],
        "instructions": [
            "Wash and drain spinach.",
            "Sauté garlic in olive oil.",
            "Toss spinach until wilted."
        ]
    }

    # Inventory only has spinach and garlic; olive oil is absent
    inventory = [
        {"ingredient_name": "spinach", "quantity": 200.0, "unit": "g", "status": "available", "expiry_status": "urgent", "days_until_expiry": 1},
        {"ingredient_name": "garlic", "quantity": 6.0, "unit": "cloves", "status": "available", "expiry_status": "safe", "days_until_expiry": 15}
    ]

    generated = generator.generate(candidate, full_recipe, inventory, servings=2)

    assert generated.recipe_name == "Spinach & Garlic Stir Fry"
    assert "spinach" in generated.inventory_ingredients_used
    assert "cooking oil" in generated.missing_ingredients or "olive oil" in generated.missing_ingredients

    # Verify each ingredient's source classification
    for ing in generated.ingredients:
        if ing.name in ["spinach", "garlic"]:
            assert ing.source == "inventory"
        elif ing.name == "olive oil":
            assert ing.source == "additional"
