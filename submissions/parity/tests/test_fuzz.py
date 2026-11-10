"""Tests for the fuzz value library and plan generator."""

import pytest

from parity.fuzz.plan import build_plan, generate_rows, plan_to_dict
from parity.fuzz.values import CATEGORIES, categories_for_db2_type, values_for_category
from parity.sync.schema import ColumnDef, TableDef


def demo_table():
    return TableDef(
        name="demo_users",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False),
            ColumnDef(name="name", db2_type="VARCHAR(255)", nullable=True),
        ),
    )


def test_all_categories_have_values():
    for category in CATEGORIES:
        assert values_for_category(category)


def test_unknown_category_rejected():
    with pytest.raises(ValueError, match="unknown category"):
        values_for_category("nope")


def test_categories_by_type():
    assert "extreme_int" in categories_for_db2_type("INTEGER")
    assert "trailing_space" in categories_for_db2_type("VARCHAR(255)")
    assert "dst_date" in categories_for_db2_type("DATE")
    assert categories_for_db2_type("BLOB(1MB)") == categories_for_db2_type("VARCHAR(255)")


def test_categories_fit_the_column_type():
    """A rounding value only fits a decimal column."""
    assert "rounding_number" not in categories_for_db2_type("INTEGER")
    assert "rounding_number" in categories_for_db2_type("DECIMAL(10, 2)")
    assert "unicode" not in categories_for_db2_type("INTEGER")
    assert "dst_date" not in categories_for_db2_type("DECIMAL(10, 2)")


def test_build_plan_covers_all_columns():
    plan = build_plan(demo_table())
    assert [c.column for c in plan.columns] == ["id", "name"]
    assert plan.plan_id


def test_generate_rows_seeded_repeatable():
    plan = build_plan(demo_table(), seed=7)
    base = (1, "alice")
    rows_a = generate_rows(plan, base, 10)
    rows_b = generate_rows(plan, base, 10)
    assert rows_a == rows_b
    assert len(rows_a) == 10


def test_generate_rows_different_seed_differs():
    plan_a = build_plan(demo_table(), seed=1)
    plan_b = build_plan(demo_table(), seed=2)
    assert generate_rows(plan_a, (1, "alice"), 10) != generate_rows(plan_b, (1, "alice"), 10)


def test_generate_rows_rejects_bad_count():
    plan = build_plan(demo_table())
    with pytest.raises(ValueError):
        generate_rows(plan, (1, "alice"), 0)


def test_plan_to_dict_json_safe():
    plan = build_plan(demo_table())
    data = plan_to_dict(plan)
    assert data["table"] == "demo_users"
    assert len(data["columns"]) == 2
    assert data["columns"][0]["value_count"] > 0


def test_text_values_fit_the_byte_width():
    """Db2 counts bytes, Postgres counts characters."""
    from parity.fuzz.values import values_for_column

    values = values_for_column("VARCHAR(2)", "unicode")
    assert all(len(value.encode("utf-8")) <= 2 for value in values if value)
    assert values != ()
