"""Recipe Repository for IBM Db2."""
import json
from typing import List, Optional, Dict, Any
from recipe_waste_optimizer.db.connection import db_manager
from recipe_waste_optimizer.db.repositories.inventory_repo import InventoryRepository


class RecipeRepository:
    """Handles Db2 queries for recipes, ingredients, and embeddings."""

    def __init__(self, manager=None):
        self.manager = manager or db_manager
        self.inv_repo = InventoryRepository(self.manager)

    def create_recipe(self, recipe_dict: Dict[str, Any]) -> int:
        """Insert a recipe and its mapped ingredients into Db2."""
        with self.manager.cursor() as cur:
            # Check if already exists by name
            cur.execute("SELECT recipe_id FROM RECIPES WHERE name = ?", (recipe_dict["name"],))
            row = cur.fetchone()
            if row:
                return row[0]

            cur.execute(
                """
                INSERT INTO RECIPES (
                    name, description, cuisine, prep_minutes, cook_minutes,
                    servings, instructions_json, dietary_tags, source_name,
                    source_url, license_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_dict["name"],
                    recipe_dict.get("description", ""),
                    recipe_dict.get("cuisine", "General"),
                    recipe_dict.get("prep_minutes", 15),
                    recipe_dict.get("cook_minutes", 20),
                    recipe_dict.get("servings", 2),
                    json.dumps(recipe_dict.get("instructions", [])),
                    recipe_dict.get("dietary_tags", ""),
                    recipe_dict.get("source_name", "Curated Home Kitchen"),
                    recipe_dict.get("source_url", ""),
                    recipe_dict.get("license_notes", "CC-BY-4.0"),
                )
            )
            cur.execute("SELECT recipe_id FROM RECIPES WHERE name = ?", (recipe_dict["name"],))
            recipe_id = cur.fetchone()[0]

            # Insert recipe ingredients
            for ing in recipe_dict.get("ingredients", []):
                ing_id = self.inv_repo.get_or_create_ingredient(
                    name=ing["name"],
                    category=ing.get("category", "general"),
                    default_unit=ing.get("unit", "pieces")
                )
                cur.execute(
                    """
                    INSERT INTO RECIPE_INGREDIENTS (recipe_id, ingredient_id, quantity, unit, is_optional)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id,
                        ing_id,
                        ing.get("quantity"),
                        ing.get("unit", "pieces"),
                        1 if ing.get("is_optional") else 0
                    )
                )

            return recipe_id

    def get_recipe(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """Fetch recipe by ID including parsed ingredients."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                SELECT recipe_id, name, description, cuisine, prep_minutes,
                       cook_minutes, servings, instructions_json, dietary_tags,
                       source_name, source_url, license_notes
                FROM RECIPES
                WHERE recipe_id = ?
                """,
                (recipe_id,)
            )
            row = cur.fetchone()
            if not row:
                return None

            recipe = {
                "recipe_id": int(row[0]),
                "name": str(row[1]),
                "description": str(row[2]),
                "cuisine": str(row[3]),
                "prep_minutes": int(row[4]),
                "cook_minutes": int(row[5]),
                "servings": int(row[6]),
                "instructions": json.loads(row[7]) if row[7] else [],
                "dietary_tags": str(row[8]) if row[8] else "",
                "source_name": str(row[9]),
                "source_url": str(row[10]),
                "license_notes": str(row[11]),
                "ingredients": []
            }

            cur.execute(
                """
                SELECT ri.ingredient_id, g.canonical_name, g.category,
                       ri.quantity, ri.unit, ri.is_optional
                FROM RECIPE_INGREDIENTS ri
                JOIN INGREDIENTS g ON ri.ingredient_id = g.ingredient_id
                WHERE ri.recipe_id = ?
                """,
                (recipe_id,)
            )
            for ir in cur.fetchall():
                recipe["ingredients"].append({
                    "ingredient_id": int(ir[0]),
                    "name": str(ir[1]),
                    "category": str(ir[2]),
                    "quantity": float(ir[3]) if ir[3] is not None else None,
                    "unit": str(ir[4]) if ir[4] else "pieces",
                    "is_optional": bool(ir[5])
                })

            return recipe

    def list_recipes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recipes in the master catalogue."""
        with self.manager.cursor() as cur:
            cur.execute(
                f"""
                SELECT r.recipe_id, r.name, r.description, r.cuisine,
                       r.prep_minutes, r.cook_minutes, r.servings, r.dietary_tags,
                       COUNT(ri.ingredient_id) as ing_count
                FROM RECIPES r
                LEFT JOIN RECIPE_INGREDIENTS ri ON r.recipe_id = ri.recipe_id
                GROUP BY r.recipe_id, r.name, r.description, r.cuisine,
                         r.prep_minutes, r.cook_minutes, r.servings, r.dietary_tags
                ORDER BY r.recipe_id ASC
                FETCH FIRST {limit} ROWS ONLY
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "recipe_id": int(r[0]),
                    "name": str(r[1]),
                    "description": str(r[2]),
                    "cuisine": str(r[3]),
                    "prep_minutes": int(r[4]),
                    "cook_minutes": int(r[5]),
                    "servings": int(r[6]),
                    "dietary_tags": str(r[7]) if r[7] else "",
                    "ingredient_count": int(r[8])
                }
                for r in rows
            ]

    def save_recipe_embedding(
        self,
        recipe_id: int,
        vector: List[float],
        model_name: str,
        dimension: int,
        text_hash: str
    ) -> None:
        """Persist embedding vector in Db2 RECIPE_EMBEDDINGS."""
        vector_str = json.dumps(vector)
        with self.manager.cursor() as cur:
            cur.execute("SELECT recipe_id FROM RECIPES WHERE recipe_id = ?", (recipe_id,))
            if not cur.fetchone():
                return
            # Upsert or replace
            cur.execute("DELETE FROM RECIPE_EMBEDDINGS WHERE recipe_id = ?", (recipe_id,))
            cur.execute(
                """
                INSERT INTO RECIPE_EMBEDDINGS (
                    recipe_id, embedding_vector, embedding_model, embedding_dimension, embedded_text_hash
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (recipe_id, vector_str, model_name, dimension, text_hash)
            )

    def get_all_embeddings(self) -> List[Dict[str, Any]]:
        """Retrieve all recipe embeddings from Db2 for candidate scoring."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                SELECT recipe_id, embedding_vector, embedding_model, embedding_dimension
                FROM RECIPE_EMBEDDINGS
                """
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "recipe_id": int(r[0]),
                    "embedding": json.loads(r[1]),
                    "model": str(r[2]),
                    "dimension": int(r[3])
                })
            return results
