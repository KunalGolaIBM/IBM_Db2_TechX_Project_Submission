"""Agent structured outputs, verification independence, and CrewAI wiring."""
import pytest

from app.agents import deterministic as det
from app.agents.schemas import InvestigationFindings, RecallItem, RecallPlan, RiskAssessment, SupplyChainFindings, VerificationReport
from app.services import evidence as ev
from app.services.bootstrap import SAMPLE_LAB_REPORT
from app.services.demo import TOMATO_INCIDENT
from app.services.incidents import create_incident


@pytest.fixture(scope="module")
def ctx(db):
    inc = create_incident(db, {**TOMATO_INCIDENT, "is_demo": False}, "agent-test", "analyst")
    ev.ingest_document(db, filename="agent_test_" + SAMPLE_LAB_REPORT.name, data=SAMPLE_LAB_REPORT.read_bytes() + b"\n%agent-test",
                       uploaded_by="agent-test", role="analyst", incident_id=inc["incident_id"], doc_type="LAB_REPORT")
    c = {"incident": inc}
    logs = []
    c["investigation"] = det.investigation_agent(db, c, logs.append)
    c["supply_chain"] = det.supply_chain_agent(db, c, logs.append)
    c["risk"] = det.risk_agent(db, c, logs.append)
    c["recall_plan"] = det.recall_planning_agent(db, c, logs.append)
    c["verification"] = det.verification_agent(db, c, logs.append)
    c["logs"] = logs
    return c


def test_outputs_are_valid_structured_models(ctx):
    for key, model in [("investigation", InvestigationFindings), ("supply_chain", SupplyChainFindings), ("risk", RiskAssessment),
                       ("recall_plan", RecallPlan), ("verification", VerificationReport)]:
        obj = ctx[key]
        assert isinstance(obj, model)
        model.model_validate_json(obj.model_dump_json())  # round-trips through JSON (as stored in Db2)


def test_investigation_is_grounded_in_uploaded_report(ctx):
    inv = ctx["investigation"]
    assert inv.lab_confirmed and inv.supplier_id == "SUP-001"
    pos = [f for f in inv.lab_findings if f.positive]
    assert pos and all(f.page and f.document_id for f in pos)
    assert any("Salmonella" in f.snippet for f in pos)
    assert inv.conflicts, "supplier COA (PASS) vs lab report (positive) must be surfaced"


def test_supply_chain_agent_uses_db2_results(ctx):
    sc = ctx["supply_chain"]
    assert sc.queries_executed and all(q["query"] for q in sc.queries_executed)
    assert set(sc.finished_batch_ids) == {"PB-2026-1002", "PB-2026-1004", "PB-2026-1005", "PB-2026-1006", "PB-2026-1007", "PB-2026-1008", "PB-2026-1009"}


def test_plan_is_targeted_and_excludes_same_sku_batches(ctx):
    plan = ctx["recall_plan"]
    planned = {i.batch_id for i in plan.items}
    assert "PB-2026-1011" not in planned and "PB-2026-1013" not in planned
    assert {"PB-2026-1011", "PB-2026-1013"} <= {e.batch_id for e in plan.excluded_batches}
    assert all(i.reason and i.evidence_refs for i in plan.items)
    assert any(i.inclusion_basis == "PRECAUTIONARY" for i in plan.items)
    assert all("SIMULATED" in n.instruction for n in plan.notifications)


def test_verification_passes_db2_checks_with_warnings(ctx):
    v = ctx["verification"]
    assert v.verdict == "PASS_WITH_WARNINGS"
    assert v.requires_human_review is True
    assert not v.missing_from_plan and not v.extraneous_in_plan and not v.unsupported_claims


def test_verification_detects_injected_unrelated_item(db, ctx):
    bad = ctx["recall_plan"].model_copy(deep=True)
    bad.items.append(RecallItem(batch_id="PB-2026-1030", product_id="P-BIS", location_kind="RETAILER", location_ref="RTL-BLR-02",
                                quantity_units=10, priority="P1", inclusion_basis="DIRECT", reason="injected", evidence_refs=["x"]))
    v = det.verification_agent(db, ctx, lambda m: None, plan=bad)
    assert v.verdict == "FAIL" and "PB-2026-1030" in v.extraneous_in_plan


def test_verification_detects_dropped_batch(db, ctx):
    bad = ctx["recall_plan"].model_copy(deep=True)
    bad.items = [i for i in bad.items if i.batch_id != "PB-2026-1007"]
    v = det.verification_agent(db, ctx, lambda m: None, plan=bad)
    assert v.verdict == "FAIL" and "PB-2026-1007" in v.missing_from_plan


def test_verification_flags_invented_identifier(db, ctx):
    bad = ctx["recall_plan"].model_copy(deep=True)
    bad.summary += " Also recall PB-2026-9999 from lot XYZ-2026-123."
    v = det.verification_agent(db, ctx, lambda m: None, plan=bad)
    assert "PB-2026-9999" in v.unsupported_claims and v.verdict == "FAIL"


def test_crewai_crew_builds_with_db2_tools(db, monkeypatch):
    """Constructs real CrewAI Agent/Task/Crew objects (no LLM call is made)."""
    pytest.importorskip("crewai")
    from app.agents.crew import CrewRunner, NARRATIVES
    from app.core.config import Settings

    s = Settings(llm_provider="openai", llm_model="gpt-4o-mini", openai_api_key="sk-test-not-a-real-key")
    runner = CrewRunner(db, s)
    assert {t.name for t in runner.tools} == {"db2_trace_impact", "evidence_search"}
    crew = runner.build_step("supply_chain", {"source_ref": "TOM-2026-041"}, "context")
    assert len(crew.agents) == 1 and crew.tasks[0].output_pydantic is NARRATIVES["supply_chain"]
    # the Db2 tool returns real trace data
    out = next(t for t in runner.tools if t.name == "db2_trace_impact")._run("TOM-2026-041")
    assert "PB-2026-1007" in out


# ---------------------------------------------------------------- CrewAI execution with a local stub LLM
STUB_REPLIES = {
    "InvestigationNarrative": {"summary": "Lab report confirms Salmonella in TOM-2026-041.", "hypothesis": "Supplier-origin contamination.", "open_questions": ["Were drums D-11..D-19 from one harvest?"]},
    "SupplyChainNarrative": {"summary": "Db2 trace shows seven finished batches.", "notable_gaps": ["DST-05 has no onward records"]},
    "RiskNarrative": {"narrative": "Severity and wide retail distribution dominate the score."},
    "RecallNarrative": {"summary": "Targeted Class I recall.", "retailer_instruction_preamble": "URGENT FOOD SAFETY NOTICE."},
    "VerificationNarrative": {"summary": "Checks reviewed.", "additional_concerns": ["Confirm pasteuriser repair"]},
}


STUB_CALLS: list = []


def _stub_llm():
    from crewai import BaseLLM

    class StubLLM(BaseLLM):
        def call(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None, from_agent=None, response_model=None):
            STUB_CALLS.append(1)
            text = messages if isinstance(messages, str) else " ".join(str(m.get("content", "")) for m in messages)
            name = next(k for k in STUB_REPLIES if k in text)
            return "Thought: I now know the final answer\nFinal Answer: " + __import__("json").dumps(STUB_REPLIES[name])

    return StubLLM(model="stub-local")


def test_crewai_kickoff_produces_validated_narrative(db):
    pytest.importorskip("crewai")
    from app.agents.crew import CrewRunner, SupplyChainNarrative
    from app.core.config import Settings

    runner = CrewRunner(db, Settings(llm_provider="openai", llm_model="gpt-4o-mini", openai_api_key="sk-test"), llm=_stub_llm())
    out = runner.run_step("supply_chain", {"source_ref": "TOM-2026-041"}, "ctx")
    assert isinstance(out, SupplyChainNarrative) and "seven" in out.summary


def test_orchestrator_llm_mode_merges_narrative_but_keeps_db2_facts(db, monkeypatch):
    pytest.importorskip("crewai")
    from app.agents import crew, orchestrator
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai")
    monkeypatch.setattr(s, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(s, "openai_api_key", "sk-test")
    stub = _stub_llm()
    monkeypatch.setattr(crew, "build_llm", lambda settings: stub)
    inc = create_incident(db, {**TOMATO_INCIDENT, "title": "LLM-mode orchestrator test", "is_demo": True}, "llm-test", "analyst")
    res = orchestrator.start_investigation(db, inc["incident_id"], "llm-test", "analyst", background=False)
    assert res["mode"] == "CREWAI_LLM"
    run = orchestrator.get_run(db, res["run_id"])
    assert run["status"] == "COMPLETED" and run["mode"] == "CREWAI_LLM"
    by = {a["agent_name"]: a for a in run["agents"]}
    assert by["supply_chain"]["output"]["summary"] == "Db2 trace shows seven finished batches."
    assert "PB-2026-1007" in by["supply_chain"]["output"]["finished_batch_ids"]  # facts untouched
    assert all(n["instruction"].startswith("URGENT FOOD SAFETY NOTICE.") for n in by["recall_planning"]["output"]["notifications"])
    assert len(STUB_CALLS) >= 5
