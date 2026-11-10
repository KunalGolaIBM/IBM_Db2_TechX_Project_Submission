"""Local embeddings for knowledge search.

V1 uses a deterministic hashing embedder. It needs
no model download, no torch, and no network. The
interface matches a sentence transformer embedder,
so a neural model can replace it later without
changing callers.

Dimension is 384 to match the planned Db2 VECTOR
column. Cosine distance works the same for both.
"""

from __future__ import annotations

import hashlib
import math
import re

_DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Deterministic 384 dim embedder. No dependencies."""

    def __init__(self, dim: int = _DIM) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed(self, text: str) -> tuple[float, ...]:
        """Embed text into a normalized vector."""
        vector = [0.0] * self.dim
        tokens = _TOKEN.findall(text.lower())
        if not tokens:
            return tuple(vector)
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dim
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


def cosine_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Cosine distance between two vectors. 0 is identical."""
    if len(left) != len(right):
        raise ValueError("vectors must have the same length")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    return 1.0 - (dot / (left_norm * right_norm))
