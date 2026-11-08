"""The intake evaluation is frozen (gold answers and documents pinned before its first run) and scores honestly."""

from __future__ import annotations

import json
from datetime import date

from asof import intake
from asof.eval import intake_eval

# Pinned before the first run (Sat 7 Nov 2026). Never edit the documents or gold.json; add a new set instead.
FROZEN = "99c183ebefa7adc7315179a04a3af587142197bba2d3a0b715c31f1286461034"


def test_the_evaluation_is_frozen():
    assert intake_eval.frozen_digest() == FROZEN, "the intake evaluation changed after it was frozen"


def test_the_gold_answers_are_well_formed_and_each_document_states_them():
    gold = json.loads(intake_eval.GOLD.read_text(encoding="utf-8"))
    paths = intake_eval.document_paths()
    assert len(paths) == 3 and sum(len(d["expect"]) for d in gold["documents"]) == 11
    for d, path in zip(gold["documents"], paths, strict=True):
        text = intake.read_pdf(path.read_bytes(), path.name).text
        for e in d["expect"]:
            assert e["kind"] in ("CHANGE", "NEW", "UNCHANGED") and date.fromisoformat(e["from"])
            assert e["from"] and all(t is None or date.fromisoformat(t) for t in e["to"])
            if e["clause_id"] == "NEW":
                assert e["text_has"].casefold() in text.casefold()
            else:
                assert e["clause_id"] in intake.corpus_clauses(d["doc_id"])
        if d.get("injection"):
            assert d["injection"].casefold() in text.casefold()


def _proposal(rule, kind="CHANGE", blocked=False, start=date(2027, 2, 1), end=None, cid="BAG-001"):
    checks = [intake.Check("verbatim text", "fail" if blocked else "pass", "x")]
    return intake.Proposal(1, kind, cid, "baggage", "t", "text", rule, start, end, "q", 1, checks)


def test_the_scorer_separates_caught_errors_from_escaped_ones():
    expect = {"clause_id": "BAG-001", "kind": "CHANGE", "from": "2027-02-01", "to": [None],
              "values": [{"unit": "usd", "value": 45}]}
    assert intake_eval.score(expect, _proposal({"first_bag_fee_usd": 45}))["outcome"] == "correct, acceptable"
    assert intake_eval.score(expect, _proposal({"bag_fee_usd": 45}, blocked=True))["outcome"] == "correct, blocked"
    assert intake_eval.score(expect, _proposal({"first_bag_fee_usd": 50}, blocked=True))["outcome"] == "wrong, blocked"
    wrong = intake_eval.score(expect, _proposal({"first_bag_fee_usd": 45}, start=date(2027, 1, 1)))
    assert wrong["outcome"] == "wrong, acceptable" and "from 2027-01-01" in wrong["problems"][0]
    assert intake_eval.score(expect, None)["outcome"] == "missing"


def test_flags_and_lists_are_matched_by_meaning_not_by_order():
    assert intake_eval._value_ok({"flag": "transfer_allowed", "value": True}, {"transfer_allowed": True})
    assert not intake_eval._value_ok({"flag": "transfer_allowed", "value": True}, {"transfer_allowed": 1})
    assert intake_eval._value_ok({"items": ["Spouse", "child"]}, {"relations": ["child", "spouse"]})
    assert not intake_eval._value_ok({"items": ["spouse", "child"]}, {"relations": ["child"]})
