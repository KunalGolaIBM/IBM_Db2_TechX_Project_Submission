"""Tests for schema aware fuzz planning."""

from parity.fuzz.plan import build_plan, generate_rows
from parity.sync.schema import ColumnDef, TableDef


def test_not_null_column_skips_null_category():
    table = TableDef(
        name="t",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False),
            ColumnDef(name="name", db2_type="VARCHAR(255)", nullable=True),
        ),
    )
    plan = build_plan(table)
    id_col = plan.columns[0]
    assert "null" not in id_col.categories
    assert "null" in id_col.skipped_categories
    assert all(value is not None for value in id_col.values)


def test_nullable_column_keeps_null():
    table = TableDef(
        name="t",
        columns=(ColumnDef(name="name", db2_type="VARCHAR(255)", nullable=True),),
    )
    plan = build_plan(table)
    assert "null" in plan.columns[0].categories


def test_narrow_column_truncates_long_values():
    table = TableDef(
        name="t",
        columns=(ColumnDef(name="name", db2_type="VARCHAR(3)", nullable=True),),
    )
    plan = build_plan(table)
    strings = [v for v in plan.columns[0].values if isinstance(v, str)]
    assert strings
    assert all(len(value) <= 3 for value in strings)


def test_generated_rows_respect_constraints():
    table = TableDef(
        name="t",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False),
            ColumnDef(name="name", db2_type="VARCHAR(2)", nullable=True),
        ),
    )
    plan = build_plan(table)
    rows = generate_rows(plan, (1, "ab"), count=20)
    assert all(row[0] is not None for row in rows)
    assert all(not isinstance(row[1], str) or len(row[1]) <= 2 for row in rows)
