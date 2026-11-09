import sys
import types
from pathlib import Path

import pytest

from civiclens.agent import fallback
from civiclens.agent.llm import LlmConfigError, build_llm
from civiclens.config import Settings
from civiclens.domain.investigation_models import RunRequest


@pytest.mark.parametrize(
    ("count", "sev", "expected"),
    [(10, 3.0, 1), (7, 3.0, 2), (4, 3.0, 3), (2, 3.0, 4), (1, 3.0, 5), (7, 3.57, 2), (3, 1.0, 5)],
)
def test_priority_rules(count, sev, expected):
    assert fallback.priority_for(count, sev) == expected


def test_confidence_is_monotonic_and_bounded():
    vals = [fallback.confidence_for(n) for n in (1, 3, 7, 50)]
    assert vals == sorted(vals) and 0 < vals[0] and vals[-1] < 1


class FakeTool:
    def __init__(self, data, ok=True):
        self.data, self.ok, self.calls = data, ok, []

    def invoke(self, args):
        self.calls.append(args)
        return {"ok": self.ok, "data": self.data}


def test_fallback_builds_labelled_grounded_drafts():
    spot = {"geo_cell": "C1_2", "category": "POTHOLE", "complaint_count": 7, "avg_severity": 3.6,
            "first_reported_at": "2026-10-01", "last_reported_at": "2026-10-20"}  # fmt: skip
    tools = {"hotspot_summary": FakeTool([spot]),
             "search_complaints": FakeTool([{"complaint_id": 4}, {"complaint_id": 9}])}  # fmt: skip
    res = fallback.run_fallback(tools, RunRequest(mode="fallback", max_hotspots=1))
    d = res.drafts[0]
    assert d.evidence_ids == [4, 9] and res.seen_ids == {4, 9}
    assert d.priority == 1 and "[RULE-BASED, NO LLM]" in d.rationale
    assert tools["search_complaints"].calls[0]["geo_cell"] == "C1_2"


def test_fallback_with_no_hotspots_returns_no_drafts():
    res = fallback.run_fallback(
        {"hotspot_summary": FakeTool([]), "search_complaints": FakeTool([])}, RunRequest()
    )
    assert res.drafts == []


@pytest.mark.parametrize(
    ("provider", "module", "cls", "settings"),
    [
        ("openai", "langchain_openai", "ChatOpenAI", {"openai_api_key": "k"}),
        ("anthropic", "langchain_anthropic", "ChatAnthropic", {"anthropic_api_key": "k"}),
        ("watsonx", "langchain_ibm", "ChatWatsonx", {"watsonx_apikey": "k", "watsonx_project_id": "p"}),
    ],
)
def test_a_client_that_cannot_be_created_is_a_config_error_naming_only_the_exception_class(
    monkeypatch, provider, module, cls, settings
):
    """The watsonx client authenticates against IBM when it is created, so a wrong key fails right here. Whatever
    the SDK raises must surface as LlmConfigError, never as a raw exception, and without the SDK's text."""

    class Boom:
        def __init__(self, **kwargs):
            raise ConnectionError("401 Unauthorized for key sk-FAKE-0123456789")

    fake = types.ModuleType(module)
    setattr(fake, cls, Boom)
    monkeypatch.setitem(sys.modules, module, fake)
    with pytest.raises(LlmConfigError) as exc:
        build_llm(Settings(_env_file=None, llm_provider=provider, llm_model="m", **settings))
    assert "ConnectionError" in str(exc.value) and provider in str(exc.value)
    assert "sk-FAKE" not in str(exc.value) and exc.value.__cause__ is None


def test_llm_provider_none_returns_no_client():
    assert build_llm(Settings(_env_file=None)) is None


@pytest.mark.parametrize(
    ("provider", "extra"),
    [("openai", {}), ("anthropic", {}), ("watsonx", {"watsonx_apikey": "k"})],
)
def test_missing_credentials_or_model_raise_config_error(provider, extra):
    with pytest.raises(LlmConfigError, match="LLM_MODEL"):
        build_llm(Settings(_env_file=None, llm_provider=provider, **extra))
    with pytest.raises(LlmConfigError):
        build_llm(Settings(_env_file=None, llm_provider=provider, llm_model="m", **extra))


@pytest.mark.parametrize(
    ("provider", "key_field", "cls"),
    [("openai", "openai_api_key", "ChatOpenAI"), ("anthropic", "anthropic_api_key", "ChatAnthropic")],
)
def test_client_construction_without_network(provider, key_field, cls):
    """Construction only (dummy key, no request is made). Does NOT prove the provider works."""
    pytest.importorskip({"openai": "langchain_openai", "anthropic": "langchain_anthropic"}[provider])
    handle = build_llm(
        Settings(
            _env_file=None, llm_provider=provider, llm_model="test-model", **{key_field: "dummy-not-a-key"}
        )
    )
    assert type(handle.model).__name__ == cls and handle.label == f"{provider}:test-model"


SCRIPTS = Path(__file__).resolve().parents[2] / "src/backend/scripts"


# ---- scripts/llm_preflight.py: a no-cost, no-network readiness check ------------------------------------------------
def _preflight(monkeypatch, capsys, **settings):
    import importlib

    monkeypatch.syspath_prepend(str(SCRIPTS))
    module = importlib.import_module("llm_preflight")
    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None, **settings))
    code = module.main()
    return code, capsys.readouterr().out


def test_preflight_is_blocked_when_no_provider_is_selected(monkeypatch, capsys):
    code, out = _preflight(monkeypatch, capsys)
    assert (
        code == 2
        and "BLOCKED" in out
        and "LLM_PROVIDER is 'none'" in out
        and "Nothing is claimed to be AI" in out
    )


def test_preflight_lists_what_is_missing_without_printing_any_value(monkeypatch, capsys):
    code, out = _preflight(
        monkeypatch,
        capsys,
        llm_provider="watsonx",
        llm_model="granite-test",
        watsonx_apikey="sk-FAKE-0123456789",
    )
    assert code == 2 and "BLOCKED" in out and "WATSONX_PROJECT_ID is not set" in out
    assert (
        "sk-FAKE" not in out and "granite-test" in out
    )  # the model name is configuration, a key is a secret


def test_preflight_ready_never_claims_the_credentials_work(monkeypatch, capsys):
    pytest.importorskip("langchain_openai")
    code, out = _preflight(
        monkeypatch, capsys, llm_provider="openai", llm_model="m", openai_api_key="sk-FAKE-0123456789"
    )
    assert code == 0 and "READY" in out and "NOT verified" in out and "explicit authorization" in out
    assert "sk-FAKE" not in out
