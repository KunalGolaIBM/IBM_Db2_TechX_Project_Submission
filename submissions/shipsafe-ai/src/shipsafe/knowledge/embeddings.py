"""Embedding providers for the Db2 vector stores.

Default: IBM Granite embeddings (`granite-embedding:30m`, 384 dimensions) served
locally by Ollama, through LangChain's `OllamaEmbeddings`.

`HashingEmbeddings` is a deterministic feature-hashing embedder used only when
the operator explicitly sets SHIPSAFE_EMBEDDINGS=hashing (for example on a CI
runner with no model server). It is never chosen silently.
"""

import hashlib
import math
import re
from typing import TYPE_CHECKING, List, Optional

from langchain_core.embeddings import Embeddings

if TYPE_CHECKING:  # pragma: no cover
    from ..config import LlmConfig

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "be", "for", "on", "with",
    "what", "how", "should", "must", "do", "does", "i", "we", "my", "our", "it", "that", "this",
    "by", "as", "at", "from", "into", "can", "any", "all",
}


class HashingEmbeddings(Embeddings):
    """Deterministic signed feature-hashing embeddings compatible with LangChain."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _features(self, text: str) -> List[str]:
        words = [w for w in _TOKEN.findall(text.lower()) if w not in _STOP]
        feats = list(words)
        feats += [f"{a}__{b}" for a, b in zip(words, words[1:])]
        for w in words:
            padded = f"#{w}#"
            feats += [f"c:{padded[i:i + 3]}" for i in range(len(padded) - 2)]
        return feats

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        for feat in self._features(text):
            h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dimension
            sign = 1.0 if h[4] & 1 else -1.0
            weight = 0.35 if feat.startswith("c:") else 1.0
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def build_embeddings(provider: str = "ollama", dimension: int = 384, llm: Optional["LlmConfig"] = None) -> Embeddings:
    """Return the configured LangChain embeddings. Raises if the provider is unknown."""
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        from ..config import LlmConfig

        cfg = llm or LlmConfig.from_env()
        return OllamaEmbeddings(model=cfg.embed_model, base_url=cfg.host)
    if provider == "hashing":
        return HashingEmbeddings(dimension=dimension)
    raise ValueError(f"Unknown embedding provider {provider!r}; use 'ollama' or 'hashing'.")
