"""Tests for regression mode."""

import json
from pathlib import Path

from parity.cli import build_parser
from parity.engine.result import ComparisonResult, ComparisonStatus
from parity.history.json_store import JsonRunStore
from parity.history.regression import (
    RegressionResult,
    compare_to_baseline,
    find_last_passing,
    format_regression,
)
from parity.history.store import InMemoryRunStore, save_run
from parity.history.types import ComparisonRecord, RunRecord
from parity.report.html import render_json_summary
from parity.report.risk import QueryReport


def report(qid: str, status: ComparisonStatus) -> QueryReport:
    result = ComparisonResult(status=status)
    return QueryReport.from_result(qid, f"SELECT {qid}", f"SELECT {qid}", result)


def record(qid: str, status: str) -> ComparisonRecord:
    return ComparisonRecord(
        query_id=qid,
        source_sql=f"SELECT {qid}",
        db2_sql=f"SELECT {qid}",
        status=status,
        risk_score=0,
        risk_label="LOW",
        note="",
        diff_summary="",
    )


def baseline_run() -> RunRecord:
    return RunRecord(
        run_id=1,
        source_dir="samples",
        records=(
            record("q_match", "MATCH"),
            record("q_fail", "MISMATCH"),
        ),
    )


def current_reports():
    return [
        report("q_match", ComparisonStatus.MISMATCH),  # new regression
        report("q_fail", ComparisonStatus.MISMATCH),  # repeat failure
        report("q_healed", ComparisonStatus.MATCH),  # fixed
        report("q_new", ComparisonStatus.MATCH),  # unknown query
    ]


def test_new_failure_detected():
    result = compare_to_baseline(current_reports(), baseline_run())
    assert result.new_failures == ("q_match",)


def test_repeat_failure_detected():
    result = compare_to_baseline(current_reports(), baseline_run())
    assert result.repeat_failures == ("q_fail",)


def test_fixed_query_detected():
    baseline = RunRecord(
        run_id=1,
        source_dir="samples",
        records=(record("q_healed", "MISMATCH"),),
    )
    result = compare_to_baseline(current_reports(), baseline)
    assert result.fixed == ("q_healed",)
    assert not result.has_failures


def test_unknown_query_detected():
    result = compare_to_baseline(current_reports(), baseline_run())
    assert result.unknown_queries == ("q_healed", "q_new")


def test_regressions_flag_platforms():
    result = compare_to_baseline(current_reports(), baseline_run())
    assert result.has_regressions
    assert result.has_failures
    assert result.baseline_run_id == 1


def test_as_dict_is_json_safe():
    result = compare_to_baseline(current_reports(), baseline_run())
    text = json.dumps(result.as_dict())
    assert '"new_failures": ["q_match"]' in text


def test_find_last_passing_prefers_latest_pass():
    store = InMemoryRunStore()
    save_run(store, "samples", [report("a", ComparisonStatus.MATCH)], 0)
    save_run(store, "samples", [report("a", ComparisonStatus.MISMATCH)], 1)
    baseline = find_last_passing(store)
    assert baseline is not None
    assert baseline.run_id == 1


def test_find_last_passing_takes_last_pass_after_fails():
    store = InMemoryRunStore()
    save_run(store, "samples", [report("a", ComparisonStatus.MATCH)], 0)
    save_run(store, "samples", [report("a", ComparisonStatus.MISMATCH)], 1)
    save_run(store, "samples", [report("a", ComparisonStatus.MATCH)], 0)
    baseline = find_last_passing(store)
    assert baseline is not None
    assert baseline.run_id == 3


def test_find_last_passing_none_without_pass():
    store = InMemoryRunStore()
    save_run(store, "samples", [report("a", ComparisonStatus.MISMATCH)], 1)
    assert find_last_passing(store) is None


def test_format_regression_text():
    result = RegressionResult(baseline_run_id=4, new_failures=("q_match",))
    text = format_regression(result)
    assert "run id 4" in text
    assert "new regressions: q_match" in text


def test_format_regression_clean():
    result = RegressionResult(baseline_run_id=2)
    assert "no differences from the baseline" in format_regression(result)


def test_json_store_regression_flow(tmp_path: Path):
    history = tmp_path / "history.json"
    store = JsonRunStore(history)
    pass_run = save_run(store, "a", [report("x", ComparisonStatus.MATCH)], 0)
    assert pass_run == 1
    baseline = find_last_passing(store)
    assert baseline is not None
    result = compare_to_baseline(
        [report("x", ComparisonStatus.MISMATCH), report("y", ComparisonStatus.MATCH)],
        baseline,
    )
    assert result.new_failures == ("x",)
    assert result.unknown_queries == ("y",)


def test_cli_regression_parser():
    args = build_parser().parse_args(
        ["run", "--dir", "samples", "--regression", "--history", "h.json"]
    )
    assert args.regression is True
    assert args.history == "h.json"


def test_json_summary_with_regression():
    result = RegressionResult(baseline_run_id=1, new_failures=("q_match",))
    text = render_json_summary([report("q", ComparisonStatus.MATCH)], regression=result.as_dict())
    assert '"regression"' in text
    assert '"has_regressions": true' in text
