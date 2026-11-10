"""Tests for risk scoring, HTML report, pipeline, and CLI."""

from pathlib import Path

from parity.cli import build_parser
from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonResult, ComparisonStatus, DiffKind, ResultSet, RowDiff
from parity.pipeline import run_pipeline
from parity.report.html import render_html, render_json_summary
from parity.report.risk import QueryReport, risk_label, risk_score


def mismatch_result():
    return ComparisonResult(
        status=ComparisonStatus.MISMATCH,
        diffs=(RowDiff(kind=DiffKind.VALUE, detail="row 0 differs", source_value=1, target_value=2),),
    )


def test_risk_score_match_is_zero():
    assert risk_score(ComparisonResult(status=ComparisonStatus.MATCH)) == 0


def test_risk_score_mismatch_high():
    score = risk_score(mismatch_result())
    assert score >= 20
    assert risk_label(score) in ("MEDIUM", "HIGH")


def test_risk_label_bands():
    assert risk_label(0) == "LOW"
    assert risk_label(30) == "MEDIUM"
    assert risk_label(80) == "HIGH"


def test_html_report_contents():
    report = QueryReport.from_result("q1", "SELECT 1", "SELECT 1", mismatch_result())
    html = render_html([report])
    assert "Parity report" in html
    assert "MISMATCH" in html
    assert "SELECT 1" in html
    assert "row 0 differs" in html


def test_html_escapes_sql():
    report = QueryReport.from_result("q1", "SELECT '<script>'", "SELECT 1", ComparisonResult(status=ComparisonStatus.MATCH))
    html = render_html([report])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_json_summary():
    report = QueryReport.from_result("q1", "SELECT 1", "SELECT 1", mismatch_result())
    summary = render_json_summary([report])
    assert '"query_id": "q1"' in summary
    assert '"status": "MISMATCH"' in summary


def test_pipeline_with_memory_executors(tmp_path: Path):
    (tmp_path / "q.sql").write_text("SELECT id FROM demo_users;", encoding="utf-8")
    result_set = ResultSet(columns=("id",), rows=((1,),))
    source = InMemoryExecutor({"SELECT id FROM demo_users": result_set})
    target = InMemoryExecutor({'SELECT id FROM "DEMO_USERS"': result_set})
    reports = run_pipeline(tmp_path, source, target)
    assert len(reports) == 1
    assert reports[0].result.status is ComparisonStatus.MATCH


def test_pipeline_marks_write_queries(tmp_path: Path):
    (tmp_path / "q.sql").write_text("DELETE FROM demo_users;", encoding="utf-8")
    source = InMemoryExecutor({})
    target = InMemoryExecutor({})
    reports = run_pipeline(tmp_path, source, target)
    assert reports[0].result.status is ComparisonStatus.NOT_COMPARABLE


def test_cli_run_parser():
    args = build_parser().parse_args(["run", "--dir", "samples", "--out", "r.html"])
    assert args.command == "run"
    assert args.dir == "samples"
    assert args.bridge is False
