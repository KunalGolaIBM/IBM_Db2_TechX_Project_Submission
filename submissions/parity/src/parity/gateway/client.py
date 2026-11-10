"""The gateway itself.

One entry point for all model calls. It checks the
cache first, enforces budgets, tries providers in
order, and records usage. In replay mode it never
touches the network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable

from parity.gateway.cache import CacheStore
from parity.gateway.types import (
    CacheMissError,
    GatewayResponse,
    ProviderConfig,
    TokenBudget,
    UsageReport,
    cache_key,
)

Transport = Callable[[ProviderConfig, str, str], GatewayResponse]
_RETRYABLE = (429, 500, 502, 503, 504)


def _http_transport(provider: ProviderConfig, system: str, user: str) -> GatewayResponse:
    """Call one OpenAI compatible chat endpoint."""
    url = provider.base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    if provider.api_key:
        request.add_header("Authorization", f"Bearer {provider.api_key}")
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    text = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    return GatewayResponse(
        text=text,
        provider=provider.name,
        model=provider.model,
        tokens_in=int(usage.get("prompt_tokens", 0)),
        tokens_out=int(usage.get("completion_tokens", 0)),
    )


class Gateway:
    """Route model calls through cache, budget, and fallback."""

    def __init__(
        self,
        providers: list[ProviderConfig],
        cache: CacheStore,
        budget: TokenBudget | None = None,
        transport: Transport | None = None,
        replay_only: bool = False,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self._providers = providers
        self._cache = cache
        self._budget = budget or TokenBudget()
        self._transport = transport or _http_transport
        self._replay_only = replay_only
        self.report = UsageReport()

    def complete(self, agent: str, system: str, user: str) -> GatewayResponse:
        """Run one model call. Return the response."""
        prompt = f"{system}\n{user}"
        key = cache_key(agent, prompt, self._providers[0].model)
        cached = self._cache.get(key)
        if cached is not None:
            self.report.record(cached)
            return cached
        if self._replay_only:
            raise CacheMissError("replay mode cache miss. Run was not recorded.")
        self._budget.check(estimate=1000)
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                response = self._transport(provider, system, user)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in _RETRYABLE:
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                continue
            self._budget.record(response.tokens_in, response.tokens_out)
            self._cache.put(key, agent, response)
            self.report.record(response)
            return response
        raise RuntimeError(f"all providers failed: {last_error}")
