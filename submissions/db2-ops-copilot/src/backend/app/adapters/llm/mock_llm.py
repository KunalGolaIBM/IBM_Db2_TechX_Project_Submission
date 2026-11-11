"""Mock chat-model adapter — deterministic canned generations."""

from __future__ import annotations

import time

from app.adapters.base import ModelResult, ProbeResult
from app.core.config import Settings


class MockChatModelAdapter:
    """Offline stand-in for the Ollama chat endpoint."""

    probe_name = "llm"
    provider_id = "mock"
    mode = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._closed = False

    @property
    def model_name(self) -> str:
        return self._settings.ollama_llm_model

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
            detail=f"mock chat model ready (target: {self.model_name})",
        )

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> ModelResult:
        start = time.perf_counter()
        # Deterministic: identical input -> identical output.
        body = " ".join(prompt.split())[: max(max_tokens * 4, 64)]
        reply = f"[mock:{self.model_name}] {body}"
        return ModelResult(
            text=reply,
            model=self.model_name,
            latency_ms=(time.perf_counter() - start) * 1000,
            usage={"prompt_tokens": len(prompt) // 4, "completion_tokens": len(reply) // 4},
        )

    def close(self) -> None:
        self._closed = True
