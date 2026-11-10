"""Tests for the parity replay subcommand."""

from pathlib import Path

from parity.cli import build_parser
from parity.gateway.cache import InMemoryCache
from parity.gateway.client import Gateway
from parity.gateway.types import GatewayResponse, ProviderConfig


def test_replay_parser_defaults():
    args = build_parser().parse_args(["replay", "--dir", "samples", "--cache", "c.json"])
    assert args.command == "replay"
    assert args.dir == "samples"
    assert args.cache == "c.json"
    assert args.out == "parity-report.html"
    assert args.bridge is False


def test_replay_gateway_never_calls_transport(tmp_path: Path):
    calls = []

    def fail(provider, system, user):
        calls.append(user)
        raise AssertionError("transport must not be called in replay")

    provider = ProviderConfig(name="replay", base_url="http://localhost", model="recorded-model")
    gateway = Gateway(providers=[provider], cache=InMemoryCache(), transport=fail, replay_only=True)
    from parity.engine.executor import InMemoryExecutor
    from parity.engine.result import ResultSet
    from parity.pipeline import run_pipeline

    src = "SELECT name FROM demo WHERE name ~ 'a'"
    (tmp_path / "q.sql").write_text(src + ";", encoding="utf-8")
    result_set = ResultSet(columns=("name",), rows=(("alice",),))
    source = InMemoryExecutor({src: result_set})
    target = InMemoryExecutor({'SELECT name FROM "DEMO" WHERE name LIKE \'a%\'': result_set})
    reports = run_pipeline(tmp_path, source, target, gateway=gateway)
    assert calls == []
    assert "replay cache miss" in reports[0].result.note
    assert reports[0].result.status.value == "NOT_COMPARABLE"


def test_replay_cache_hit_skips_transport(tmp_path: Path):
    from parity.agents.prompts import system_prompt
    from parity.agents.types import AgentRole
    from parity.engine.executor import InMemoryExecutor
    from parity.engine.result import ResultSet
    from parity.gateway.types import cache_key
    from parity.pipeline import run_pipeline

    src = "SELECT name FROM demo WHERE name ~ 'a'"
    system = system_prompt(AgentRole.TRANSLATOR)
    prompt = f"{system}\nTranslate this PostgreSQL query to Db2:\n{src}"
    cache = InMemoryCache()
    cache.put(
        cache_key("translator", prompt, "recorded-model"),
        "translator",
        GatewayResponse(text="SELECT name FROM demo WHERE name LIKE 'a%'", provider="recorded", model="recorded-model"),
    )

    def fail(provider, system, user):
        raise AssertionError("transport must not be called in replay")

    provider = ProviderConfig(name="replay", base_url="http://localhost", model="recorded-model")
    gateway = Gateway(providers=[provider], cache=cache, transport=fail, replay_only=True)
    (tmp_path / "q.sql").write_text(src + ";", encoding="utf-8")
    result_set = ResultSet(columns=("name",), rows=(("alice",),))
    source = InMemoryExecutor({src: result_set})
    target = InMemoryExecutor({'SELECT name FROM "DEMO" WHERE name LIKE \'a%\'': result_set})
    reports = run_pipeline(tmp_path, source, target, gateway=gateway)
    assert reports[0].result.status.value == "MATCH"
    assert gateway.report.cache_hits == 1
