"""Deterministic decision policy.

Db2 compares facts to rules. This module only labels the outcome, which
keeps the business policy small, pure and unit-testable.

Labels
------
ELIGIBLE      no mandatory criterion failed, no mandatory criterion unknown
NEAR_MISS     exactly one mandatory failure, and it is a numeric threshold
              the applicant can plausibly move towards (income, age, land)
CLARIFY       nothing failed, but a mandatory fact is missing
NOT_ELIGIBLE  a categorical mismatch, or more than one mandatory failure
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from .models import RuleRow

NUMERIC_OPS = {"lte", "gte"}


def classify(rows: Sequence[RuleRow]) -> str:
    if not rows:
        return "CLARIFY"

    blocking = [r for r in rows if r.blocking]
    if blocking:
        if len(blocking) == 1 and blocking[0].rule_op in NUMERIC_OPS:
            return "NEAR_MISS"
        return "NOT_ELIGIBLE"

    if any(r.needs_info for r in rows):
        return "CLARIFY"

    return "ELIGIBLE"


def readiness(rows: Sequence[RuleRow]) -> int:
    """Percentage of criteria satisfied, useful as a UI signal."""
    if not rows:
        return 0
    satisfied = sum(1 for r in rows if r.verdict == "PASS")
    return round(100 * satisfied / len(rows))


def group_by_scheme(rows: Iterable[RuleRow]) -> Dict[str, List[RuleRow]]:
    grouped: Dict[str, List[RuleRow]] = {}
    for row in rows:
        grouped.setdefault(row.scheme_id, []).append(row)
    return grouped


def split_parts(rows: Sequence[RuleRow]) -> tuple[List[RuleRow], List[RuleRow], List[RuleRow]]:
    """(blocking failures, advisory failures, missing mandatory facts)"""
    blocking = [r for r in rows if r.blocking]
    advisory = [r for r in rows if not r.mandatory and r.verdict == "FAIL"]
    missing = [r for r in rows if r.needs_info]
    return blocking, advisory, missing


def gap_hint(row: RuleRow) -> str:
    """One human sentence describing why a criterion failed."""
    if row.rule_op == "lte":
        return f"{humanize(row.criterion_code)} must be at most {row.limit_text()}"
    if row.rule_op == "gte":
        return f"{humanize(row.criterion_code)} must be at least {row.limit_text()}"
    if row.rule_op == "in":
        return f"{humanize(row.criterion_code)} must be {row.limit_text()}"
    return f"{humanize(row.criterion_code)} must be {row.limit_text()}"


def humanize(key: str) -> str:
    return key.replace("_", " ")


CATEGORY_ORDER = {
    "eligible": 0,
    "near_miss": 1,
    "clarify": 2,
    "not_eligible": 3,
}
