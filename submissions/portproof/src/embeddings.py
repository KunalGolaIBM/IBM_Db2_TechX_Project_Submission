"""Local sentence-transformer embeddings.

Runs on CPU, needs no API key and costs nothing, so a judge can reproduce the
vector parts of PortProof offline. The model is loaded lazily, so importing this
module stays cheap for the unit tests that never embed anything.
"""
from __future__ import annotations

import re
from typing import Any

from langchain_core.embeddings import Embeddings

from .config import embedding_model_name

#: all-MiniLM-L6-v2 produces 384-dimensional vectors, matching VECTOR(384, FLOAT32).
EMBEDDING_DIM = 384


class LocalEmbeddings(Embeddings):
    """A LangChain ``Embeddings`` backed by sentence-transformers."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or embedding_model_name()
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [[float(x) for x in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


#: Token characters: SQL identifiers plus the ``-440`` style SQLCODE tokens.
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|-?\d+")


class DeterministicEmbeddings(Embeddings):
    """A seeded, dependency-free stand-in used by the fast tests.

    Deterministic, offline, and the same dimensionality as the real model, so
    tests can exercise the vector plumbing without downloading one.

    It is a *hashing vectoriser* (the hashing trick) over lowercased tokens, not
    a hash of the whole string. That distinction is the whole point: hashing the
    string would send two near-identical texts to orthogonal vectors, so
    nearest-neighbour recall would be indistinguishable from random and a test
    built on it would assert nothing. Bag-of-tokens preserves enough similarity
    for "a similar failure recalls the fix" to be a real assertion, while
    carrying none of the real model's semantics -- which is why production uses
    :class:`LocalEmbeddings`.
    """

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        import hashlib
        import math

        raw = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            # Signed hashing keeps collisions from systematically inflating
            # similarity between unrelated texts.
            sign = 1.0 if digest[4] & 1 else -1.0
            raw[bucket] += sign
        norm = math.sqrt(sum(x * x for x in raw))
        if norm == 0.0:  # no tokens at all; any unit vector will do
            raw[0], norm = 1.0, 1.0
        return [x / norm for x in raw]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
