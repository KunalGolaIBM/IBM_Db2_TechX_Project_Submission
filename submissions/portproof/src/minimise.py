"""Shrink a counterexample to the fewest rows that still disagree.

A verdict of PROVEN DIFFERENT comes with the dataset that showed it, and that
dataset was built to provoke many things at once: a dozen rows a table, most of
them irrelevant to this statement. A developer handed forty rows has to find
the two that matter. This module finds them.

The method is delta debugging over the rows of the witness dataset. A candidate
with some rows removed is loaded into both engines, both statements are run,
and the candidate is kept only if the engines still disagree. Rows are removed
in halves first and then one at a time, table by table, until no single row can
be removed or the trial budget is spent. A candidate either engine refuses to
load (a child row whose parent was removed) is simply not kept.

Every trial is a real execution on both engines, so the result is not an
explanation of the difference. It is a smaller input on which the difference
was observed again.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .corpus import Variant
from .counterexample import InstanceResult, go_home, prove_semantics


@dataclass
class Minimal:
    """The smallest input found on which the two engines still disagree."""

    rows: dict[str, list[tuple]]
    source_rows: list[tuple[str, ...]] = field(default_factory=list)
    db2_rows: list[tuple[str, ...]] = field(default_factory=list)
    rows_before: int = 0
    rows_after: int = 0
    trials: int = 0

    def as_detail(self) -> dict[str, Any]:
        return {
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "trials": self.trials,
            "input": {t: [[str(v) for v in r] for r in rows] for t, rows in self.rows.items() if rows},
            "source_rows": [list(r) for r in self.source_rows[:5]],
            "db2_rows": [list(r) for r in self.db2_rows[:5]],
        }


def _total(rows: dict[str, list[tuple]]) -> int:
    return sum(len(r) for r in rows.values())


def _forget(engine: Any, variant: Variant) -> None:
    forget = getattr(engine, "forget", None)
    if callable(forget):
        try:
            forget(variant)
        except Exception:  # pragma: no cover - cleanup must never change a result
            pass


def minimise(
    *,
    source_sql: str,
    db2_sql: str,
    source: Any,
    target: Any,
    witness: Variant,
    dialect: str,
    max_trials: int = 40,
) -> Minimal | None:
    """Reduce ``witness`` while the two statements still disagree on it.

    Returns None if the disagreement does not reproduce on the witness itself
    (which would mean the verdict depended on something other than its rows).
    """
    trials = 0

    def disagrees(rows: dict[str, list[tuple]]) -> InstanceResult | None:
        nonlocal trials
        trials += 1
        candidate = Variant(
            name=f"{witness.name}:reduced", targets=witness.targets,
            rows={t: list(r) for t, r in rows.items()},
            ddl=witness.ddl, tables=witness.tables, origin=witness.origin,
            strategy=witness.strategy,
        )
        try:
            verdict = prove_semantics(
                source_sql=source_sql, db2_sql=db2_sql, source=source, target=target,
                variants=[candidate], dialect=dialect,
            )
        except Exception:
            return None
        finally:
            if candidate.fingerprint != witness.fingerprint:
                _forget(source, candidate)
                _forget(target, candidate)
        if verdict.order_unstable:
            return None
        for instance in verdict.instances:
            if not instance.agreed and not instance.inconclusive and not instance.db2_error:
                return instance
        return None

    current = {t: list(r) for t, r in witness.rows.items()}
    best = disagrees(current)
    if best is None:
        go_home(source)
        go_home(target)
        return None
    before = _total(current)

    def attempt(table: str, keep: Sequence[tuple]) -> bool:
        nonlocal best, current
        if trials >= max_trials:
            return False
        candidate = dict(current)
        candidate[table] = list(keep)
        found = disagrees(candidate)
        if found is None:
            return False
        current, best = candidate, found
        return True

    # Largest tables first: that is where the most can be removed per trial.
    for table in sorted(current, key=lambda t: -len(current[t])):
        chunk = max(1, len(current[table]) // 2)
        while chunk >= 1 and trials < max_trials:
            index, removed = 0, False
            while index < len(current[table]) and trials < max_trials:
                rows = current[table]
                keep = rows[:index] + rows[index + chunk:]
                if len(keep) < len(rows) and attempt(table, keep):
                    removed = True
                else:
                    index += chunk
            if chunk == 1 and not removed:
                break
            chunk = chunk // 2 if chunk > 1 else (1 if removed else 0)
    go_home(source)
    go_home(target)
    return Minimal(
        rows=current, source_rows=list(best.source_rows), db2_rows=list(best.db2_rows),
        rows_before=before, rows_after=_total(current), trials=trials,
    )
