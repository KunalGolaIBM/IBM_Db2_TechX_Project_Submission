"""Chat model factory with a quota-aware fallback chain.

Gemini by default; other LangChain providers are optional installs. Each Gemini model has
its own free-tier daily quota, so ``LLM_FALLBACK_MODELS`` lists models to switch to when
the current one reports its *daily* quota is exhausted. The switch is sticky for the
process, so later calls go straight to the working model.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections.abc import Callable
from functools import lru_cache

from .config import load_settings


class LlmNotConfigured(RuntimeError):
    """Raised when the selected provider has no API key; the rest of the app still works."""


TRANSIENT_RETRIES = 3


def _is_daily_quota(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return ("RESOURCE_EXHAUSTED" in text or "429" in text) and ("per day" in text or "PerDay" in text)


def _is_transient(exc: Exception) -> bool:
    """Per-minute rate limits and server hiccups: worth a short wait and a retry on the same model."""
    text = f"{type(exc).__name__}: {exc}"
    return any(s in text for s in ("RESOURCE_EXHAUSTED", "429", "500 INTERNAL", "503", "UNAVAILABLE",
                                   "DEADLINE_EXCEEDED", "RateLimit", "ServerError"))


def _retry_delay(exc: Exception) -> float | None:
    """The server's suggested retry delay ("retryDelay": "17s"), if any."""
    m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"](\d+(?:\.\d+)?)s", str(exc))
    return float(m.group(1)) if m else None


def friendly_llm_error(exc: Exception) -> str | None:
    """Turn provider quota / rate-limit errors into one actionable sentence (None if it is something else)."""
    text = f"{type(exc).__name__}: {exc}"
    if "RESOURCE_EXHAUSTED" in text or "429" in text or "RateLimit" in text:
        chain = ", ".join(model_chain())
        if _is_daily_quota(exc):
            return (f"The LLM provider's daily free-tier quota is used up for every configured model ({chain}). "
                    "Add more models to LLM_FALLBACK_MODELS, enable billing on the key, or try again after the "
                    "daily reset. Db2 features (approvals, dry run, time travel, radar) still work.")
        return "The LLM provider is rate-limiting requests; wait a minute and retry, or lower LLM_RPM in .env."
    return None


def _rate_limiter(rpm: float):
    if rpm <= 0:
        return None
    from langchain_core.rate_limiters import InMemoryRateLimiter

    # Smooths bursts (the briefing route makes many calls) instead of hitting HTTP 429.
    return InMemoryRateLimiter(requests_per_second=rpm / 60.0, check_every_n_seconds=0.1, max_bucket_size=2)


def model_chain() -> list[str]:
    """Primary model followed by the configured fallbacks (duplicates removed, order kept)."""
    s = load_settings().llm
    extra = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
    return list(dict.fromkeys([s.model, *extra]))


_exhausted: set[str] = set()
_lock = threading.Lock()


def active_model() -> str:
    """The model the next call will use (first one whose daily quota is not exhausted)."""
    chain = model_chain()
    return next((m for m in chain if m not in _exhausted), chain[0])


@lru_cache(maxsize=8)
def get_chat_model(name: str | None = None):
    s = load_settings().llm
    reason = s.missing_credentials()
    if reason:
        raise LlmNotConfigured(reason)
    model = name or s.model
    limiter = _rate_limiter(s.rpm)
    if s.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # Tool calling and structured output need the v1beta API; newer google-genai SDKs may default to v1.
        # Retries are handled in invoke_llm: the SDK would otherwise back off for minutes on a *daily*
        # quota error instead of letting the fallback chain switch model immediately.
        return ChatGoogleGenerativeAI(model=model, temperature=s.temperature, max_retries=0,
                                      rate_limiter=limiter, api_version=os.getenv("GEMINI_API_VERSION", "v1beta"))
    if s.provider == "openai":  # pip install langchain-openai
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=s.temperature, rate_limiter=limiter)
    if s.provider == "watsonx":  # pip install langchain-ibm
        from langchain_ibm import ChatWatsonx

        return ChatWatsonx(model_id=model, url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
                           project_id=os.getenv("WATSONX_PROJECT_ID"), params={"temperature": s.temperature},
                           rate_limiter=limiter)
    if s.provider == "ollama":  # pip install langchain-ollama
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, temperature=s.temperature)
    raise ValueError(f"Unsupported LLM_PROVIDER '{s.provider}' (gemini, openai, watsonx, ollama)")


def invoke_llm(make: Callable, messages, on_switch: Callable[[str, str], None] | None = None):
    """Invoke ``make(chat_model)`` (e.g. ``lambda m: m.bind_tools(tools)``), falling back down the model
    chain when a model's daily quota is exhausted. ``on_switch(old, new)`` is called on each switch."""
    last_exc: Exception | None = None
    for name in model_chain():
        if name in _exhausted:
            continue
        for attempt in range(TRANSIENT_RETRIES + 1):
            try:
                return make(get_chat_model(name)).invoke(messages)
            except Exception as exc:  # noqa: BLE001 - classified below, re-raised if not retryable
                last_exc = exc
                if _is_daily_quota(exc):
                    with _lock:
                        _exhausted.add(name)
                    nxt = active_model()
                    if on_switch and nxt not in _exhausted:
                        on_switch(name, nxt)
                    break  # next model in the chain
                if _is_transient(exc) and attempt < TRANSIENT_RETRIES:
                    time.sleep(min(30.0, _retry_delay(exc) or 4.0 * (attempt + 1)))
                    continue
                raise
    raise last_exc or RuntimeError("no LLM model available")
