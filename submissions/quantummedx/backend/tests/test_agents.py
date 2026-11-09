"""Agent pipeline tests (in-memory repo). Verify tool logging, report grounding and the number guardrail.
A live CrewAI/LLM run is NOT covered here: it needs a real LLM key."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agents.verify import allowed_numbers, unverified_numbers
from test_api_logic import FakeRepo, csv_bytes, signup, upload  # noqa: F401
from test_api_logic import client  # noqa: F401  (fixture)


class AgentRepo(FakeRepo):
    def __init__(self):
        super().__init__()
        self.runs, self.acts, self.reports = {}, [], {}

    def create_agent_run(self, did, uid, mode):
        i = next(self._ids); self.runs[i] = dict(run_id=i, dataset_id=did, started_by=uid, mode=mode, status="RUNNING", error_message=None); return i

    def finish_agent_run(self, i, status, error=None): self.runs[i].update(status=status, error_message=error)
    def log_activity(self, run_id, agent, tool, status, input_ref="", output_summary="", error=None):
        self.acts.append(dict(run_id=run_id, agent_name=agent, tool_name=tool, status=status, output_summary=output_summary, error_message=error))
    def get_run(self, i):
        r = self.runs.get(i)
        return dict(r, owner_id=self.datasets[r["dataset_id"]]["owner_id"]) if r else None
    def list_runs(self, owner, limit=50): return [r for r in self.runs.values() if owner is None or self.datasets[r["dataset_id"]]["owner_id"] == owner]
    def activities(self, i): return [a for a in self.acts if a["run_id"] == i]
    def save_report(self, run_id, did, title, body, status="FINAL"):
        i = next(self._ids); self.reports[i] = dict(report_id=i, run_id=run_id, dataset_id=did, title=title, body_md=body, status=status); return i
    def get_report(self, i):
        r = self.reports.get(i)
        return dict(r, owner_id=self.datasets[r["dataset_id"]]["owner_id"]) if r else None
    def list_reports(self, owner, limit=50): return list(self.reports.values())

    def comparison(self, did):  # the real repo returns richer columns; mimic them from stored results
        out = []
        for i, e in self.exps.items():
            if e["dataset_id"] == did and e["status"] == "COMPLETED":
                r = self.results[i]
                out.append(dict(experiment_id=i, model_family=e["model_family"], algorithm=e["algorithm"], accuracy=r["accuracy"],
                                precision_score=r["precision"], recall=r["recall"], f1_score=r["f1"], roc_auc=r["roc_auc"],
                                train_seconds=r["train_seconds"], infer_seconds=r["infer_seconds"], backend_info=r["backend_info"]))
        return sorted(out, key=lambda x: -x["f1_score"])


@pytest.fixture()
def aclient(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-which-is-long-enough")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    repo = AgentRepo()
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    yield TestClient(main.app), repo
    main.app.dependency_overrides.clear()


def test_guardrail_flags_invented_numbers():
    ok = allowed_numbers([dict(experiment_id=1, accuracy=0.9123, f1_score=0.9, precision_score=None, recall=None, roc_auc=None)])
    assert unverified_numbers("Accuracy was 0.9123 (91.23%).", ok) == []
    assert unverified_numbers("Accuracy was 0.9876.", ok) == ["0.9876"]


def test_deterministic_pipeline_end_to_end(aclient):
    c, repo = aclient
    h = signup(c, "hank")
    did = upload(c, h).json()["dataset_id"]
    r = c.post("/api/agents/run", headers=h, json={"dataset_id": did, "mode": "DETERMINISTIC"})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    assert c.get(f"/api/agents/runs/{run_id}", headers=h).json()["status"] == "COMPLETED"
    acts = c.get(f"/api/agents/activity/{run_id}", headers=h).json()
    agents = {a["agent_name"] for a in acts}
    assert agents == {"Data Intelligence Agent", "Clinical Data Analysis Agent", "Classical ML Agent", "Quantum ML Agent", "Research & Verification Agent"}
    assert all(a["status"] == "COMPLETED" for a in acts)
    rep = c.get("/api/reports/" + str(next(iter(repo.reports))), headers=h).json()
    assert rep["status"] == "FINAL" and "no LLM was used" in rep["body_md"]
    assert "All numbers in the narrative match stored results." in rep["body_md"]
    assert "logistic_regression" in rep["body_md"] and "vqc" in rep["body_md"]
    assert "does not show quantum advantage" in rep["body_md"]


def test_crewai_mode_refuses_without_llm_config(aclient, monkeypatch):
    c, _ = aclient
    for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    h = signup(c, "ivy")
    did = upload(c, h).json()["dataset_id"]
    r = c.post("/api/agents/run", headers=h, json={"dataset_id": did, "mode": "CREWAI"})
    assert r.status_code == 400 and "DETERMINISTIC" in r.json()["detail"]


def test_run_and_report_isolation(aclient):
    c, repo = aclient
    ha, hb = signup(c, "jack"), signup(c, "kim")
    did = upload(c, ha).json()["dataset_id"]
    run_id = c.post("/api/agents/run", headers=ha, json={"dataset_id": did, "mode": "DETERMINISTIC"}).json()["run_id"]
    assert c.get(f"/api/agents/runs/{run_id}", headers=hb).status_code == 404
    assert c.get(f"/api/agents/activity/{run_id}", headers=hb).status_code == 404
    assert c.post("/api/agents/run", headers=hb, json={"dataset_id": did, "mode": "DETERMINISTIC"}).status_code == 404
    rid = next(iter(repo.reports))
    assert c.get(f"/api/reports/{rid}", headers=hb).status_code == 404
