"""Provider fallback: a hosted model that fails hands the same call to local Ollama, and the
ledger's MODEL_INFO says so. Content from a working primary is never second-guessed."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fakes import ScriptedLLM, ZeroEmbeddings, claims, clause, judge, verdict

from asof.config import Settings
from asof.gate import Gate, GateRequest
from asof.llm import FallbackLLM, LLMError, build_llm
from asof.schemas import ExtractionResult


class Named(ScriptedLLM):
    def __init__(self, name, **kw):
        super().__init__(**kw)
        self.provider, self.model_name = name.split(":", 1)
        self.chat_model = object()

    @property
    def info(self):
        return f"{self.provider}:{self.model_name}"


def test_a_working_primary_is_used_and_recorded_as_is():
    primary = Named("openrouter:m", extract=[claims()])
    fb = FallbackLLM(primary, Named("ollama:q"))
    fb.begin_check()
    fb.structured(ExtractionResult, [])
    assert fb.info == "openrouter:m"


def test_a_failing_primary_hands_the_same_call_to_the_fallback():
    primary = Named("openrouter:m", extract=[LLMError("timed out")])
    local = Named("ollama:q", extract=[claims()])
    fb = FallbackLLM(primary, local)
    fb.begin_check()
    assert fb.structured(ExtractionResult, [("user", "x")]).value.claims == []
    assert local.calls == [(ExtractionResult, [("user", "x")])]
    assert fb.info == "openrouter:m (fallback ollama:q on 1 of 1 calls)"


def test_when_both_fail_the_error_names_both():
    fb = FallbackLLM(Named("openrouter:m", extract=[LLMError("timed out")]),
                     Named("ollama:q", extract=[LLMError("connection refused")]))
    with pytest.raises(LLMError, match="timed out.*fallback ollama:q also failed"):
        fb.structured(ExtractionResult, [])


def test_usage_resets_per_check():
    fb = FallbackLLM(Named("openrouter:m", extract=[LLMError("x"), claims()]), Named("ollama:q", extract=[claims()]))
    fb.begin_check()
    fb.structured(ExtractionResult, [])
    fb.begin_check()
    fb.structured(ExtractionResult, [])
    assert fb.info == "openrouter:m"


def test_the_gate_records_the_fallback_in_the_ledger_entry(monkeypatch):
    import asof.gate as gate_mod
    from asof.ledger import Appended

    on = date(2026, 6, 2)
    retro = "You can request the bereavement fare after travel."
    quote = "Retroactive requests are accepted within 90 days of the ticket's issue date"
    entries = []
    monkeypatch.setattr(gate_mod, "clauses_as_of", lambda *a, **k: [clause("BRV-002", on)])
    monkeypatch.setattr(gate_mod.ledger, "append",
                        lambda conn, entry, schema="ASOF": entries.append(entry) or Appended(1, "h" * 64, datetime(2026, 11, 6)))
    primary = Named("openrouter:m", extract=[LLMError("timed out")], judge=[judge(verdict(1, "SUPPORTED", "BRV-002", quote))])
    local = Named("ollama:q", extract=[claims((retro, "bereavement", "deadline"))])

    class Conn:
        def close(self):
            pass

    result = Gate(FallbackLLM(primary, local), ZeroEmbeddings(), connect=Conn).check(
        GateRequest("Can I apply after travel?", retro, on, "AURELIA-CSP", "api"))
    assert result.model_info == "openrouter:m (fallback ollama:q on 1 of 2 calls)"
    assert entries and entries[0].model_info == result.model_info


def test_build_llm_wraps_a_hosted_primary_unless_told_not_to():
    s = Settings(_env_file=None, openrouter_api_key="sk-or-test")
    assert isinstance(build_llm(s, provider="openrouter"), FallbackLLM)
    assert not isinstance(build_llm(s, provider="openrouter", fallback=False), FallbackLLM)
    assert not isinstance(build_llm(s, provider="ollama"), FallbackLLM)
    assert not isinstance(build_llm(Settings(_env_file=None, openrouter_api_key="sk", llm_fallback="none"),
                                    provider="openrouter"), FallbackLLM)
