"""REAL Ollama chat-model adapter (M2 — Ollama REST API, ``/api/chat``).

Production behavior:
- one reused ``httpx.Client`` via :class:`OllamaHttpClient` (keep-alive),
- bounded retry with backoff for transient failures only (M2.3),
- request timeout from ``OLLAMA_TIMEOUT_MS``,
- response normalization into :class:`ModelResult` (text + token usage),
- structured logging of *metadata only* — model, endpoint, token counts,
  latency. Prompt and completion CONTENT is never logged,
- all failures raise ``AdapterUnavailableError`` / ``UpstreamTimeoutError``
  with actionable messages; never a silent mock fallback.

NEVER executed against a real Ollama server on the development machine
(no Ollama installation per the project constraint). Offline unit tests
exercise it with a mocked HTTP transport (backend/tests/test_ollama_unit.py).
"""

from __future__ import annotations

import logging
import time

from app.adapters.base import ModelResult, ProbeResult
from app.adapters.ollama_http import OllamaHttpClient
from app.core.config import Settings
from app.core.errors import AdapterUnavailableError

logger = logging.getLogger(__name__)


class OllamaChatAdapter:
    """Chat completions from a locally running Ollama server."""

    probe_name = "llm"
    provider_id = "ollama"
    mode = "real"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._closed = False
        self._http = OllamaHttpClient(settings, "chat")

    @property
    def base_url(self) -> str:
        return self._http.base_url

    @property
    def model_name(self) -> str:
        return self._settings.ollama_llm_model

    # -- probes -----------------------------------------------------------
    def list_models(self) -> tuple[set[str], str | None]:
        """Return the set of local model names, or an error string."""
        try:
            body = self._http.request_json("GET", "/api/tags")
        except AdapterUnavailableError as exc:
            return set(), exc.message
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            return set(), f"{type(exc).__name__}: {exc}"
        names = {
            model.get("name", "")
            for model in body.get("models", [])
            if isinstance(model, dict)
        }
        return names, None

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

        names, error = self.list_models()
        if error is not None:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"Ollama not reachable at {self.base_url} ({error}). "
                    "Install Ollama and start the service — see "
                    "docs/OLLAMA_INTEGRATION.md."
                ),
            )
        wanted = self.model_name
        if wanted not in names and not any(
            n == wanted or n.split(":")[0] == wanted.split(":")[0] for n in names
        ):
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=elapsed(),
                detail=(
                    f"Ollama is running but model '{wanted}' is not pulled "
                    f"(run: ollama pull {wanted})."
                ),
            )
        return ProbeResult(
            name=self.probe_name,
            status="ok",
            mode=self.mode,
            latency_ms=elapsed(),
            detail=f"Ollama ready at {self.base_url} (model: {wanted})",
        )

    # -- generation --------------------------------------------------------
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> ModelResult:
        if self._closed:
            raise AdapterUnavailableError("Ollama adapter is closed.")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        start = time.perf_counter()
        body = self._http.request_json("POST", "/api/chat", json_body=payload)
        latency_ms = (time.perf_counter() - start) * 1000

        message = body.get("message")
        if not isinstance(message, dict):
            raise AdapterUnavailableError(
                "Ollama /api/chat response is missing the 'message' object."
            )
        content = str(message.get("content", ""))

        usage: dict[str, int] = {}
        if "prompt_eval_count" in body:
            usage["prompt_tokens"] = int(body["prompt_eval_count"])
        if "eval_count" in body:
            usage["completion_tokens"] = int(body["eval_count"])

        # Metadata only — never prompt/completion content.
        logger.info(
            "ollama chat ok model=%s prompt_tokens=%s completion_tokens=%s "
            "latency_ms=%.0f",
            self.model_name,
            usage.get("prompt_tokens", "-"),
            usage.get("completion_tokens", "-"),
            latency_ms,
        )
        return ModelResult(
            text=content,
            model=self.model_name,
            latency_ms=latency_ms,
            usage=usage or None,
        )

    def close(self) -> None:
        self._closed = True
        self._http.close()
