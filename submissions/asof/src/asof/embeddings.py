"""Local sentence embeddings (all-MiniLM-L6-v2, 384 dimensions) on CPU.

CPU is fast enough for this model and avoids torch's Metal backend, which crashes on
macOS 14 with torch 2.15. Vectors are L2-normalised, so cosine distance is well behaved.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings

DIM = 384


@lru_cache(maxsize=2)
def get_embeddings(model_name: str) -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def clause_embedding_text(title: str, clause_text: str) -> str:
    """What gets embedded for a clause: its title gives short claims something to match."""
    return f"{title}. {clause_text}"
