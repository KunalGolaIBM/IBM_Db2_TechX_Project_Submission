"""Fuzz plan and row generation.

A FuzzPlan says which edge case values to use for
each column of one table. Generation is seeded, so
the same plan always makes the same rows.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any

from parity.fuzz.values import categories_for_db2_type, values_for_column
from parity.sync.schema import TableDef


@dataclass(frozen=True)
class ColumnFuzz:
    """Edge values for one column."""

    column: str
    categories: tuple[str, ...]
    values: tuple[Any, ...]
    skipped_categories: tuple[str, ...] = ()


def _varchar_width(db2_type: str) -> int | None:
    """Return the length inside VARCHAR(n), or None."""
    import re

    match = re.search(r"\(\s*(\d+)\s*\)", db2_type.upper())
    return int(match.group(1)) if match else None


def _fit_width(value: Any, width: int | None) -> Any:
    """Truncate long strings to the column width."""
    if width is not None and isinstance(value, str) and len(value) > width:
        return value[:width]
    return value


@dataclass(frozen=True)
class FuzzPlan:
    """Full fuzz plan for one table."""

    table: str
    columns: tuple[ColumnFuzz, ...]
    seed: int = 42

    @property
    def plan_id(self) -> str:
        """Stable id for this plan."""
        raw = f"{self.table}:{self.seed}:" + ",".join(
            f"{c.column}={','.join(c.categories)}" for c in self.columns
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def build_plan(table: TableDef, seed: int = 42) -> FuzzPlan:
    """Build a plan from a table definition.

    NOT NULL columns never get the null category. Text
    values that are longer than the column width are cut
    to the width, so fuzz rows always fit the column.
    Skipped categories are recorded on each column.
    """
    columns: list[ColumnFuzz] = []
    for col in table.columns:
        categories = categories_for_db2_type(col.db2_type)
        skipped: list[str] = []
        if not col.nullable and "null" in categories:
            categories = tuple(c for c in categories if c != "null")
            skipped.append("null")
        values: list[Any] = []
        for category in categories:
            values.extend(values_for_column(col.db2_type, category))
        columns.append(
            ColumnFuzz(
                column=col.name,
                categories=categories,
                values=tuple(values),
                skipped_categories=tuple(skipped),
            )
        )
    return FuzzPlan(table=table.name, columns=tuple(columns), seed=seed)


def generate_rows(
    plan: FuzzPlan,
    base_row: tuple[Any, ...],
    count: int,
    skip_columns: tuple[str, ...] = (),
) -> list[tuple[Any, ...]]:
    """Generate fuzz rows from a base row.

    Each row starts as a copy of the base row, then
    one or two columns get edge values. The seed
    makes the output repeatable. Columns in
    skip_columns keep their base value, which is how
    a primary key stays unique.
    """
    if count <= 0:
        raise ValueError("count must be positive")
    rng = random.Random(plan.seed)
    rows: list[tuple[Any, ...]] = []
    width = len(plan.columns)
    free = [
        index for index, column in enumerate(plan.columns) if column.column not in skip_columns
    ]
    if not free:
        free = list(range(width))
    for _ in range(count):
        row = list(base_row)
        picks = rng.sample(free, k=min(2, len(free)))
        for index in picks:
            values = plan.columns[index].values
            if values:
                row[index] = rng.choice(values)
        rows.append(tuple(row))
    return rows


def plan_to_dict(plan: FuzzPlan) -> dict[str, Any]:
    """Return a JSON safe dict for storage and logs."""
    return {
        "plan_id": plan.plan_id,
        "table": plan.table,
        "seed": plan.seed,
        "columns": [
            {
                "column": col.column,
                "categories": list(col.categories),
                "value_count": len(col.values),
            }
            for col in plan.columns
        ],
    }
