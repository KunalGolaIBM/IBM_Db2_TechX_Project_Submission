"""Local, offline embeddings.

`sentence-transformers/all-MiniLM-L6-v2` runs through the ONNX runtime via
fastembed: no API key, no GPU, no network at inference time. The model is
baked into the Docker image at build time so a reviewer can run the whole
stack offline after `docker compose up`.

384 dimensions on purpose - it maps one-to-one onto
``VECTOR(384, FLOAT32)`` in sql/01_schema.sql.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from .config import settings

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from fastembed import TextEmbedding

        _MODEL = TextEmbedding(model_name=settings.embedding_model)
    return _MODEL


def embed_documents(texts: Iterable[str]) -> List[List[float]]:
    texts = [t for t in texts if t and t.strip()]
    if not texts:
        return []
    vectors = [list(map(float, v)) for v in _model().embed(texts)]
    _assert_dim(vectors[0])
    return vectors


def embed_query(text: str) -> List[float]:
    vectors = embed_documents([text])
    if not vectors:
        raise ValueError("Cannot embed an empty query")
    return vectors[0]


def vector_literal(vector: List[float]) -> str:
    """Db2's VECTOR constructor takes a bracketed string of coordinates."""
    _assert_dim(vector)
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def _assert_dim(vector: List[float]) -> None:
    if len(vector) != settings.embedding_dim:
        raise ValueError(
            f"Embedding dimension mismatch: model produced {len(vector)} values "
            f"but the schema expects {settings.embedding_dim}. Update EMBEDDING_DIM "
            f"and the VECTOR(...) column together."
        )


def warm_up() -> Optional[int]:
    """Download/load the model and report the dimension (used by the CLI)."""
    vector = embed_query("warm up")
    return len(vector)
