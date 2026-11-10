"""Record types for run history.

A run is one execution of the pipeline over a workload
directory. It holds one record per query outcome. The
records are plain data so any store can persist them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parity.report.risk import QueryReport

_DIFF_SUMMARY_LIMIT = 990


def build_diff_summary(report: QueryReport) -> str:
    """Describe the first differences in one short string."""
    parts = [
        f"{diff.kind.value}: {diff.detail}" for diff in report.result.diffs
    ]
    summary = "; ".join(parts)
    if len(summary) > _DIFF_SUMMARY_LIMIT:
        summary = summary[: _DIFF_SUMMARY_LIMIT] + "..."
    return summary


@dataclass(frozen=True)
class ComparisonRecord:
    """One query outcome inside a run."""

    query_id: str
    source_sql: str
    db2_sql: str
    status: str
    risk_score: int
    risk_label: str
    note: str
    diff_summary: str
    applied_rules: tuple[str, ...] = ()

    @classmethod
    def from_report(cls, report: QueryReport) -> ComparisonRecord:
        """Build a record from a report entry."""
        return cls(
            query_id=report.query_id,
            source_sql=report.source_sql,
            db2_sql=report.db2_sql,
            status=report.result.status.value,
            risk_score=report.score,
            risk_label=report.label,
            note=report.result.note,
            diff_summary=build_diff_summary(report),
            applied_rules=report.applied_rules,
        )


@dataclass
class RunRecord:
    """One full run with its query outcomes."""

    run_id: int
    source_dir: str
    started_at: str = ""
    finished_at: str = ""
    exit_code: int | None = None
    records: tuple[ComparisonRecord, ...] = field(default_factory=tuple)
