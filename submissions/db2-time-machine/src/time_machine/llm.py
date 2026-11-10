"""Provider-agnostic LLM client with an offline fallback.

* ``anthropic`` - Anthropic Messages API (ANTHROPIC_API_KEY)
* ``openai``    - any OpenAI-compatible chat endpoint (OPENAI_API_KEY, OPENAI_BASE_URL) - also works with Ollama
* ``offline``   - no network; agents fall back to deterministic heuristics

The application never depends on the LLM for correctness: every LLM answer is validated,
and every agent has a deterministic fallback.
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional

import httpx

from .config import Settings

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, provider: str, model: str = "", api_key: str = "", base_url: str = "", timeout: float = 45.0):
        self.provider = provider
        self.model = model or DEFAULT_MODELS.get(provider, "")
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.calls = 0
        self.last_latency_ms: Optional[float] = None

    @property
    def enabled(self) -> bool:
        return self.provider != "offline"

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}" if self.enabled else "offline heuristics"

    @classmethod
    def from_settings(cls, s: Settings) -> "LLM":
        provider = s.llm_provider
        if provider == "auto":
            provider = "anthropic" if s.anthropic_api_key else ("openai" if s.openai_api_key else "offline")
        if provider == "anthropic" and not s.anthropic_api_key:
            provider = "offline"
        if provider == "openai" and not (s.openai_api_key or "localhost" in s.openai_base_url):
            provider = "offline"
        return cls(provider, s.llm_model, s.anthropic_api_key if provider == "anthropic" else s.openai_api_key,
                   s.openai_base_url)

    # -- calls ---------------------------------------------------------------
    def complete(self, system: str, user: str, max_tokens: int = 700) -> str:
        if not self.enabled:
            raise LLMError("offline mode")
        t0 = time.perf_counter()
        try:
            if self.provider == "anthropic":
                r = httpx.post(
                    "https://api.anthropic.com/v1/messages", timeout=self.timeout,
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": self.model, "max_tokens": max_tokens, "system": system,
                          "messages": [{"role": "user", "content": user}]})
                r.raise_for_status()
                text = "".join(b.get("text", "") for b in r.json().get("content", []))
            else:
                headers = {"content-type": "application/json"}
                if self.api_key:
                    headers["authorization"] = f"Bearer {self.api_key}"
                r = httpx.post(
                    f"{self.base_url}/chat/completions", timeout=self.timeout, headers=headers,
                    json={"model": self.model, "max_tokens": max_tokens, "temperature": 0,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # network, auth, quota, malformed response ...
            raise LLMError(str(exc)[:200]) from exc
        finally:
            self.calls += 1
            self.last_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return text

    def json(self, system: str, user: str, max_tokens: int = 700) -> dict:
        text = self.complete(system + "\nReply with a single JSON object and nothing else.", user, max_tokens)
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise LLMError("no JSON object in reply")
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"invalid JSON: {exc}") from exc


def offline_llm() -> LLM:
    return LLM("offline")
