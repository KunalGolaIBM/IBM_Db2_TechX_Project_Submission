"""Embedding providers for the Db2 policy vector store.

`HashingEmbeddings` is the default: a deterministic, offline feature-hashing
embedder (word unigrams + bigrams + character trigrams, signed hashing, L2
normalised). It needs no model download and no network, which keeps ShipSafe
local-first and makes retrieval results reproducible in tests and demos.

Set SHIPSAFE_EMBEDDINGS=huggingface to use a sentence-transformers model through
`langchain-huggingface` instead (optional dependency).
"""

import hashlib
import math
import re
from typing import List

from langchain_core.embeddings import Embeddings

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


def build_embeddings(provider: str = "hashing", dimension: int = 384) -> Embeddings:
    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings  # optional extra

        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return HashingEmbeddings(dimension=dimension)
