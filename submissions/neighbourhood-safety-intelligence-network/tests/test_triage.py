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
    ("A man with a knife is threatening people", "hazard", "P1_CRITICAL"),
    ("Someone is following me home, please help me", "sos", "P1_CRITICAL"),
    ("Neighbour fainted in the lift and needs a doctor", "medical", "P2_HIGH"),
    ("A masked man is trying door handles of parked cars", "suspicious_activity", "P2_HIGH"),
])
def test_triage_classification(text, category, priority):
    assert triage(text) == (category, priority)
