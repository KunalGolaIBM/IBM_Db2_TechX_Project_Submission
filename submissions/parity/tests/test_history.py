"""Tests for run history types and stores."""

import pytest

from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonResult, ComparisonStatus, DiffKind, ResultSet, RowDiff
from parity.history.store import InMemoryRunStore, save_run
from parity.history.types import ComparisonRecord, RunRecord, build_diff_summary
from parity.pipeline import run_pipeline
from parity.report.risk import QueryReport


def mismatch_report() -> QueryReport:
    """One report with one value diff."""
    result = ComparisonResult(
        status=ComparisonStatus.MISMATCH,
        note="row 0 differs",
        diffs=(
            RowDiff(
                kind=DiffKind.VALUE,
                detail="row 0 differs",
                row_index=0,
                column="id",
                source_value=1,
                target_value=2,
            ),
        ),
    )
    return QueryReport.from_result("q1", "SELECT 1", "SELECT 1", result)


def match_report() -> QueryReport:
    return QueryReport.from_result(
        "q2", "SELECT 2", "SELECT 2", ComparisonResult(status=ComparisonStatus.MATCH)
    )


def test_comparison_record_from_report():
    record = ComparisonRecord.from_report(mismatch_report())
    assert record.query_id == "q1"
    assert record.status == "MISMATCH"
    assert record.risk_score >= 20
    assert record.risk_label in ("MEDIUM", "HIGH")
    assert record.note == "row 0 differs"
    assert "VALUE" in record.diff_summary
    assert "row 0 differs" in record.diff_summary


def test_diff_summary_joins_diffs():
    result = ComparisonResult(
        status=ComparisonStatus.MISMATCH,
        diffs=(
            RowDiff(kind=DiffKind.VALUE, detail="a"),
            RowDiff(kind=DiffKind.ROW_COUNT, detail="b"),
        ),
    )
    report = QueryReport.from_result("q", "a", "b", result)
    summary = build_diff_summary(report)
    assert summary == "VALUE: a; ROW_COUNT: b"


def test_diff_summary_truncated():
    detail = "x" * 2000
    result = ComparisonResult(
        status=ComparisonStatus.MISMATCH,
        diffs=(RowDiff(kind=DiffKind.VALUE, detail=detail),),
    )
    report = QueryReport.from_result("q", "a", "b", result)
    assert len(build_diff_summary(report)) <= 1000
    assert build_diff_summary(report).endswith("...")


def test_memory_store_roundtrip():
    store = InMemoryRunStore()
    run_id = store.start_run("samples")
    run = store.get_run(run_id)
    assert run.run_id == run_id
    assert run.source_dir == "samples"
    assert run.exit_code is None
    store.save_records(run_id, (ComparisonRecord.from_report(match_report()),))
    store.finish_run(run_id, 0)
    loaded = store.get_run(run_id)
    assert loaded.exit_code == 0
    assert len(loaded.records) == 1
    assert loaded.records[0].status == "MATCH"


def test_memory_store_start_ids_increment():
    store = InMemoryRunStore()
    first = store.start_run("a")
    second = store.start_run("b")
    assert second == first + 1


def test_memory_store_unknown_run():
    store = InMemoryRunStore()
    with pytest.raises(KeyError):
        store.get_run(99)


def test_save_run_helper():
    store = InMemoryRunStore()
    run_id = save_run(store, "samples", [mismatch_report(), match_report()], 1)
    run = store.get_run(run_id)
    assert run.exit_code == 1
    assert [r.query_id for r in run.records] == ["q1", "q2"]
    assert next(r.diff_summary for r in run.records) != ""


def test_pipeline_with_history(tmp_path):
    (tmp_path / "q.sql").write_text("SELECT COUNT(*) FROM demo_users;", encoding="utf-8")
    result_set = ResultSet(columns=("count",), rows=((3,),))
    source = InMemoryExecutor({"SELECT COUNT(*) FROM demo_users": result_set})
    target = InMemoryExecutor({'SELECT COUNT(*) AS count FROM "DEMO_USERS"': result_set})
    reports = run_pipeline(tmp_path, source, target)
    store = InMemoryRunStore()
    run_id = save_run(store, str(tmp_path), reports, 0)
    run = store.get_run(run_id)
    assert run.exit_code == 0
    assert run.records[0].status == "MATCH"


def test_run_record_defaults():
    run = RunRecord(run_id=1, source_dir="samples")
    assert run.records == ()
    assert run.exit_code is None
