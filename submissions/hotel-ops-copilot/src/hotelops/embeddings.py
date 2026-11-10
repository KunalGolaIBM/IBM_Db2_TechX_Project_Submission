"""Local sentence embeddings (384-d) via fastembed / ONNX.

The model is configurable with EMBEDDING_MODEL (IBM Granite or BGE-small, both 384-d).
It runs fully offline after the first model download, so guest reviews never leave the
machine for embedding.
"""
from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from .config import load_settings


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=load_settings().embedding_model)


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    return [list(map(float, v)) for v in _model().embed(list(texts), batch_size=64)]


def embed_query(text: str) -> list[float]:
    # BGE models recommend an instruction prefix for short retrieval queries; Granite does not use one.
    if "bge" in load_settings().embedding_model.lower():
        text = f"Represent this sentence for searching relevant passages: {text}"
    return [float(x) for x in next(iter(_model().embed([text])))]
