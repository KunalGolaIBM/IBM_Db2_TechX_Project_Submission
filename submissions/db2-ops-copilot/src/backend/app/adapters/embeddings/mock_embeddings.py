"""Mock embedding adapter — deterministic hash-based vectors (768-dim default).

Same text always yields the same vector, so retrieval behaviour is stable in
offline tests without downloading any model.
"""

from __future__ import annotations

import hashlib
import math
import time

from app.adapters.base import EmbeddingResult, ProbeResult
from app.core.config import Settings


def _deterministic_vector(text: str, dimensions: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        block = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(block), 4):
            values.append(int.from_bytes(block[i : i + 4], "big") / 0xFFFFFFFF)
            if len(values) == dimensions:
                break
        counter += 1
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class MockEmbeddingModelAdapter:
    """Offline stand-in for nomic-embed-text via Ollama."""

    probe_name = "embeddings"
    provider_id = "mock"
    mode = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._closed = False

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    @property
    def model_name(self) -> str:
        return self._settings.ollama_embed_model

    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="mock adapter closed",
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=0.0,
            detail=f"mock embedding model ready (target: {self.model_name}, {self.dimensions}-dim)",
        )

    def embed(self, texts: list[str]) -> EmbeddingResult:
        start = time.perf_counter()
        vectors = [_deterministic_vector(t, self.dimensions) for t in texts]
        return EmbeddingResult(
            vectors=vectors,
            model=self.model_name,
            dimensions=self.dimensions,
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    def close(self) -> None:
        self._closed = True
