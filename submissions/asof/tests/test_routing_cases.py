"""The routing evaluation's cases: well formed, labelled with real documents, and the test split frozen."""

from __future__ import annotations

import pytest

from asof.domains import DOC_IDS
from asof.eval import routing_cases as rc


def test_the_routing_test_split_is_frozen():
    assert rc.split_sha256("routing-test") == rc.FROZEN["routing-test"]


@pytest.mark.parametrize("split", sorted(rc.SPLITS))
def test_every_case_is_well_formed(split):
    cases = rc.load(split)
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        assert c.expected in (*DOC_IDS, rc.ASK) and c.expected in c.acceptable, c.id
        assert set(c.acceptable) <= {*DOC_IDS, rc.ASK}, c.id
        assert c.question.strip() and c.draft.strip() and c.note.strip(), c.id
        assert (c.expected == rc.ASK) == (c.category in ("ambiguous", "out_of_scope", "mixed")), c.id


def test_the_test_split_covers_both_documents_and_the_ask_cases():
    cases = rc.load("routing-test")
    assert len(cases) == 40
    by = {e: sum(c.expected == e for c in cases) for e in (*DOC_IDS, rc.ASK)}
    # The split was pinned with two documents; the third (Indian Railways) has no cases in it.
    assert by == {"AURELIA-CSP": 15, "FERNHOLLOW-FEES": 15, "INDIAN-RAIL-REFUNDS": 0, rc.ASK: 10}


def test_routing_outcomes_separate_the_dangerous_error_from_the_safe_one():
    from asof.eval.routing import outcome

    A, B, ASK = "AURELIA-CSP", "FERNHOLLOW-FEES", rc.ASK
    assert outcome(A, (A,), A) == "correct"
    assert outcome(A, (A,), B) == "misrouted"   # checked against the other company's policy
    assert outcome(A, (A,), ASK) == "asked"     # safe, costs a person's time
    assert outcome(ASK, (ASK,), B) == "guessed"
    assert outcome(A, (A, ASK), ASK) == "correct"  # an injection case accepts a person too


def test_the_routing_summary_and_report_count_what_happened():
    from asof.eval.routing import render, summarize

    rows = [{"id": "R1", "category": "clear_airline", "expected": "AURELIA-CSP", "got": "AURELIA-CSP", "outcome": "correct",
             "method": "db2", "agent": None, "latency_ms": 10},
            {"id": "R2", "category": "trap", "expected": "FERNHOLLOW-FEES", "got": rc.ASK, "outcome": "asked",
             "method": "ask", "agent": None, "latency_ms": 30},
            {"id": "R3", "category": "ambiguous", "expected": rc.ASK, "got": "AURELIA-CSP", "outcome": "guessed",
             "method": "db2+agent", "agent": {"document": "AURELIA-CSP"}, "latency_ms": 900}]
    s = summarize(rows)
    assert (s["routable"], s["routed_right"], s["misrouted"], s["asked"]) == (2, 1, 0, 1)
    assert (s["ask_cases"], s["ask_cases_asked"], s["guessed"], s["agent_calls"]) == (1, 0, 1, 1)
    assert s["methods"] == {"db2": 1, "db2+agent": 1, "ask": 1} and s["latency_ms_p50"] == 30
    report = render([{"split": "routing-test", "label": "test run", "started_at": "2026-11-08T12:00:00", "git_commit": "abc1234",
                      "summary": s, "rows": rows}])
    assert "| **Misrouted** (other document) | **0 of 2** |" in report
    assert "`R3` (ambiguous) expected ASK, got AURELIA-CSP via db2+agent, agent said AURELIA-CSP" in report


def test_every_model_allowed_to_route_has_a_clean_run_on_the_pinned_split():
    """ASOF_ROUTER_AGENT=auto lets only router.MEASURED models run the routing agent: each must have a shipped run on
    the frozen test split, at its pinned SHA-256, that misrouted nothing and guessed on nothing."""
    import json
    from pathlib import Path

    from asof.router import MEASURED

    runs = [json.loads(f.read_text()) for f in (Path(__file__).resolve().parents[1] / "docs" / "routing").glob("*.json")]
    clean = {r["model"] for r in runs if r["split"] == "routing-test" and r["model"]
             and r["cases_sha256"] == rc.FROZEN["routing-test"]
             and r["summary"]["misrouted"] == 0 and r["summary"]["guessed"] == 0}
    assert MEASURED and MEASURED <= clean
    measured_badly = {r["model"] for r in runs if r["split"] == "routing-test" and r["model"]
                      and (r["summary"]["misrouted"] or r["summary"]["guessed"])}
    assert not MEASURED & measured_badly  # a model with any unclean run is not allowed
