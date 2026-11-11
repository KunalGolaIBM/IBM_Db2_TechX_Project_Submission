"""LangChain ``Embeddings`` bridge over our embedding adapter (M2.4).

DB2VS (langchain-db2) expects a ``langchain_core.embeddings.Embeddings``
object (its ``embedding_function`` argument). This module adapts our
:class:`EmbeddingModelAdapter` contract to that ABC without pulling
langchain into module import time — the import happens inside the factory,
so the offline application (mock mode) never loads langchain at all.

The wrapper delegates ``embed_documents`` / ``embed_query`` to the real
Ollama adapter, which owns retries, timeouts and normalization.
"""

from __future__ import annotations

from app.adapters.base import EmbeddingModelAdapter


def build_lc_embeddings(adapter: EmbeddingModelAdapter):
    """Return a ``langchain_core.embeddings.Embeddings`` wrapping ``adapter``.

    Raises ``AdapterUnavailableError``-safe ``ImportError`` semantics: the
    caller (real vector-store adapter) already verified package availability
    before calling.
    """
    from langchain_core.embeddings import Embeddings

    class AdapterEmbeddings(Embeddings):
        """Delegates to the application embedding adapter (Ollama in real mode)."""

        def __init__(self, wrapped: EmbeddingModelAdapter) -> None:
            self._wrapped = wrapped

        @property
        def model_name(self) -> str:
            return getattr(self._wrapped, "model_name", "unknown")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._wrapped.embed(texts).vectors

        def embed_query(self, text: str) -> list[float]:
            return self._wrapped.embed([text]).vectors[0]

    return AdapterEmbeddings(adapter)
