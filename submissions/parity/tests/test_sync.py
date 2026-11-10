"""Tests for schema sync types, DDL builder, and checksums."""

import pytest

from parity.sync.data import checksum_rows, verify_checksums
from parity.sync.schema import ColumnDef, TableDef, build_create_table, quote_ident
from parity.sync.types import map_type, supported_types


def test_map_type_common():
    assert map_type("integer") == "INTEGER"
    assert map_type("character varying") == "VARCHAR(255)"
    assert map_type("timestamp with time zone") == "TIMESTAMP WITH TIME ZONE"
    assert map_type("text") == "VARCHAR(4000)"


def test_map_type_case_insensitive():
    assert map_type("INTEGER") == "INTEGER"


def test_map_type_unknown_rejected():
    with pytest.raises(ValueError, match="no Db2 mapping"):
        map_type("inet")


def test_supported_types_sorted():
    types = supported_types()
    assert list(types) == sorted(types)
    assert "integer" in types


def test_quote_ident():
    assert quote_ident("users") == '"USERS"'
    with pytest.raises(ValueError):
        quote_ident("users; DROP TABLE x")
    with pytest.raises(ValueError):
        quote_ident("")


def test_build_create_table():
    table = TableDef(
        name="users",
        columns=(
            ColumnDef(name="id", db2_type="INTEGER", nullable=False),
            ColumnDef(name="name", db2_type="VARCHAR(255)", nullable=True),
        ),
    )
    sql = build_create_table(table)
    assert sql == 'CREATE TABLE "USERS" ("ID" INTEGER NOT NULL, "NAME" VARCHAR(255))'


def test_checksum_stable_and_order_insensitive():
    rows_a = [(1, "a"), (2, "b")]
    rows_b = [(2, "b"), (1, "a")]
    assert checksum_rows(rows_a) == checksum_rows(rows_b)
    assert checksum_rows(rows_a) != checksum_rows([(1, "a")])


def test_verify_checksums():
    verify_checksums("abc", "abc")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_checksums("abc", "def")


def test_map_type_keeps_text_length():
    assert map_type("character varying", length=2) == "VARCHAR(2)"
    assert map_type("character varying", length=150) == "VARCHAR(150)"
    assert map_type("character", length=10) == "CHAR(10)"


def test_map_type_keeps_decimal_precision():
    assert map_type("numeric", precision=10, scale=2) == "DECIMAL(10, 2)"
    assert map_type("decimal", precision=12, scale=4) == "DECIMAL(12, 4)"


def test_map_type_without_length_uses_the_default():
    assert map_type("character varying") == "VARCHAR(255)"
    assert map_type("numeric") == "DECIMAL(18, 6)"
