import json

from conftest import SAMPLES
from fakes import FakeKB, FakeRepo, ScriptedLLM
from issuesmith.agents.graph import Services, run_pipeline
from issuesmith.embeddings import HashEmbeddings
from issuesmith.llm import NoLLM


def _services(llm=None, repo=None):
    return Services(repo=repo or FakeRepo(), embeddings=HashEmbeddings(), llm=llm or NoLLM(), kb=FakeKB())


def test_full_graph_without_llm():
    svc = _services()
    raw = (SAMPLES / "01_wsl_runtime_install_failure.log").read_text()
    state = run_pipeline(svc, raw, "01.log")
    assert state["category"] == "RUNTIME_INSTALL"
    assert state["critic"]["passed"]
    assert "Winter2026" not in state["body"] and "alice" not in state["body"]
    assert [t["agent"] for t in state["trace"]] == [
        "sanitizer", "triage", "retriever", "deduplicator", "writer", "critic", "publisher"]
    assert len(svc.repo.runs) == 7 and svc.repo.drafts[-1]["final"]


def test_duplicate_detection():
    repo = FakeRepo()
    raw = (SAMPLES / "02_quick_restart_stopped_container.log").read_text()
    first = run_pipeline(_services(repo=repo), raw)
    second = run_pipeline(_services(repo=repo), raw)
    assert first.get("duplicate_of") is None
    assert second["duplicate_of"] == first["incident_id"]


def test_critic_sends_bad_llm_draft_back_to_writer():
    bad = json.dumps({"title": "Quick restart fails when the Db2 container is stopped in WSL",
                      "description": "The root cause is definitely a bug in the extension.",
                      "actual": ["Quick restart failed."], "expected": ["It works."],
                      "hypotheses": ["May assume running container."], "impact": "Please fix?"})
    good = json.dumps({"title": "Quick restart fails when the existing Db2 container is stopped in WSL",
                       "description": "Quick restart failed for a stopped container; a later full restart reported Db2 as accessible.",
                       "evidence_boundary": "The log shows the error but not the code-path defect.",
                       "actual": ['Podman reported "container state improper".'], "expected": ["Pick a restart path that fits a stopped container."],
                       "hypotheses": ["The quick path may assume a running container."],
                       "impact": "Could the maintainers review the stopped-container branch?"})
    llm = ScriptedLLM([bad, good])
    state = run_pipeline(_services(llm=llm), (SAMPLES / "02_quick_restart_stopped_container.log").read_text())
    assert state["round"] == 2
    assert state["critic"]["passed"]
    assert "reviewer rejected" in llm.calls[1]
    assert state["generated_by"] == "scripted"
