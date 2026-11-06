"""The eval sets are well formed, labelled consistently with the corpus, and the test split is frozen."""

from __future__ import annotations

import pytest

from asof.corpus import load_corpus
from asof.eval import DECISIONS, FROZEN_TEST_SHA256, load_cases, split_sha256, summarize


def test_test_split_is_frozen():
    """Any edit to the test cases after they were committed (81b5b69) fails here."""
    assert split_sha256("test") == FROZEN_TEST_SHA256


def test_split_sizes_and_unique_ids():
    dev, test = load_cases("dev"), load_cases("test")
    assert (len(dev), len(test)) == (20, 40)
    ids = [c.id for c in dev + test]
    assert len(ids) == len(set(ids))


def test_debugged_scenarios_are_in_dev_only():
    test_drafts = {c.draft for c in load_cases("test")}
    for c in load_cases("dev")[:4]:  # D01-D04: March/June Moffatt, bag fee, ticket transfer
        assert c.draft not in test_drafts


@pytest.mark.parametrize("split", ["dev", "test"])
def test_labels_are_consistent_with_the_corpus(split):
    corpus = load_corpus()
    for c in load_cases(split):
        assert c.expected in DECISIONS and c.expected in c.acceptable, c.id
        assert c.draft_ok == (c.expected == "PASS"), c.id
        assert ("PASS" in c.acceptable) == c.draft_ok, c.id
        if c.key_clause:
            v = corpus.version_in_force(c.key_clause, c.as_of)
            assert v is not None and v.version_label == c.key_version, c.id
        else:
            assert c.category == "not_covered", c.id


def test_every_category_has_counts_cases():
    assert sum(c.category == "counts" for c in load_cases("test")) >= 4


def _rec(cat, ok, decision, cited=True, overrides=0):
    acceptable = ["PASS"] if ok else ["CORRECTED", "ESCALATED"]
    return {"category": cat, "draft_ok": ok, "decision": decision, "acceptable": acceptable,
            "expected": "PASS" if ok else "CORRECTED", "ideal": decision == ("PASS" if ok else "CORRECTED"),
            "safe": decision in acceptable, "false_allow": (not ok) and decision == "PASS",
            "false_block": ok and decision != "PASS", "cited_key_clause": cited, "reason": "X",
            "rule_overrides": overrides, "latency_ms": 1000, "llm_calls": 2}


def test_summary_metrics():
    recs = [_rec("a", True, "PASS"), _rec("a", True, "CORRECTED"), _rec("b", False, "PASS", cited=False),
            _rec("b", False, "CORRECTED", overrides=1), _rec("b", False, "ESCALATED", cited=None)]
    o = summarize(recs)["overall"]
    assert o["false_allow_rate"] == round(1 / 3, 4) and o["false_block_rate"] == 0.5
    assert o["safe_rate"] == 0.6 and o["citation_accuracy"] == 0.75 and o["rule_overrides"] == 1
