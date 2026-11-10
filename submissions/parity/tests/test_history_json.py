"""Tests for the JSON run history store and CLI history wiring."""

import json
from pathlib import Path

import pytest

from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonResult, ComparisonStatus, DiffKind, ResultSet, RowDiff
from parity.history.json_store import JsonRunStore
from parity.history.store import save_run
from parity.pipeline import run_pipeline
from parity.report.html import render_json_summary
from parity.report.risk import QueryReport


def mismatch_report() -> QueryReport:
    result = ComparisonResult(
        status=ComparisonStatus.MISMATCH,
        note="row 0 differs",
        diffs=(RowDiff(kind=DiffKind.VALUE, detail="row 0 differs", source_value=1, target_value=2),),
    )
    return QueryReport.from_result("q1", "SELECT 1", "SELECT 1", result)


def filled_store(path: Path) -> JsonRunStore:
    store = JsonRunStore(path)
    save_run(store, "samples", [mismatch_report()], 1)
    return store


def test_json_store_roundtrip(tmp_path: Path):
    path = tmp_path / "history.json"
    filled_store(path)
    loaded = JsonRunStore(path)
    run = loaded.get_run(1)
    assert run.source_dir == "samples"
    assert run.exit_code == 1
    assert run.started_at != ""
    assert run.finished_at != ""
    assert [r.query_id for r in run.records] == ["q1"]
    assert run.records[0].status == "MISMATCH"


def test_json_store_ids_increment(tmp_path: Path):
    history = tmp_path / "history.json"
    store = filled_store(history)
    second = store.start_run("again")
    assert second == 2
    persisted = JsonRunStore(history)
    assert persisted.get_run(2).source_dir == "again"


def test_json_store_unknown_run(tmp_path: Path):
    with pytest.raises(KeyError):
        JsonRunStore(tmp_path / "history.json").get_run(99)


def test_json_store_file_format(tmp_path: Path):
    path = tmp_path / "history.json"
    filled_store(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["runs"][0]["exit_code"] == 1
    assert payload["runs"][0]["records"][0]["query_id"] == "q1"


def test_json_summary_with_run_id():
    report = mismatch_report()
    text = render_json_summary([report], run_id=7)
    assert '"run_id": 7' in text


def test_json_summary_without_run_id():
    text = render_json_summary([mismatch_report()])
    assert "run_id" not in text


def test_pipeline_save_into_json_history(tmp_path: Path):
    (tmp_path / "q.sql").write_text("SELECT id FROM demo_users;", encoding="utf-8")
    result_set = ResultSet(columns=("id",), rows=((1,),))
    source = InMemoryExecutor({"SELECT id FROM demo_users": result_set})
    target = InMemoryExecutor({'SELECT id FROM "DEMO_USERS"': result_set})
    reports = run_pipeline(tmp_path, source, target)
    store = JsonRunStore(tmp_path / "history.json")
    run_id = save_run(store, str(tmp_path), reports, 0)
    assert store.get_run(run_id).exit_code == 0
