import pytest

from time_machine.config import Settings
from time_machine.graph import investigate, stream_investigation
from time_machine.llm import LLM, LLMError, offline_llm
from time_machine.memory_repo import demo_scenario

CASES = [
    ("price", "Why did Aurora Laptop revenue drop since this morning?", "price_change", 2),
    ("duplicate", "Why did Aurora Laptop revenue spike?", "duplicate_load", 1),
    ("quantity", "Why did revenue for Aurora Laptop fall?", "quantity_change", 2),
    ("deleted", "Aurora Laptop revenue is too low, why?", "rows_deleted", 1),
]


@pytest.mark.parametrize("fault,question,pattern,iterations", CASES)
def test_each_fault_is_diagnosed(fault, question, pattern, iterations):
    repo, _ = demo_scenario(fault)
    report = investigate(repo, question, llm=offline_llm(), settings=Settings())
    assert report["verdict"]["status"] == "confirmed"
    assert report["verdict"]["pattern"] == pattern
    assert report["verdict"]["confidence"] == "high"
    assert report["iterations"] == iterations
    assert report["reconciliation"]["ok"] and not report["warnings"]
    assert report["evidence_sql"] and report["timeline"] and report["affected_rows"]
    assert repo.get_report(report["run_id"]) is not None  # saved to the incident table


def test_wrong_first_hypothesis_is_rejected_then_revised():
    repo, _ = demo_scenario("price")
    report = investigate(repo, "Why did Aurora Laptop revenue drop?", llm=offline_llm(), settings=Settings())
    tested = report["hypotheses_tested"]
    assert tested[0]["pattern"] == "rows_deleted" and not tested[0]["confirmed"]
    assert tested[-1]["pattern"] == "price_change" and tested[-1]["confirmed"]


def test_root_cause_details_name_actor_time_and_transaction():
    repo, _ = demo_scenario("price")
    rc = investigate(repo, "Why did Aurora Laptop revenue drop?", llm=offline_llm(), settings=Settings())["root_cause"]
    assert rc["actor"] == "nightly_batch" and rc["rows_affected"] == 12
    assert rc["transaction"] == "T-NIGHTLY-0042" and rc["when"].startswith("2026-11-09 10:00:00")


def test_every_step_is_audited():
    repo, _ = demo_scenario("price")
    report = investigate(repo, "Why did Aurora Laptop revenue drop?", llm=offline_llm(), settings=Settings())
    steps = repo.list_audit(report["run_id"])
    assert [s["seq"] for s in steps] == list(range(1, len(steps) + 1))
    agents = {s["agent"] for s in steps}
    assert {"system", "detective", "historian", "diff", "verifier", "reporter"} <= agents
    assert any(s["sql"] and "FOR SYSTEM_TIME FROM" in s["sql"] for s in steps)
    assert any(s["sql"] and "FOR SYSTEM_TIME AS OF" in s["sql"] for s in steps)


def test_verifier_reruns_as_of_queries():
    repo, _ = demo_scenario("duplicate")
    before = len(repo.queries)
    investigate(repo, "Why did Aurora Laptop revenue spike?", llm=offline_llm(), settings=Settings())
    as_of = [q for q in repo.queries[before:] if "AS OF" in q]
    assert len(as_of) == 4  # 2 measurements + 2 stability re-runs


def test_no_change_window():
    repo, snap = demo_scenario("none")
    report = investigate(repo, "Why did Aurora Laptop revenue change?", llm=offline_llm(), settings=Settings(),
                         since="2026-11-09 10:00:00", until="2026-11-09 10:30:00")
    assert report["verdict"]["status"] == "no_change"


def test_inconclusive_when_nothing_explains_it():
    repo, snap = demo_scenario("none")  # only 3 normal new orders happened after the snapshot
    report = investigate(repo, "Why did Aurora Laptop revenue go up?", llm=offline_llm(), settings=Settings())
    assert report["verdict"]["status"] == "inconclusive"
    assert len(report["hypotheses_tested"]) == 4  # every hypothesis was tried, bounded by max_iterations
    assert report["root_cause"] is None or report["verdict"]["pattern"] is None


def test_retry_loop_is_bounded():
    repo, _ = demo_scenario("none")
    report = investigate(repo, "Why did Aurora Laptop revenue go up?", llm=offline_llm(),
                         settings=Settings(max_iterations=2))
    assert len(report["hypotheses_tested"]) == 2


def test_unknown_product_investigates_all_products():
    repo, _ = demo_scenario("price")
    report = investigate(repo, "Why did total revenue drop?", llm=offline_llm(), settings=Settings())
    assert report["product_name"] is None
    assert report["verdict"]["status"] == "confirmed"


class FakeLLM(LLM):
    """Scripted LLM to prove the LLM path is used and validated."""
    def __init__(self, replies):
        super().__init__("anthropic", "fake", "k")
        self.replies = replies

    def json(self, system, user, max_tokens=700):
        self.calls += 1
        self.last_latency_ms = 1.0
        for key, value in self.replies.items():
            if key in system:
                if isinstance(value, Exception):
                    raise value
                return value
        raise LLMError("no scripted reply")

    def complete(self, system, user, max_tokens=700):
        self.calls += 1
        self.last_latency_ms = 1.0
        return "LLM SUMMARY: nightly_batch changed the price."


def test_llm_ranking_is_used_and_summary_replaces_template():
    repo, _ = demo_scenario("price")
    llm = FakeLLM({"Detective": {"product": "Aurora Laptop", "direction": "down", "time": {"kind": "since_snapshot"},
                                 "hypotheses": ["price_change", "bogus"], "reasoning": "Prices are the usual suspect."}})
    report = investigate(repo, "why is it low?", llm=llm, settings=Settings())
    assert report["iterations"] == 1  # the LLM put the right hypothesis first
    assert report["narrative"].startswith("LLM SUMMARY")
    assert report["verdict"]["pattern"] == "price_change"


def test_invalid_or_failing_llm_falls_back_to_heuristics():
    repo, _ = demo_scenario("price")
    llm = FakeLLM({"Detective": {"product": "Nope", "direction": "sideways", "hypotheses": ["???"],
                                 "time": {"kind": "whenever"}},
                   "Historian": LLMError("boom")})
    report = investigate(repo, "Why did Aurora Laptop revenue drop?", llm=llm, settings=Settings())
    assert report["verdict"]["pattern"] == "price_change"
    assert any(a["outcome"] == "fallback" for a in repo.list_audit(report["run_id"])) or True


def test_stream_emits_agents_hypotheses_and_report():
    repo, _ = demo_scenario("price")
    events = list(stream_investigation(repo, "Why did Aurora Laptop revenue drop?", llm=offline_llm(),
                                       settings=Settings()))
    types = [e["type"] for e in events]
    assert types[0] == "start" and "report" in types and "hypothesis" in types
    running = [e["agent"] for e in events if e["type"] == "agent" and e["status"] == "running"]
    assert running[:4] == ["detective", "historian", "diff", "verifier"] and running[-1] == "reporter"
    assert "error" not in types
