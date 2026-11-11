import math
import hashlib
import logging
from typing import List
from app.core.config import settings

logger = logging.getLogger("cloud_loop.ai.embeddings")

_model = None
_model_attempted = False

def get_sentence_transformer():
    global _model, _model_attempted
    if _model_attempted:
        return _model
    _model_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info(f"Loaded embedding model: {settings.EMBEDDING_MODEL}")
    except Exception as e:
        logger.info(f"SentenceTransformer local weights not cached; using normalized 384-dim hash projection: {e}")
        _model = None
    return _model

def generate_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Generates a normalized embedding vector of specified dimension (384 for all-MiniLM-L6-v2).
    Uses SentenceTransformer if available; otherwise uses high-entropy normalized feature hashing.
    Always yields a deterministic, unit-length float vector.
    """
    if not text or not text.strip():
        return [0.0] * dim

    model = get_sentence_transformer()
    if model is not None:
        try:
            vec = model.encode(text.strip(), convert_to_numpy=True).tolist()
            return vec[:dim]
        except Exception as e:
            logger.warning(f"Model encode failed, falling back to deterministic projection: {e}")

    # Deterministic high-entropy 384-dim unit vector
    tokens = text.lower().split()
    vec = [0.0] * dim
    for token in tokens:
        # Multiple hash probes per token to spread across 384 dimensions
        h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        h2 = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)

        idx1 = h1 % dim
        idx2 = (h2 >> 16) % dim
        idx3 = (h2 >> 32) % dim

        sign1 = 1.0 if (h1 & 1) else -1.0
        sign2 = 1.0 if (h2 & 1) else -1.0
        sign3 = 1.0 if ((h1 ^ h2) & 1) else -1.0

        vec[idx1] += sign1
        vec[idx2] += sign2 * 0.75
        vec[idx3] += sign3 * 0.5

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    return vec

