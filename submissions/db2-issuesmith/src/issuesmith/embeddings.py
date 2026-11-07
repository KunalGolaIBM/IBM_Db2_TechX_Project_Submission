"""Embedding backends (both implement LangChain's `Embeddings` interface).

* sentence-transformers (default): semantic, runs locally, 384 dimensions.
* hash: dependency-free feature hashing, also 384 dimensions. Used automatically
  if sentence-transformers is not installed, and in unit tests.

Both produce 384-dim vectors so the Db2 VECTOR(384, FLOAT32) columns stay valid.
If you switch backend later, run `python src/cli.py init-db --reset` and re-seed.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re

from langchain_core.embeddings import Embeddings

log = logging.getLogger(__name__)
DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")


class HashEmbeddings(Embeddings):
    """Deterministic bag-of-words + bigram feature hashing, L2-normalised."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN.findall(text.lower())
        grams = tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, lazy

        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.encode(texts, normalize_embeddings=True)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embeddings(backend: str, model_name: str) -> Embeddings:
    if backend == "hash":
        return HashEmbeddings()
    try:
        emb = SentenceTransformerEmbeddings(model_name)
        if len(emb.embed_query("probe")) != DIM:
            log.warning("Model %s is not %s-dim; using hash embeddings instead.", model_name, DIM)
            return HashEmbeddings()
        return emb
    except Exception as exc:  # ImportError, download failure, etc.
        log.warning("sentence-transformers unavailable (%s); using hash embeddings.", exc)
        return HashEmbeddings()


def to_vector_literal(vec: list[float]) -> str:
    """Format a Python list the way Db2's VECTOR(?, n, FLOAT32) expects."""
    return "[" + ",".join(f"{v:.7f}" for v in vec) + "]"
