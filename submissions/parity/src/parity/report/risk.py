"""Risk scoring and per query report records.

Risk score is a simple transparent formula. A DBA
can check it by hand. No model is involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from parity.engine.result import ComparisonResult, ComparisonStatus, DiffKind

_WEIGHTS: dict[DiffKind, int] = {
    DiffKind.VALUE: 10,
    DiffKind.NULL_VS_VALUE: 10,
    DiffKind.ROW_COUNT: 10,
    DiffKind.TYPE: 8,
    DiffKind.COLUMN_NAME: 5,
    DiffKind.COLUMN_ORDER: 5,
    DiffKind.COLUMN_COUNT: 5,
    DiffKind.TRAILING_SPACE: 3,
    DiffKind.TIE_ORDER: 3,
}

_STATUS_BONUS: dict[ComparisonStatus, int] = {
    ComparisonStatus.MISMATCH: 20,
    ComparisonStatus.ERROR: 15,
    ComparisonStatus.NOT_COMPARABLE: 5,
    ComparisonStatus.MATCH: 0,
}


def risk_score(result: ComparisonResult) -> int:
    """Return a 0 to 100 risk score for one result."""
    score = _STATUS_BONUS[result.status]
    for diff in result.diffs:
        score += _WEIGHTS.get(diff.kind, 5)
    return min(100, score)


def risk_label(score: int) -> str:
    """Return LOW, MEDIUM, or HIGH for a score."""
    if score >= 50:
        return "HIGH"
    if score >= 20:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class QueryReport:
    """One query result for the report."""

    query_id: str
    source_sql: str
    db2_sql: str
    result: ComparisonResult
    score: int = 0
    label: str = "LOW"
    applied_rules: tuple[str, ...] = ()

    @classmethod
    def from_result(
        cls,
        query_id: str,
        source_sql: str,
        db2_sql: str,
        result: ComparisonResult,
        applied_rules: tuple[str, ...] = (),
    ) -> QueryReport:
        """Build a report entry and score it."""
        score = risk_score(result)
        return cls(
            query_id=query_id,
            source_sql=source_sql,
            db2_sql=db2_sql,
            result=result,
            score=score,
            label=risk_label(score),
            applied_rules=applied_rules,
        )
