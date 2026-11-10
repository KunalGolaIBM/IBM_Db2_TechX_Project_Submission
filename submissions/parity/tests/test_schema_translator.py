"""Tests for the schema aware translator."""

from parity.sync.schema import ColumnDef, TableDef
from parity.translate.rules import translate
from parity.translate.schema import SchemaContext


def schema() -> SchemaContext:
    tables = (
        TableDef(
            name="order_items",
            columns=(
                ColumnDef(name="id", db2_type="INTEGER", nullable=False, primary_key=True),
                ColumnDef(name="quantity", db2_type="INTEGER", nullable=True),
                ColumnDef(name="unit_price", db2_type="DECIMAL(10, 2)", nullable=True),
            ),
        ),
        TableDef(
            name="products",
            columns=(
                ColumnDef(name="id", db2_type="INTEGER", nullable=False, primary_key=True),
                ColumnDef(name="stock", db2_type="INTEGER", nullable=True),
                ColumnDef(name="price", db2_type="DECIMAL(10, 2)", nullable=True),
            ),
        ),
    )
    return SchemaContext.from_tables(tables)


def test_sum_of_integer_column_gets_a_bigint_cast():
    result = translate("SELECT SUM(quantity) FROM order_items", schema=schema())
    assert result.db2_sql == (
        "SELECT SUM(CAST(quantity AS BIGINT)) AS sum FROM order_items"
    )
    assert "sum_to_bigint" in result.applied_rules


def test_sum_of_decimal_column_is_left_alone():
    result = translate("SELECT SUM(unit_price) FROM order_items", schema=schema())
    assert result.db2_sql == "SELECT SUM(unit_price) AS sum FROM order_items"
    assert "sum_to_bigint" not in result.applied_rules


def test_sum_without_schema_is_left_alone():
    result = translate("SELECT SUM(quantity) FROM order_items")
    assert result.db2_sql == "SELECT SUM(quantity) AS sum FROM order_items"
    assert "sum_to_bigint" not in result.applied_rules


def test_sum_with_a_qualified_column():
    result = translate(
        "SELECT SUM(oi.quantity) FROM order_items oi", schema=schema()
    )
    assert result.db2_sql == (
        "SELECT SUM(CAST(oi.quantity AS BIGINT)) AS sum FROM order_items oi"
    )


def test_sum_of_an_unknown_column_is_left_alone():
    result = translate("SELECT SUM(mystery) FROM order_items", schema=schema())
    assert result.db2_sql == "SELECT SUM(mystery) AS sum FROM order_items"
    assert "sum_to_bigint" not in result.applied_rules


def test_sum_over_a_join_uses_the_right_table():
    result = translate(
        "SELECT SUM(stock) FROM products", schema=schema()
    )
    assert "sum_to_bigint" in result.applied_rules


def test_column_type_lookup():
    context = schema()
    assert context.column_type("order_items", "QUANTITY") == "INTEGER"
    assert context.column_type("order_items", "missing") is None


def test_resolve_type_needs_one_answer():
    context = schema()
    assert context.resolve_type(("order_items",), "quantity") == "INTEGER"
    assert context.resolve_type(("order_items", "products"), "id") == "INTEGER"
    assert context.resolve_type(("order_items",), "missing") is None


def test_is_integer():
    context = schema()
    assert context.is_integer(("order_items",), "quantity") is True
    assert context.is_integer(("order_items",), "unit_price") is False
    assert context.is_integer(("order_items",), "missing") is False


def test_primary_key_is_in_the_db2_ddl():
    from parity.sync.schema import build_create_table

    table = TableDef(
        name="t",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False, primary_key=True),
            ColumnDef(name="name", db2_type="VARCHAR(50)", nullable=True),
        ),
    )
    ddl = build_create_table(table)
    assert 'PRIMARY KEY ("ID")' in ddl


def test_ddl_without_a_key_has_no_key():
    from parity.sync.schema import build_create_table

    table = TableDef(
        name="t",
        columns=(ColumnDef(name="name", db2_type="VARCHAR(50)", nullable=True),),
    )
    assert "PRIMARY KEY" not in build_create_table(table)
