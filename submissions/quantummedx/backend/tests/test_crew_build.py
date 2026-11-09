"""Builds the real CrewAI crew (no network, no LLM call). Proves 5 agents, 5 sequential tasks and tool wiring.
Does NOT prove LLM behaviour: that needs a live key."""
import pytest

pytest.importorskip("crewai")


def test_crew_has_five_agents_and_tools(monkeypatch):
    from crewai import LLM, Process
    from app.agents.crew import build_crew
    from app.agents.tools import AGENTS, Toolbox

    box = Toolbox(repo=None, dataset={"dataset_id": 1, "storage_ref": "x"}, target="target", run_id=1)
    crew = build_crew(box, LLM(model="openai/gpt-4o-mini", api_key="dummy-not-used"))
    assert [a.role for a in crew.agents] == list(AGENTS.values())
    assert len(crew.tasks) == 5 and crew.process == Process.sequential
    names = {t.name for a in crew.agents for t in a.tools}
    assert names == {"check_data_quality", "analyze_feature_patterns", "train_classical_model", "run_quantum_vqc", "fetch_stored_results"}
