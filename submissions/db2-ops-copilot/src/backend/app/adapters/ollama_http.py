"""Shared HTTP plumbing for the REAL Ollama adapters (M2.3).

Responsibilities:
- one reused ``httpx.Client`` per adapter (keep-alive, connection pooling,
  single timeout policy, closed with the adapter),
- bounded retry with linear backoff for *transient* failures only
  (connection errors, timeouts, HTTP 5xx / 429). HTTP 4xx (bad request,
  model not found) is never retried — it cannot succeed by repeating,
- error normalization into the application error types.

Security/logging notes:
- prompts and embedding texts are NEVER logged here (only metadata:
  endpoint, model, status, attempt count, latency).
- the base URL is configuration, not a secret; no credentials exist in
  any Ollama request (Ollama runs locally without auth by default).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import AdapterUnavailableError, UpstreamTimeoutError

logger = logging.getLogger(__name__)

# Statuses worth retrying: transient server-side / rate-limit conditions.
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class OllamaHttpClient:
    """Owns the httpx.Client and the retry policy for one adapter."""

    def __init__(self, settings: Settings, client_label: str) -> None:
        self._settings = settings
        self._label = client_label
        self._client: httpx.Client | None = None

    # -- lifecycle -------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self._settings.ollama_base_url.rstrip("/")

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            # Total timeout is per-request; connect gets a short slice so a
            # dead host fails fast even when the total budget is large.
            connect_timeout = min(self._settings.ollama_timeout_ms / 1000, 5.0)
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    self._settings.ollama_timeout_ms / 1000,
                    connect=connect_timeout,
                ),
                headers={"User-Agent": "db2-ops-copilot/0.1"},
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()
        self._client = None

    # -- requests ---------------------------------------------------------
    def request_json(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Perform a JSON request with the configured retry policy.

        Raises ``UpstreamTimeoutError`` on exhausted timeouts and
        ``AdapterUnavailableError`` for every other failure — always with an
        actionable message and never with prompt content.
        """
        attempts = self._settings.ollama_max_retries + 1
        backoff_s = self._settings.ollama_retry_backoff_ms / 1000
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                response = self._ensure_client().request(
                    method, path, json=json_body
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "ollama %s %s timed out (attempt %d/%d, model=%s)",
                    method,
                    path,
                    attempt,
                    attempts,
                    json_body.get("model") if json_body else "-",
                )
                if attempt == attempts:
                    raise UpstreamTimeoutError(
                        f"Ollama request {method} {path} timed out after "
                        f"{self._settings.ollama_timeout_ms} ms "
                        f"({attempts} attempt(s))."
                    ) from exc
            except httpx.HTTPError as exc:
                # Transport-level failure (connection refused/reset/DNS).
                last_error = exc
                logger.warning(
                    "ollama %s %s transport error (attempt %d/%d): %s",
                    method,
                    path,
                    attempt,
                    attempts,
                    type(exc).__name__,
                )
                if attempt == attempts:
                    raise AdapterUnavailableError(
                        f"Ollama at {self.base_url} is unreachable "
                        f"({type(exc).__name__}). Start the Ollama service — "
                        "see docs/OLLAMA_INTEGRATION.md."
                    ) from exc
            else:
                elapsed_ms = (time.perf_counter() - started) * 1000
                if response.status_code in _RETRYABLE_STATUSES:
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                    logger.warning(
                        "ollama %s %s -> HTTP %d (attempt %d/%d, %.0f ms)",
                        method,
                        path,
                        response.status_code,
                        attempt,
                        attempts,
                        elapsed_ms,
                    )
                    if attempt == attempts:
                        raise AdapterUnavailableError(
                            f"Ollama at {self.base_url} returned HTTP "
                            f"{response.status_code} after {attempts} "
                            "attempt(s). Check the Ollama service logs."
                        )
                elif response.status_code >= 400:
                    # Non-retryable client error — surface sanitized detail.
                    detail = _safe_detail(response)
                    raise AdapterUnavailableError(
                        f"Ollama rejected {method} {path} with HTTP "
                        f"{response.status_code}: {detail}",
                        detail={"status": response.status_code, "endpoint": path},
                    )
                else:
                    logger.debug(
                        "ollama %s %s -> 200 in %.0f ms (attempt %d)",
                        method,
                        path,
                        elapsed_ms,
                        attempt,
                    )
                    try:
                        body = response.json()
                    except ValueError as exc:
                        raise AdapterUnavailableError(
                            f"Ollama returned a non-JSON response for {path}."
                        ) from exc
                    if not isinstance(body, dict):
                        raise AdapterUnavailableError(
                            f"Ollama returned an unexpected payload shape for {path}."
                        )
                    return body

            if backoff_s > 0 and attempt < attempts:
                time.sleep(backoff_s * attempt)

        # Defensive: loop always returns or raises; this satisfies the type.
        raise AdapterUnavailableError(
            f"Ollama request {method} {path} failed after {attempts} attempts.",
            detail={"last_error": type(last_error).__name__ if last_error else None},
        )


def _safe_detail(response: httpx.Response) -> str:
    """Extract a short, secret-free error detail from an Ollama response."""
    try:
        body = response.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, str):
                return err[:200]
    except ValueError:
        pass
    return response.text[:200] if response.text else "no detail"
