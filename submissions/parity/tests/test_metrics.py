"""Tests for run metrics."""

import json

from parity.engine.result import ComparisonResult, ComparisonStatus
from parity.report.html import render_json_summary
from parity.report.metrics import build_metrics
from parity.report.risk import QueryReport


def report(qid: str, status: ComparisonStatus) -> QueryReport:
    return QueryReport.from_result(
        qid, f"SELECT {qid}", f"SELECT {qid}", ComparisonResult(status=status)
    )


def test_metrics_rates():
    reports = [
        report("a", ComparisonStatus.MATCH),
        report("b", ComparisonStatus.MATCH),
        report("c", ComparisonStatus.MISMATCH),
        report("d", ComparisonStatus.ERROR),
    ]
    metrics = build_metrics(reports)
    assert metrics["queries_total"] == 4
    assert metrics["match_rate"] == 0.5
    assert metrics["mismatch_rate"] == 0.25
    assert metrics["error_rate"] == 0.25
    assert metrics["not_comparable_rate"] == 0.0


def test_metrics_empty_reports():
    metrics = build_metrics([])
    assert metrics["queries_total"] == 0
    assert metrics["match_rate"] == 0.0


def test_metrics_cost_per_query():
    reports = [report("a", ComparisonStatus.MATCH), report("b", ComparisonStatus.MATCH)]
    usage = {"tokens_in": 30, "tokens_out": 10}
    metrics = build_metrics(reports, usage)
    assert metrics["cost_per_query_tokens"] == 20


def test_json_summary_includes_metrics():
    text = render_json_summary([report("a", ComparisonStatus.MATCH)])
    payload = json.loads(text)
    assert payload["metrics"]["queries_total"] == 1
    assert payload["metrics"]["match_rate"] == 1.0
