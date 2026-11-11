"""REAL Ollama embedding-model adapter (M2 — Ollama REST API, ``/api/embed``).

Production behavior mirrors the chat adapter:
- one reused ``httpx.Client`` (keep-alive) via :class:`OllamaHttpClient`,
- bounded retry with backoff for transient failures only (M2.3),
- request timeout from ``OLLAMA_TIMEOUT_MS``,
- response normalization into :class:`EmbeddingResult` (vectors + dimension),
- structured metadata logging (model, count, dimension, latency) — input
  text is never logged,
- actionable ``AdapterUnavailableError`` / ``UpstreamTimeoutError`` on
  failure; no mock fallback, ever.

Required model: ``nomic-embed-text:v1.5`` (768 dimensions by default).
NEVER executed against a real Ollama server on the development machine.
"""

from __future__ import annotations

import logging
import time

from app.adapters.base import EmbeddingResult, ProbeResult
from app.adapters.ollama_http import OllamaHttpClient
from app.core.config import Settings
from app.core.errors import AdapterUnavailableError

logger = logging.getLogger(__name__)


class OllamaEmbeddingsAdapter:
    """Embeddings from nomic-embed-text (or configured model) via Ollama."""

    probe_name = "embeddings"
    provider_id = "ollama"
    mode = "real"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._closed = False
        self._http = OllamaHttpClient(settings, "embeddings")

    @property
    def base_url(self) -> str:
        return self._http.base_url

    @property
    def model_name(self) -> str:
        return self._settings.ollama_embed_model

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    # -- probes -----------------------------------------------------------
    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="Ollama adapter closed",
            )
        start = time.perf_counter()

        def elapsed() -> float:
            return (time.perf_counter() - start) * 1000

        try:
            body = self._http.request_json("GET", "/api/tags")
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"Ollama not reachable at {self.base_url} "
                    f"({type(exc).__name__}: {exc}). Install/start Ollama — "
                    "see docs/OLLAMA_INTEGRATION.md."
                ),
            )
        names = {
            m.get("name", "")
            for m in body.get("models", [])
            if isinstance(m, dict)
        }
        wanted = self.model_name
        if wanted not in names and not any(
            n.split(":")[0] == wanted.split(":")[0] for n in names
        ):
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"Ollama is running but embedding model '{wanted}' is not "
                    f"pulled (run: ollama pull {wanted})."
                ),
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=elapsed(),
            detail=f"Ollama embeddings ready (model: {wanted}, {self.dimensions}-dim)",
        )

    # -- embedding ---------------------------------------------------------
    def embed(self, texts: list[str]) -> EmbeddingResult:
        if self._closed:
            raise AdapterUnavailableError("Ollama adapter is closed.")
        if not texts:
            return EmbeddingResult(
                vectors=[],
                model=self.model_name,
                dimensions=self.dimensions,
                latency_ms=0.0,
            )
        start = time.perf_counter()
        body = self._http.request_json(
            "POST",
            "/api/embed",
            json_body={"model": self.model_name, "input": texts},
        )
        latency_ms = (time.perf_counter() - start) * 1000

        vectors = body.get("embeddings")
        if not isinstance(vectors, list) or not all(
            isinstance(v, list) for v in vectors
        ):
            raise AdapterUnavailableError(
                "Ollama embedding response did not contain an 'embeddings' list."
            )
        if len(vectors) != len(texts):
            raise AdapterUnavailableError(
                f"Ollama returned {len(vectors)} embeddings for {len(texts)} inputs."
            )
        dimensions = len(vectors[0]) if vectors and vectors[0] else self.dimensions
        logger.info(
            "ollama embed ok model=%s count=%d dimensions=%d latency_ms=%.0f",
            self.model_name,
            len(vectors),
            dimensions,
            latency_ms,
        )
        return EmbeddingResult(
            vectors=vectors,
            model=self.model_name,
            dimensions=dimensions,
            latency_ms=latency_ms,
        )

    def close(self) -> None:
        self._closed = True
        self._http.close()
