"""Pipeline stages (pure, always run) and the LangChain composition (needs langchain-core)."""

from helpers import resource, session, snapshot, wait

from locklens.config import Settings
from locklens.models import DiagnosisResult, Severity
from locklens.pipeline import diagnostic_chain as dc

import pytest

SETTINGS = Settings.from_env({"DB2_PASSWORD": "pw"})


def payload(**kw):
    snap = snapshot(waits=[wait(9, 7, seconds=30)], sessions=[session(7, state="UOWWAIT")], resources=[resource()])
    return {"snapshot": snap, **kw}


# ---- stage functions (no LangChain needed) ----------------------------------------------
def test_prepare_input_rejects_wrong_type():
    with pytest.raises(TypeError):
        dc.prepare_input({"snapshot": "not a snapshot"})


def test_stages_compose_manually_to_a_result():
    state = dc.prepare_input(payload())
    state["findings"] = dc.apply_rules(state)
    result = dc.build_result(state, "manual")
    assert isinstance(result, DiagnosisResult) and result.narrative_source == dc.DETERMINISTIC
    assert any(f.finding_type == "IDLE_TRANSACTION_HOLDER" for f in result.findings)
    assert result.stages[-1] == "finalize" and "deterministic_narrative" in result.stages


def test_deterministic_narrative_lists_actionable_findings_only():
    state = dc.prepare_input(payload()); state["findings"] = dc.apply_rules(state)
    text = dc.deterministic_narrative_text(state["findings"])
    assert "need attention" in text
    assert "[WARNING]" in text or "[CRITICAL]" in text
    assert "[INFO]" not in text


def test_llm_input_contains_findings_but_no_secrets():
    state = dc.prepare_input(payload()); state["findings"] = dc.apply_rules(state)
    blob = dc.findings_to_json(state)["findings_json"]
    assert "BLOCKING_SESSION" in blob
    assert "password" not in blob.lower()


def test_run_diagnostics_works_without_langchain():
    original = dc.LANGCHAIN_AVAILABLE
    dc.LANGCHAIN_AVAILABLE = False
    try:
        r = dc.run_diagnostics(payload()["snapshot"], SETTINGS)
    finally:
        dc.LANGCHAIN_AVAILABLE = original
    assert r.pipeline.startswith("direct") and r.findings


# ---- LangChain composition (skipped automatically if langchain-core is not installed) ---
def test_langchain_pipeline_is_a_real_runnable_chain():
    pytest.importorskip("langchain_core")
    from langchain_core.runnables import Runnable

    chain = dc.build_pipeline()
    assert isinstance(chain, Runnable)
    result = chain.invoke({"snapshot": payload()["snapshot"]})
    assert isinstance(result, DiagnosisResult) and result.pipeline == "langchain"
    assert result.narrative_source == dc.DETERMINISTIC
    assert any(f.severity >= Severity.WARNING for f in result.findings)


def test_run_diagnostics_uses_langchain_when_available():
    pytest.importorskip("langchain_core")
    assert dc.run_diagnostics(payload()["snapshot"], SETTINGS).pipeline == "langchain"


def test_optional_llm_narrative_is_labelled_and_findings_are_unchanged():
    pytest.importorskip("langchain_core")
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    snap = payload()["snapshot"]
    base = dc.run_diagnostics(snap, SETTINGS)
    llm = FakeListChatModel(responses=["Application 7 is holding a lock that application 9 waits for."])
    r = dc.run_diagnostics(snap, SETTINGS, use_llm=True, llm=llm)
    assert r.narrative_source.startswith("llm:") and "Application 7" in r.narrative
    assert [f.to_dict() for f in r.findings] == [f.to_dict() for f in base.findings]


def test_failing_llm_falls_back_to_deterministic_text():
    pytest.importorskip("langchain_core")
    from langchain_core.runnables import RunnableLambda

    def boom(_):
        raise RuntimeError("ollama down")

    snap = payload()["snapshot"]
    r = dc.run_diagnostics(snap, SETTINGS, use_llm=True, llm=RunnableLambda(boom))
    assert r.narrative_source.startswith("deterministic-fallback") and "need attention" in r.narrative


def test_unavailable_ollama_degrades_without_error():
    pytest.importorskip("langchain_core")
    model, reason = dc.build_ollama_model(SETTINGS)
    r = dc.run_diagnostics(payload()["snapshot"], SETTINGS, use_llm=True, llm=None) if model is None else None
    if r is not None:
        assert r.narrative_source.startswith("deterministic-fallback") and reason
