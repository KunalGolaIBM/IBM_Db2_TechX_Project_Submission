"""Tests for the fuzz runner and loader."""



from parity.fuzz.plan import build_plan
from parity.fuzz.runner import fresh_key, prepare_rows
from parity.sync.schema import ColumnDef, TableDef


def customers_table() -> TableDef:
    return TableDef(
        name="customers",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False, primary_key=True),
            ColumnDef(name="name", db2_type="VARCHAR(255)", nullable=True),
            ColumnDef(name="email", db2_type="VARCHAR(255)", nullable=True),
        ),
    )


def test_fresh_key_avoids_the_base_data():
    assert fresh_key(1, 0) == 1_000_001
    assert fresh_key(1, 5) == 1_000_006
    assert fresh_key("a", 2) == "a-fuzz-2"
    assert fresh_key(None, 0) is None


def test_prepare_rows_keeps_keys_unique():
    table = customers_table()
    rows, plan = prepare_rows(table, (1, "alice", "a@example.com"), count=5)
    assert len(rows) == 5
    keys = [row[0] for row in rows]
    assert len(set(keys)) == 5
    assert 1 not in keys
    assert plan.table == "customers"


def test_prepare_rows_never_writes_to_the_key_column():
    table = customers_table()
    rows, _ = prepare_rows(table, (7, "alice", "a@example.com"), count=10)
    assert all(row[0] != 7 for row in rows)


def test_prepare_rows_uses_edge_values():
    table = customers_table()
    rows, _ = prepare_rows(table, (1, "alice", "a@example.com"), count=20)
    values = {row[1] for row in rows}
    assert any(value != "alice" for value in values)


def test_generate_rows_skips_columns():
    from parity.fuzz.plan import FuzzPlan

    plan = FuzzPlan(
        table="t",
        columns=(),
        seed=1,
    )
    assert plan.plan_id


def test_plan_skips_null_for_not_null_column():
    table = TableDef(
        name="t",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False, primary_key=True),
            ColumnDef(name="name", db2_type="VARCHAR(255)", nullable=True),
        ),
    )
    plan = build_plan(table)
    assert "null" not in plan.columns[0].categories
    assert "null" in plan.columns[1].categories


def test_rows_fit_the_column_width():
    table = TableDef(
        name="t",
        columns=(ColumnDef(name="name", db2_type="VARCHAR(3)", nullable=True),),
    )
    rows, _ = prepare_rows(table, ("abc",), count=20)
    assert all(not isinstance(row[0], str) or len(row[0]) <= 3 for row in rows)
