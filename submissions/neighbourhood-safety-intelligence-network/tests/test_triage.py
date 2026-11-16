"""Triage rules: whole-word matching and the priority ladder."""
import pytest

from backend.app.ai.crewai.agents import crew_orchestrator


def triage(text):
    out = crew_orchestrator.run_incident_assistance_workflow(text)
    return out["parsed_category"], out["suggested_priority"]


@pytest.mark.parametrize("text, category, priority", [
    # Substring traps that the old rules got wrong
    ("A suspicious person is loitering near Gate 2", "suspicious_activity", "P3_MODERATE"),
    ("Kids are setting off fireworks in the park", "child_alert", "P2_HIGH"),
    ("Heavy rainfall flooded the underpass", "hazard", "P3_MODERATE"),
    ("Our business street has no lights", "hazard", "P3_MODERATE"),
    # Correct escalation
    ("My grandmother is not answering her phone since morning", "elder_welfare", "P2_HIGH"),
    ("Grandpa needs his medicines delivered this week", "elder_welfare", "P3_MODERATE"),
    ("A man with a knife is threatening people", "sos", "P1_CRITICAL"),
    ("Someone is following me home, please help me", "sos", "P1_CRITICAL"),
    ("Neighbour fainted in the lift and needs a doctor", "medical", "P2_HIGH"),
    ("A masked man is trying door handles of parked cars", "suspicious_activity", "P2_HIGH"),
])
def test_triage_classification(text, category, priority):
    assert triage(text) == (category, priority)


@pytest.mark.parametrize("text, expected_protocol", [
    ("My elderly neighbour has not answered her door or phone since last night. She lives alone.",
     "DOC-ELDER-003"),
    ("My son has not reached home from school and is not answering his phone", "DOC-CHILD-002"),
    ("The streetlight on our lane has been broken for a week", "DOC-HAZARD-004"),
])
def test_cited_protocol_matches_the_triaged_category(text, expected_protocol):
    from backend.app.ai.haystack.documents import APPROVED_CIVIC_SAFETY_DOCUMENTS
    titles = {d["id"]: d["title"] for d in APPROVED_CIVIC_SAFETY_DOCUMENTS}
    out = crew_orchestrator.run_incident_assistance_workflow(text)
    assert out["retrieved_civic_protocols"], "a protocol should be cited"
    assert out["retrieved_civic_protocols"][0]["title"] == titles[expected_protocol]


def test_unanswered_door_escalates_elder_welfare():
    assert triage("My elderly neighbour has not answered her door since last night") == ("elder_welfare", "P2_HIGH")


def test_crewai_flow_routes_critical_reports_to_escalation():
    out = crew_orchestrator.run_incident_assistance_workflow("A man with a knife is attacking people near Gate 2")
    assert out["suggested_priority"] == "P1_CRITICAL" and out["escalated"] is True
    assert out["workflow_steps"][:3] == ["intake:sos", "triage:P1_CRITICAL", "escalated"]
    assert out["immediate_safety_checklist"][0].startswith("Call 112")


def test_crewai_flow_standard_branch_does_not_escalate():
    out = crew_orchestrator.run_incident_assistance_workflow("The streetlight on Lane 4 is broken")
    assert out["escalated"] is False and "escalated" not in out["workflow_steps"]
    assert out["workflow_steps"][0] == "intake:hazard" and out["workflow_steps"][-1].startswith("knowledge:")


def test_crewai_flow_keeps_reported_location_when_text_has_none():
    out = crew_orchestrator.run_incident_assistance_workflow("Suspicious van parked for hours", location="Gate 7")
    assert out["extracted_location"] == "Gate 7"
