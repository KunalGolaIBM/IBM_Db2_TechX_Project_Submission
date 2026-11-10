"""Tests for agent translation, the gateway path, and replay mode."""

import json
from pathlib import Path

from parity.cli import build_parser
from parity.config import load_llm_settings
from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonStatus
from parity.gateway.cache import InMemoryCache
from parity.gateway.client import Gateway
from parity.gateway.json_cache import JsonGatewayCache
from parity.gateway.types import (
    GatewayResponse,
    ProviderConfig,
    TokenBudget,
    cache_key,
)
from parity.pipeline import run_pipeline
from parity.report.html import render_json_summary

_SRC = "SELECT name FROM demo WHERE name ~ 'a'"


def executors():
    source = InMemoryExecutor({_SRC: result_set()})
    target = InMemoryExecutor(
        {'SELECT name FROM "DEMO" WHERE name LIKE \'a%\'': result_set()}
    )
    return source, target


def result_set():
    from parity.engine.result import ResultSet

    return ResultSet(columns=("name",), rows=(("alice",),))


def replay_gateway(cache, model="recorded-model"):
    provider = ProviderConfig(name="replay", base_url="http://localhost", model=model)
    return Gateway(providers=[provider], cache=cache, replay_only=True)


def store_hit(cache, db2_sql, model="recorded-model"):
    system_from = _system_user()
    key = cache_key("translator", system_from, model)
    cache.put(
        key,
        "translator",
        GatewayResponse(text=db2_sql, provider="recorded", model=model),
    )


def _system_user():
    from parity.agents.prompts import system_prompt
    from parity.agents.types import AgentRole

    system = system_prompt(AgentRole.TRANSLATOR)
    return f"{system}\nTranslate this PostgreSQL query to Db2:\n{_SRC}"


def test_untranslatable_without_gateway(tmp_path: Path):
    (tmp_path / "q.sql").write_text(_SRC + ";", encoding="utf-8")
    source, target = executors()
    reports = run_pipeline(tmp_path, source, target)
    assert reports[0].result.status is ComparisonStatus.NOT_COMPARABLE
    assert "no agent gateway configured" in reports[0].result.note


def test_replay_cache_hit_executes_agent_sql(tmp_path: Path):
    (tmp_path / "q.sql").write_text(_SRC + ";", encoding="utf-8")
    source, target = executors()
    gateway = replay_gateway(InMemoryCache())
    store_hit(gateway._cache, 'SELECT name FROM demo WHERE name LIKE \'a%\'')
    reports = run_pipeline(tmp_path, source, target, gateway=gateway)
    assert reports[0].result.status is ComparisonStatus.MATCH
    assert reports[0].db2_sql == 'SELECT name FROM "DEMO" WHERE name LIKE \'a%\''
    report = gateway.report
    assert report.calls == 1
    assert report.cache_hits == 1


def test_replay_cache_miss_is_not_comparable(tmp_path: Path):
    (tmp_path / "q.sql").write_text(_SRC + ";", encoding="utf-8")
    source, target = executors()
    gateway = replay_gateway(InMemoryCache())
    reports = run_pipeline(tmp_path, source, target, gateway=gateway)
    assert reports[0].result.status is ComparisonStatus.NOT_COMPARABLE
    assert "replay cache miss" in reports[0].result.note


def test_budget_exhausted_is_not_comparable(tmp_path: Path):
    (tmp_path / "q.sql").write_text(_SRC + ";", encoding="utf-8")
    source, target = executors()
    provider = ProviderConfig(name="p", base_url="http://localhost", model="m")
    budget = TokenBudget(per_query=1, per_run=1)
    gateway = Gateway(providers=[provider], cache=InMemoryCache(), budget=budget)
    reports = run_pipeline(tmp_path, source, target, gateway=gateway)
    assert reports[0].result.status is ComparisonStatus.NOT_COMPARABLE
    assert "token budget exhausted" in reports[0].result.note


def test_json_gateway_cache_roundtrip(tmp_path: Path):
    path = tmp_path / "cache.json"
    store = JsonGatewayCache(path)
    store.put(
        "key1",
        "translator",
        GatewayResponse(text="SELECT 1", provider="p", model="m", tokens_in=9, tokens_out=3),
    )
    loaded = JsonGatewayCache(path)
    response = loaded.get("key1")
    assert response is not None
    assert response.from_cache is True
    assert response.text == "SELECT 1"
    assert response.tokens_in == 9
    assert loaded.get("missing") is None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["key1"]["agent"] == "translator"


def test_live_path_stores_in_cache(tmp_path: Path):
    (tmp_path / "q.sql").write_text(_SRC + ";", encoding="utf-8")
    source, target = executors()
    provider = ProviderConfig(name="p", base_url="http://localhost", model="m")
    gateway = Gateway(providers=[provider], cache=InMemoryCache())
    gateway._transport = lambda prov, sys, user: GatewayResponse(
        text="SELECT name FROM demo WHERE name LIKE 'a%'",
        provider="p",
        model="m",
        tokens_in=10,
        tokens_out=5,
    )
    reports = run_pipeline(tmp_path, source, target, gateway=gateway)
    assert reports[0].result.status is ComparisonStatus.MATCH
    assert gateway.report.calls == 1
    assert gateway.report.cache_hits == 0


def test_load_llm_settings_defaults(monkeypatch):
    for name in ("PARITY_LLM_MODEL", "PARITY_LLM_BASE_URL", "PARITY_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = load_llm_settings()
    assert (settings.model, settings.base_url, settings.api_key) == (
        "recorded-model",
        "http://localhost",
        "",
    )
    assert settings.is_replay_only is True


def test_cli_replay_flags():
    args = build_parser().parse_args(
        ["run", "--dir", "samples", "--replay", "--llm-cache", "c.json"]
    )
    assert args.replay is True
    assert args.llm_cache == "c.json"
    assert args.bridge is False


def test_json_summary_llm_usage():
    from parity.gateway.types import UsageReport

    usage = UsageReport()
    usage.record(GatewayResponse(text="", provider="p", model="m", tokens_in=4, tokens_out=2))
    text = render_json_summary([], llm_usage=usage.as_dict())
    assert '"llm_usage"' in text
    assert '"calls": 1' in text
