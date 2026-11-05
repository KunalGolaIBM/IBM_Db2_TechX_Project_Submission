"""Recipe Dataset Seed and Embedding Builder for IBM Db2."""
import sys
import json
from pathlib import Path

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent / "src"
data_dir = current_dir.parent / "data"
sys.path.insert(0, str(src_dir))

from recipe_waste_optimizer.db.repositories.recipe_repo import RecipeRepository
from recipe_waste_optimizer.services.embedding_service import embedding_service
from recipe_waste_optimizer.config import settings


def seed_recipes():
    """Load sample recipes from JSON, save to Db2, and compute/persist embeddings."""
    recipes_file = data_dir / "sample_recipes.json"
    if not recipes_file.is_file():
        print(f"ERROR: Recipe dataset not found at {recipes_file}")
        sys.exit(1)

    with open(recipes_file, "r", encoding="utf-8") as f:
        recipes_data = json.load(f)

    print(f"Loaded {len(recipes_data)} recipes from {recipes_file.name}.")
    repo = RecipeRepository()

    count_inserted = 0
    count_embedded = 0

    for item in recipes_data:
        recipe_id = repo.create_recipe(item)
        count_inserted += 1

        # Build embedding text and generate dense vector
        text = embedding_service.build_recipe_text(item)
        text_hash = embedding_service.hash_text(text)
        vector = embedding_service.generate_embedding(text)

        repo.save_recipe_embedding(
            recipe_id=recipe_id,
            vector=vector,
            model_name=settings.EMBEDDING_MODEL,
            dimension=len(vector),
            text_hash=text_hash
        )
        count_embedded += 1
        print(f"  [+] Ingested & Embedded Recipe #{recipe_id}: '{item['name']}' ({len(vector)} dims)")

    print(f"\nSeed complete: {count_inserted} recipes and {count_embedded} embeddings persisted in IBM Db2.")


if __name__ == "__main__":
    seed_recipes()
