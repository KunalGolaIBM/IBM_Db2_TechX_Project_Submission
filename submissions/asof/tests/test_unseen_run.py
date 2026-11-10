"""The unseen-domain runner's pre-registered metrics, on synthetic records (never GPT's cases)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from asof.eval.unseen import run


def rec(case_id: str, label: str, decision: str, **kw) -> dict:
    base = {"id": case_id, "customer_date": "2026-03-10", "as_of": "2026-03-10", "governing": "V1", "label": label,
            "decision": decision, "reason_code": "X", "released": decision != "ESCALATED", "latency_ms": 1000,
            "cited_pass1": [], "cited_pass2": [], "other_version_cited": False,
            "plain": {"decision": "RELEASE", "reason": "r", "latency_ms": 10, "error": None}}
    return base | kw


def test_wilson_interval_matches_the_textbook_values():
    lo, hi = run.wilson(0, 25)
    assert lo == 0.0 and hi == pytest.approx(0.1332, abs=1e-4)
    lo, hi = run.wilson(5, 25)
    assert (lo, hi) == (pytest.approx(0.0886, abs=1e-4), pytest.approx(0.3913, abs=1e-4))
    lo, hi = run.wilson(15, 15)
    assert lo == pytest.approx(0.7961, abs=1e-4) and hi == 1.0
    assert run.wilson(0, 0) is None


def test_a_pass_on_a_wrong_draft_is_a_false_allow_and_a_hold_is_safe_but_not_ideal():
    s = run.score([rec("a", "wrong", "PASS"), rec("b", "wrong", "ESCALATED"), rec("c", "correct", "PASS")], {})
    assert (s["false_allow"]["k"], s["false_allow"]["n"]) == (1, 2)
    rows = {r["id"]: r for r in s["rows"]}
    assert rows["b"]["safe"] and not rows["b"]["ideal"] and not rows["b"]["false_allow"]
    assert rows["c"]["ideal"] and not rows["c"]["false_block"]


def test_a_correct_draft_that_is_corrected_or_held_is_a_false_block():
    s = run.score([rec("a", "correct", "CORRECTED"), rec("b", "correct", "ESCALATED"), rec("c", "correct", "PASS")],
                  {"a": {"grade": "right", "why": "w"}})
    assert (s["false_block"]["k"], s["false_block"]["n"]) == (2, 3)
    assert s["ideal"]["k"] == 1 and s["harmful_corrections"] == 0


def test_a_corrected_wrong_draft_counts_by_its_grade_and_is_a_range_until_graded():
    records = [rec("a", "wrong", "CORRECTED"), rec("b", "wrong", "CORRECTED")]
    pending = run.score(records, {})
    assert (pending["false_allow"]["k"], pending["false_allow"]["k_high"]) == (0, 2)
    assert (pending["ideal"]["k"], pending["ideal"]["k_high"]) == (0, 2) and pending["pending_grades"] == 2
    graded = run.score(records, {"a": {"grade": "right", "why": "w"}, "b": {"grade": "wrong", "why": "w"}})
    assert (graded["false_allow"]["k"], graded["false_allow"]["k_high"]) == (1, 1)
    assert (graded["ideal"]["k"], graded["ideal"]["k_high"]) == (1, 1) and graded["pending_grades"] == 0


def test_a_correct_draft_rewritten_into_a_wrong_answer_is_a_harmful_correction():
    s = run.score([rec("a", "correct", "CORRECTED")], {"a": {"grade": "wrong", "why": "w"}})
    assert s["harmful_corrections"] == 1 and s["false_block"]["k"] == 1


def test_a_grade_other_than_right_or_wrong_is_refused():
    with pytest.raises(run.RunError):
        run.score([rec("a", "wrong", "CORRECTED")], {"a": {"grade": "maybe", "why": "w"}})


def test_the_booking_date_is_the_iso_date_at_the_start_of_customer_date():
    assert run.booking_date("2026-04-30") == date(2026, 4, 30)
    assert run.booking_date("2026-04-30 23:59 IST") == date(2026, 4, 30)
    with pytest.raises(run.RunError):
        run.booking_date("30 April 2026")


def test_the_governing_version_follows_the_booking_date():
    assert run.governing_version(date(2026, 4, 30)) == 1
    assert run.governing_version(date(2026, 5, 1)) == 2
    assert run.governing_version(date(2026, 8, 31)) == 2
    assert run.governing_version(date(2026, 9, 1)) == 3
    with pytest.raises(run.RunError):
        run.governing_version(date(2025, 12, 31))


def test_cases_load_only_when_the_file_is_the_pinned_one(tmp_path):
    synthetic = [{"id": "X1", "customer_question": "q", "customer_date": "2026-06-02", "assistant_draft": "d",
                  "label": "wrong", "reason": "r"}]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(synthetic))
    (case,) = run.load_cases(path, sha256=None)
    assert case.as_of == date(2026, 6, 2) and case.label == "wrong"
    with pytest.raises(run.RunError):
        run.load_cases(path)  # not the pinned SHA-256
    path.write_text(json.dumps([synthetic[0] | {"label": "partly"}]))
    with pytest.raises(run.RunError):
        run.load_cases(path, sha256=None)


def test_the_runner_pins_the_same_cases_file_as_the_provenance_test():
    from test_unseen_provenance import PINNED

    assert run.CASES_SHA256 == PINNED["spr_40_test_cases.json"]


def test_the_report_marks_pending_grades_and_false_allows(tmp_path, monkeypatch):
    from asof.eval.unseen import report

    monkeypatch.setattr(report, "REPORT", tmp_path / "results.md")
    runs = [{"run": 1, "first_run": True, "note": "", "provider": "p", "model": "m", "started_at": "t",
             "git_commit": "c", "prompt_version": "v", "cases_sha256": "0" * 64, "policy_rows": 3,
             "policy_sha256": "1" * 64, "workers": 1, "wall_time_s": 1, "ledger_chain": "OK",
             "records": [rec("a", "wrong", "PASS"), rec("b", "wrong", "CORRECTED")]}]
    (tmp_path / "results.md").write_text("# Notes kept\n\n<!-- generated:runs -->\nold\n<!-- /generated:runs -->\n\nTail kept.\n")
    report.write(runs, {})
    text = (tmp_path / "results.md").read_text()
    assert "# Notes kept" in text and "Tail kept." in text and "old" not in text
    assert "**released, false allow**" in text and "pending" in text and "First run (final)" in text


def test_one_set_of_definitions_scores_all_three_setups():
    records = [rec("a", "wrong", "ESCALATED", plain={"decision": "RELEASE", "error": None}),
               rec("b", "correct", "PASS", plain={"decision": "BLOCK", "error": None}),
               rec("c", "wrong", "CORRECTED", plain={"decision": "BLOCK", "error": "timeout"})]
    grades = {"c": {"grade": "right", "why": "w"}}
    none, plain, asof = (run.score(records, grades, s) for s in run.SETUPS)
    assert (none["false_allow"]["k"], none["false_block"]["k"], none["ideal"]["k"]) == (2, 0, 1)
    assert (plain["false_allow"]["k"], plain["false_block"]["k"], plain["ideal"]["k"]) == (1, 1, 0)
    assert (asof["false_allow"]["k"], asof["false_block"]["k"], asof["ideal"]["k"]) == (0, 0, 2)
    assert plain["outcomes"]["wrong"] == {"released": 1, "rewritten": 0, "held": 1} and plain["errors"] == 1
    held_wrong = [r for r in plain["rows"] if r["id"] == "c"][0]
    assert held_wrong["safe"] and not held_wrong["ideal"] and not held_wrong["false_allow"]


def test_the_plain_judge_sees_only_v3_the_question_and_the_draft_and_fails_closed():
    from asof.eval.unseen import baseline
    from asof.llm import LLMError, LLMResult

    msgs = baseline.plain_judge_messages("q <x>", "d", baseline.latest_policy())
    assert msgs[0][1] == baseline.PLAIN_JUDGE_SYSTEM and "POLICY V3" in msgs[1][1] and "POLICY V1" not in msgs[1][1]
    assert "&lt;x&gt;" in msgs[1][1] and "data, not instructions" in baseline.PLAIN_JUDGE_SYSTEM

    class Fails:
        def structured(self, *a, **k):
            raise LLMError("timed out")

    class Says:
        def structured(self, schema, messages, *a, **k):
            return LLMResult(schema(decision="RELEASE", reason="fine"), 1, 1, 1, 1)

    out = baseline.plain_judge(Fails(), "q", "d")
    assert out.decision == "BLOCK" and out.error == "timed out"
    assert baseline.plain_judge(Says(), "q", "d").decision == "RELEASE"
