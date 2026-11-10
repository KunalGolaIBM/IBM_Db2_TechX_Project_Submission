"""Tests for the gateway, budget, and cache key."""

import urllib.error

import pytest

from parity.gateway.cache import InMemoryCache
from parity.gateway.client import Gateway
from parity.gateway.types import (
    BudgetExceededError,
    CacheMissError,
    GatewayResponse,
    ProviderConfig,
    TokenBudget,
    UsageReport,
    cache_key,
)


def providers():
    return [
        ProviderConfig(name="first", base_url="http://first", model="m1"),
        ProviderConfig(name="second", base_url="http://second", model="m2"),
    ]


def ok_transport(text="hello"):
    def transport(provider, system, user):
        return GatewayResponse(text=text, provider=provider.name, model=provider.model, tokens_in=10, tokens_out=5)

    return transport


def test_cache_key_stable():
    assert cache_key("a", "p", "m") == cache_key("a", "p", "m")
    assert cache_key("a", "p", "m") != cache_key("a", "other", "m")


def test_budget_blocks_overuse():
    budget = TokenBudget(per_query=100, per_run=1000)
    with pytest.raises(BudgetExceededError):
        budget.check(101)


def test_budget_records_and_resets():
    budget = TokenBudget(per_query=100, per_run=1000)
    budget.record(10, 5)
    assert budget.used_query == 15
    budget.reset_query()
    assert budget.used_query == 0
    assert budget.used_run == 15


def test_gateway_calls_provider_and_caches():
    cache = InMemoryCache()
    gateway = Gateway(providers(), cache, transport=ok_transport())
    first = gateway.complete("agent", "sys", "user")
    assert first.text == "hello"
    assert first.from_cache is False
    second = gateway.complete("agent", "sys", "user")
    assert second.from_cache is True
    assert gateway.report.calls == 2
    assert gateway.report.cache_hits == 1
    assert gateway.report.cache_hit_rate == 0.5


def test_gateway_falls_back_on_rate_limit():
    def transport(provider, system, user):
        if provider.name == "first":
            raise urllib.error.HTTPError("url", 429, "slow down", None, None)
        return GatewayResponse(text="from second", provider=provider.name, model=provider.model)

    gateway = Gateway(providers(), InMemoryCache(), transport=transport)
    result = gateway.complete("agent", "sys", "user")
    assert result.provider == "second"


def test_gateway_replay_mode_blocks_network():
    gateway = Gateway(providers(), InMemoryCache(), transport=ok_transport(), replay_only=True)
    with pytest.raises(CacheMissError):
        gateway.complete("agent", "sys", "user")


def test_gateway_replay_hit_works():
    cache = InMemoryCache()
    gateway = Gateway(providers(), cache, transport=ok_transport())
    gateway.complete("agent", "sys", "user")
    replay = Gateway(providers(), cache, transport=ok_transport("never"), replay_only=True)
    assert replay.complete("agent", "sys", "user").text == "hello"


def test_gateway_requires_provider():
    with pytest.raises(ValueError):
        Gateway([], InMemoryCache())


def test_usage_report_empty():
    report = UsageReport()
    assert report.cache_hit_rate == 0.0
