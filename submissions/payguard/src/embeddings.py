"""Text embeddings for Db2 vector search.

Two providers, same dimension, so the Db2 VECTOR column never changes shape:
  * gemini  - Google `gemini-embedding-001` (semantic, needs GEMINI_API_KEY)
  * local   - deterministic feature-hashing embedder (offline, zero dependencies)
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

import httpx

from config import settings

_TOKEN = re.compile(r"[a-z0-9@.$₦]+")


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class LocalHashEmbedder:
    """Signed feature hashing over word unigrams, bigrams and char trigrams.

    Captures lexical overlap ("gift card", "friends and family", "pay outside")
    well enough for scam-pattern matching without any model download.
    """

    name = "local-hash-v1"

    def __init__(self, dim: int):
        self.dim = dim

    def _features(self, text: str) -> Iterable[tuple[str, float]]:
        words = _TOKEN.findall(text.lower())
        for w in words:
            yield "w:" + w, 1.0
        for a, b in zip(words, words[1:]):
            yield f"b:{a}_{b}", 1.5
        for w in words:
            padded = f"#{w}#"
            for i in range(len(padded) - 2):
                yield "c:" + padded[i : i + 3], 0.3

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for feat, weight in self._features(text):
                h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "big")
                idx = h % self.dim
                sign = 1.0 if (h >> 63) & 1 else -1.0
                vec[idx] += sign * weight
            out.append(_normalize(vec))
        return out


class GeminiEmbedder:
    name = "gemini"

    def __init__(self, dim: int, api_key: str, model: str):
        self.dim, self.api_key, self.model = dim, api_key, model
        self.name = f"gemini:{model}:{dim}"

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents"
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 90):  # API batch limit is 100
            chunk = texts[start : start + 90]
            body = {
                "requests": [
                    {
                        "model": f"models/{self.model}",
                        "content": {"parts": [{"text": t[:8000]}]},
                        "taskType": task_type,
                        "outputDimensionality": self.dim,
                    }
                    for t in chunk
                ]
            }
            r = httpx.post(url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=60)
            r.raise_for_status()
            vectors += [_normalize(e["values"]) for e in r.json()["embeddings"]]
        return vectors


def get_embedder():
    provider = settings.embed_provider
    if provider == "gemini" or (provider == "auto" and settings.gemini_api_key):
        return GeminiEmbedder(settings.embed_dim, settings.gemini_api_key, settings.gemini_embed_model)
    return LocalHashEmbedder(settings.embed_dim)


def to_db2_vector(vec: list[float]) -> str:
    """Serialize to the string form accepted by Db2's VECTOR(str, dim, FLOAT32)."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
