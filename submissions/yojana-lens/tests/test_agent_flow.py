"""End-to-end graph execution with the database layer stubbed out.

This runs the real LangGraph, every node, the conditional edge and the
deterministic narration. Only the four Db2 calls are replaced, using rows
built from data/schemes.json with the same operator semantics as
SP_RECORD_TRACE. It is the closest thing to a live run that CI can do.
"""

from __future__ import annotations

import contextlib
import json
from collections import Counter

import pytest

from src import db
from src.agent import graph
from src.config import DATA_DIR

DEMO = (
    "I am a 34-year-old widow from a village in Uttar Pradesh. We are an OBC "
    "household. I farm two acres of our own land, our house is kutcha, and the "
    "household income is about 1.8 lakh a year. My daughter is in class 12. "
    "I have a bank account and a ration card."
)


def _compare(rule, facts):
    value = facts.get(rule["criterion_code"])
    if value is None:
        return "UNKNOWN"
    if rule["op"] == "eq":
        return "PASS" if str(value).lower() == str(rule["text"]).lower() else "FAIL"
    if rule["op"] == "in":
        return "PASS" if str(value).lower() in str(rule["text"]).lower().split(",") else "FAIL"
    if rule["op"] == "lte":
        return "PASS" if float(value) <= float(rule["num"]) else "FAIL"
    if rule["op"] == "gte":
        return "PASS" if float(value) >= float(rule["num"]) else "FAIL"
    return "UNKNOWN"


@pytest.fixture
def fake_db(monkeypatch):
    with open(DATA_DIR / "schemes.json", "r", encoding="utf-8") as handle:
        corpus = json.load(handle)

    from src.agent.extract import heuristic_normalize

    facts = heuristic_normalize(DEMO).facts
    scheme_meta = {}
    rows = []

    for scheme in corpus["schemes"]:
        chunk = scheme["chunks"][0]
        scheme_meta[scheme["scheme_id"]] = chunk
        for index, rule in enumerate(scheme["rules"], start=1):
            rows.append({
                "scheme_id": scheme["scheme_id"],
                "name": scheme["name"],
                "category": scheme["category"],
                "gov_level": scheme["level"],
                "state_code": scheme["state_code"],
                "benefit_summary": scheme["benefit_summary"],
                "source_url": scheme["source_url"],
                "rule_id": index,
                "criterion_code": rule["criterion_code"],
                "rule_op": rule["op"],
                "mandatory": 1 if rule["mandatory"] else 0,
                "observed_value": str(facts.get(rule["criterion_code"], "")) or None,
                "verdict": _compare(rule, facts),
                "clause_ref": rule["clause_ref"],
                "chunk_id": f"{scheme['scheme_id']}::{chunk['clause_ref']}",
                "narrative": None,
                "value_num": rule.get("num"),
                "value_text": rule.get("text"),
                "chunk_text": chunk["text"],
            })

    retrieved = [
        {
            "chunk_id": row["chunk_id"],
            "scheme_id": row["scheme_id"],
            "clause_ref": row["clause_ref"],
            "section": "Eligibility",
            "chunk_text": row["chunk_text"],
            "distance": 0.11,
        }
        for row in rows
    ]

    calls = {"record_trace": 0, "finish": None, "audit": []}

    @contextlib.contextmanager
    def fake_connect():
        yield None

    monkeypatch.setattr(graph.db, "connect", fake_connect)
    monkeypatch.setattr(graph.db, "create_profile", lambda *a, **k: None)
    monkeypatch.setattr(graph.db, "start_run", lambda *a, **k: None)
    monkeypatch.setattr(graph.db, "insert_facts", lambda *a, **k: None)
    monkeypatch.setattr(graph.db, "audit", lambda c, r, a, act, d="", sql="": calls["audit"].append(act))
    monkeypatch.setattr(graph, "embed_query", lambda text: [0.01] * 384)

    def fake_fetch_named(conn, name, values):
        if name == "retrieval":
            return retrieved
        if name == "scheme_trace":
            return rows
        return []

    def fake_record_trace(conn, run_id, profile_id):
        calls["record_trace"] += 1
        return len(rows)

    def fake_finish(conn, run_id, status, latency, candidates, summary):
        calls["finish"] = status

    monkeypatch.setattr(graph.db, "fetch_named", fake_fetch_named)
    monkeypatch.setattr(graph.db, "record_trace", fake_record_trace)
    monkeypatch.setattr(graph.db, "finish_run", fake_finish)
    monkeypatch.setattr(graph.db, "execute", lambda *a, **k: 0)

    return calls


def test_full_run_produces_a_balanced_decision_set(fake_db):
    state = graph.run(DEMO)

    assert state["status"] == "COMPLETED"
    assert state["counts"] == {
        "eligible": 6,
        "near_miss": 3,
        "clarify": 1,
        "not_eligible": 4,
    }
    assert state["filtered_by_residency"] == 1
    assert fake_db["record_trace"] == 1
    assert fake_db["finish"] == "COMPLETED"


def test_results_are_sorted_eligible_first(fake_db):
    results = graph.run(DEMO)["results"]
    labels = [item["label"] for item in results]
    order = {"ELIGIBLE": 0, "NEAR_MISS": 1, "CLARIFY": 2, "NOT_ELIGIBLE": 3}
    assert labels == sorted(labels, key=lambda x: order[x])
    assert results[0]["label"] == "ELIGIBLE"


def test_every_scheme_has_narration_and_grounded_citations(fake_db):
    results = graph.run(DEMO)["results"]
    ids = {item["scheme_id"] for item in results}
    for item in results:
        assert item["narrative"], item["scheme_id"]
        assert item["citations"], item["scheme_id"]
        assert item["rules"], item["scheme_id"]
        for rule in item["rules"]:
            assert rule["verdict"] in {"PASS", "FAIL", "UNKNOWN"}
            assert rule["clause_ref"]
            assert rule["chunk_id"]
    assert "ladli-behna" not in ids  # excluded by the residency pre-filter


def test_near_misses_name_a_single_threshold(fake_db):
    results = graph.run(DEMO)["results"]
    near = [item for item in results if item["label"] == "NEAR_MISS"]
    assert len(near) == 3
    for item in near:
        blocking = [r for r in item["rules"] if r["mandatory"] and r["verdict"] == "FAIL"]
        assert len(blocking) == 1, item["scheme_id"]
        assert blocking[0]["rule_op"] in {"lte", "gte"}


def test_audit_events_are_emitted_in_order(fake_db):
    graph.run(DEMO)
    assert fake_db["audit"][0] == "request.received"
    assert "profile.normalized" in fake_db["audit"]
    assert "eligibility.evaluated" in fake_db["audit"]
    assert fake_db["audit"][-1] == "run.completed"


def test_extracted_facts_reach_the_result_payload(fake_db):
    state = graph.run(DEMO)
    assert state["facts"]["category"] == "obc"
    assert state["facts"]["state_code"] == "UP"
    assert state["facts"]["income_annual"] == 180000
