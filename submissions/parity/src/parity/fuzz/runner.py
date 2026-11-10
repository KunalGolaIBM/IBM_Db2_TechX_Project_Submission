"""Run a fuzz case over a workload.

The fuzzer generates edge case rows for every table. The
same rows load into Postgres and into Db2, so any result
difference comes from the databases and not from the data.
Then the workload runs on both and the engine decides.

This is the step that turns a plan into evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parity.config import DatabaseSettings
from parity.engine.executor import DatabaseExecutor
from parity.fuzz.loader import (
    delete_fuzz_rows,
    load_db2_rows,
    load_postgres_rows,
    read_base_rows,
)
from parity.fuzz.plan import FuzzPlan, build_plan, generate_rows
from parity.report.risk import QueryReport
from parity.sync.data import checksum_rows
from parity.sync.schema import TableDef

_KEY_OFFSET = 1_000_000


@dataclass(frozen=True)
class FuzzOutcome:
    """What was loaded for one table."""

    table: str
    plan_id: str
    rows: int
    checksum: str


def fresh_key(base_value: Any, index: int) -> Any:
    """Return a key value that cannot clash with the base data."""
    if isinstance(base_value, bool):
        return base_value
    if isinstance(base_value, int):
        return base_value + _KEY_OFFSET + index
    if isinstance(base_value, str):
        return f"{base_value}-fuzz-{index}"
    return base_value


def prepare_rows(
    table: TableDef, base_row: tuple[Any, ...], count: int, seed: int = 42
) -> tuple[list[tuple[Any, ...]], FuzzPlan]:
    """Build the fuzz rows for one table.

    The primary key keeps a fresh value so the rows do not
    clash with the base data. Every other column can take
    an edge case value.
    """
    plan = build_plan(table, seed=seed)
    key_columns = tuple(column.name for column in table.columns if column.primary_key)
    key_indexes = [
        index for index, column in enumerate(table.columns) if column.primary_key
    ]
    generated = generate_rows(plan, base_row, count, skip_columns=key_columns)
    rows: list[tuple[Any, ...]] = []
    for index, row in enumerate(generated):
        values = list(row)
        for key_index in key_indexes:
            values[key_index] = fresh_key(base_row[key_index], index)
        rows.append(tuple(values))
    return rows, plan


def load_fuzz_rows(
    settings: DatabaseSettings,
    admin,
    table: TableDef,
    rows: list[tuple[Any, ...]],
) -> None:
    """Load the same rows into both databases."""
    load_postgres_rows(settings, table, rows)
    load_db2_rows(admin, table, rows)


def run_fuzz_case(
    workload_dir: Path,
    source: DatabaseExecutor,
    target: DatabaseExecutor,
    settings: DatabaseSettings,
    admin,
    tables: tuple[TableDef, ...],
    rows_per_table: int = 20,
    seed: int = 42,
    schema=None,
) -> tuple[tuple[FuzzOutcome, ...], list[QueryReport]]:
    """Load fuzz rows into both databases and run the workload.

    Returns what was loaded and the report entries.
    """
    from parity.pipeline import run_pipeline

    outcomes: list[FuzzOutcome] = []
    for table in tables:
        if not any(column.primary_key for column in table.columns):
            continue
        base_rows = read_base_rows(settings, table, limit=1)
        if not base_rows:
            continue
        rows, plan = prepare_rows(table, base_rows[0], rows_per_table, seed=seed)
        delete_fuzz_rows(settings, admin, table)
        load_fuzz_rows(settings, admin, table, rows)
        outcomes.append(
            FuzzOutcome(
                table=table.name,
                plan_id=plan.plan_id,
                rows=len(rows),
                checksum=checksum_rows(rows),
            )
        )
    reports = run_pipeline(workload_dir, source, target, schema=schema)
    return tuple(outcomes), reports
