"""Run metrics for the JSON summary.

Every number is computed from the report entries and
the gateway usage report. Nothing is sampled or guessed.
"""

from __future__ import annotations

from parity.engine.result import ComparisonStatus
from parity.report.risk import QueryReport

_FIX_RATE_NOTE = "fix rate tracks agent re-proven fixes in a later branch"


def build_metrics(
    reports: list[QueryReport], llm_usage: dict | None = None
) -> dict:
    """Compute run metrics from report entries."""
    total = len(reports)
    if total == 0:
        return {
            "queries_total": 0,
            "match_rate": 0.0,
            "mismatch_rate": 0.0,
            "error_rate": 0.0,
            "not_comparable_rate": 0.0,
            "high_risk_count": 0,
            "avg_risk": 0.0,
            "cost_per_query_tokens": 0,
            "note": "no queries ran",
        }
    matched = sum(1 for r in reports if r.result.status is ComparisonStatus.MATCH)
    mismatched = sum(
        1 for r in reports if r.result.status is ComparisonStatus.MISMATCH
    )
    errors = sum(1 for r in reports if r.result.status is ComparisonStatus.ERROR)
    not_comparable = sum(
        1 for r in reports if r.result.status is ComparisonStatus.NOT_COMPARABLE
    )
    high_risk = sum(1 for r in reports if r.label == "HIGH")
    avg_risk = round(sum(r.score for r in reports) / total, 2)
    tokens = 0
    if llm_usage:
        tokens = llm_usage.get("tokens_in", 0) + llm_usage.get("tokens_out", 0)
    return {
        "queries_total": total,
        "match_rate": round(matched / total, 4),
        "mismatch_rate": round(mismatched / total, 4),
        "error_rate": round(errors / total, 4),
        "not_comparable_rate": round(not_comparable / total, 4),
        "high_risk_count": high_risk,
        "avg_risk": avg_risk,
        "cost_per_query_tokens": tokens // total if total else 0,
        "note": _FIX_RATE_NOTE,
    }
