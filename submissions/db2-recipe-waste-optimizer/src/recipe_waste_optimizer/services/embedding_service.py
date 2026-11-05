"""Embedding Service for Recipe Representation and Semantic Search.

Computes normalized dense vectors for recipe texts and user queries.
"""
import hashlib
import numpy as np
from typing import List, Dict, Any
import logging
from recipe_waste_optimizer.config import settings

logger = logging.getLogger("embedding_service")

# Global cache for sentence transformer model instance
_MODEL_INSTANCE = None


def get_embedding_model():
    """Lazy loader for sentence transformer embedding model."""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL_INSTANCE = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(f"Loaded SentenceTransformer: {settings.EMBEDDING_MODEL}")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer ({e}). Using deterministic hash vector fallback.")
            _MODEL_INSTANCE = "fallback"
    return _MODEL_INSTANCE


class EmbeddingService:
    """Computes and compares recipe embeddings."""

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL, dimension: int = settings.EMBEDDING_DIMENSION):
        self.model_name = model_name
        self.dimension = dimension

    def build_recipe_text(self, recipe: Dict[str, Any]) -> str:
        """Construct standard canonical text for recipe embedding."""
        ing_names = []
        for ing in recipe.get("ingredients", []):
            name = ing.get("name") if isinstance(ing, dict) else str(ing)
            ing_names.append(name)

        text = (
            f"Recipe: {recipe.get('name', '')}\n"
            f"Description: {recipe.get('description', '')}\n"
            f"Cuisine: {recipe.get('cuisine', '')}\n"
            f"Ingredients: {', '.join(ing_names)}\n"
            f"Dietary tags: {recipe.get('dietary_tags', '')}"
        )
        return text

    def hash_text(self, text: str) -> str:
        """Compute sha256 hash of text for caching and provenance."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def generate_embedding(self, text: str) -> List[float]:
        """Generate normalized embedding vector for input text."""
        model = get_embedding_model()
        if model != "fallback":
            try:
                emb = model.encode(text, normalize_embeddings=True)
                return [round(float(v), 6) for v in emb]
            except Exception as e:
                logger.warning(f"Embedding generation error: {e}. Falling back to hash vector.")

        # Deterministic fallback vector: generate normalized pseudo-random vector from text hash
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [round(float(v), 6) for v in vec]

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two unit-normalized vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        sim = float(dot / (norm_a * norm_b))
        # Clamp to [0, 1] range for normalized scoring
        return max(0.0, min(1.0, (sim + 1.0) / 2.0))


embedding_service = EmbeddingService()
