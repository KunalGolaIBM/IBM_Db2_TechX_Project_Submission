"""Gateway types: providers, budgets, usage, cache.

All model calls go through one gateway. It enforces
token budgets, tries providers in order, and caches
every response so repeat runs cost zero tokens.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


class BudgetExceededError(RuntimeError):
    """Raised when a token budget is exhausted."""


class CacheMissError(RuntimeError):
    """Raised in replay mode when the cache has no entry."""


@dataclass(frozen=True)
class ProviderConfig:
    """One OpenAI compatible provider."""

    name: str
    base_url: str
    model: str
    api_key: str = ""


@dataclass(frozen=True)
class GatewayResponse:
    """One model response with usage."""

    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    from_cache: bool = False


@dataclass
class TokenBudget:
    """Token limits for one query or one run."""

    per_query: int = 8000
    per_run: int = 100000
    used_query: int = 0
    used_run: int = 0

    def check(self, estimate: int) -> None:
        """Raise when the estimate would break a budget."""
        if self.used_query + estimate > self.per_query:
            raise BudgetExceededError("per query token budget exceeded")
        if self.used_run + estimate > self.per_run:
            raise BudgetExceededError("per run token budget exceeded")

    def record(self, tokens_in: int, tokens_out: int) -> None:
        """Record actual usage."""
        total = tokens_in + tokens_out
        self.used_query += total
        self.used_run += total

    def reset_query(self) -> None:
        """Start a new query. Run total keeps counting."""
        self.used_query = 0


@dataclass
class UsageReport:
    """Usage totals for one run."""

    calls: int = 0
    cache_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)

    def record(self, response: GatewayResponse) -> None:
        """Add one response to the totals."""
        self.calls += 1
        if response.from_cache:
            self.cache_hits += 1
        self.tokens_in += response.tokens_in
        self.tokens_out += response.tokens_out
        self.by_provider[response.provider] = (
            self.by_provider.get(response.provider, 0) + 1
        )

    @property
    def cache_hit_rate(self) -> float:
        """Share of calls served from cache."""
        if self.calls == 0:
            return 0.0
        return self.cache_hits / self.calls

    def as_dict(self) -> dict:
        """JSON safe form for the run summary."""
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "by_provider": dict(self.by_provider),
        }


def cache_key(agent: str, prompt: str, model: str, settings: str = "") -> str:
    """Return a stable cache key for one call."""
    raw = f"{agent}\n{model}\n{settings}\n{prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
