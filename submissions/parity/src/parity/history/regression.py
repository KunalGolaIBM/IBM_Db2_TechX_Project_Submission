"""Regression comparison against the last passing run.

A passing run is one whose exit code was 0, so every
comparable query matched at that time. The current run
is compared query by query with that baseline:

- new regression: a query that passed before fails now.
- repeat failure: the same query fails in both runs.
- fixed: the query failed before and passes now.
- unknown query: the query was not part of the baseline.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from parity.history.types import RunRecord
from parity.report.risk import QueryReport

_MATCH = "MATCH"


@dataclass
class RegressionResult:
    """The diff between one run and its passing baseline."""

    baseline_run_id: int
    new_failures: tuple[str, ...] = field(default_factory=tuple)
    repeat_failures: tuple[str, ...] = field(default_factory=tuple)
    fixed: tuple[str, ...] = field(default_factory=tuple)
    unknown_queries: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_regressions(self) -> bool:
        """True when new failures exist."""
        return bool(self.new_failures)

    @property
    def has_failures(self) -> bool:
        """True when new or repeat failures exist."""
        return bool(self.new_failures or self.repeat_failures)

    def as_dict(self) -> dict:
        """JSON safe form for the summary."""
        return {
            "baseline_run_id": self.baseline_run_id,
            "new_failures": list(self.new_failures),
            "repeat_failures": list(self.repeat_failures),
            "fixed": list(self.fixed),
            "unknown_queries": list(self.unknown_queries),
            "has_regressions": self.has_regressions,
        }


def find_last_passing(store) -> RunRecord | None:
    """Return the newest run in the store with exit code 0."""
    for run in reversed(list(store.list_runs())):
        if run.exit_code == 0:
            return run
    return None


def compare_to_baseline(
    reports: Sequence[QueryReport], baseline: RunRecord
) -> RegressionResult:
    """Compare current report entries with the baseline run."""
    baseline_status = {record.query_id: record.status for record in baseline.records}
    result = RegressionResult(baseline_run_id=baseline.run_id)
    new: list[str] = []
    repeat: list[str] = []
    classes = [(report.query_id, report.result.status.value) for report in reports]
    for query_id, status in classes:
        before = baseline_status.get(query_id)
        if status != _MATCH and before == _MATCH:
            new.append(query_id)
        elif status != _MATCH and before is not None:
            repeat.append(query_id)
        elif status == _MATCH and before is not None and before != _MATCH:
            result.fixed = (*result.fixed, query_id)
        elif before is None:
            result.unknown_queries = (*result.unknown_queries, query_id)
    result.new_failures = tuple(new)
    result.repeat_failures = tuple(repeat)
    return result


def format_regression(result: RegressionResult) -> str:
    """Human readable text for the command line."""
    lines = [f"regression base: run id {result.baseline_run_id}"]

    if result.new_failures:
        lines.append(f"new regressions: {', '.join(result.new_failures)}")
    if result.repeat_failures:
        lines.append(f"repeat failures: {', '.join(result.repeat_failures)}")
    if result.fixed:
        lines.append(f"fixed queries: {', '.join(result.fixed)}")
    if result.unknown_queries:
        lines.append(f"unknown queries: {', '.join(result.unknown_queries)}")
    if not result.has_failures and not result.fixed and not result.unknown_queries:
        lines.append("no differences from the baseline")
    return "\n".join(lines)
