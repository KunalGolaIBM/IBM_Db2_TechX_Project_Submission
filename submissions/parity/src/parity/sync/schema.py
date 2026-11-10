"""Schema introspection and Db2 DDL generation.

Reads table and column info from PostgreSQL
information_schema, then builds Db2 CREATE TABLE
statements. Identifiers are quoted. No user data
is ever placed in DDL text.
"""

from __future__ import annotations

from dataclasses import dataclass

from parity.config import DatabaseSettings
from parity.sync.types import map_type

_IDENT = set("abcdefghijklmnopqrstuvwxyz0123456789_")

_TABLES_SQL = """
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name
"""

_COLUMNS_SQL = """
SELECT column_name, data_type, is_nullable,
       character_maximum_length, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = %s
ORDER BY ordinal_position
"""

_PRIMARY_KEY_SQL = """
SELECT kcu.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_schema = 'public'
"""


@dataclass(frozen=True)
class ColumnDef:
    """One column definition."""

    name: str
    db2_type: str
    nullable: bool
    primary_key: bool = False


@dataclass(frozen=True)
class TableDef:
    """One table definition."""

    name: str
    columns: tuple[ColumnDef, ...]


def quote_ident(name: str) -> str:
    """Quote one identifier for Db2. Uppercase it."""
    clean = name.strip()
    if not clean:
        raise ValueError("empty identifier")
    if any(ch not in _IDENT for ch in clean.lower()):
        raise ValueError(f"unsafe identifier: {name}")
    return f'"{clean.upper()}"'


def build_create_table(table: TableDef) -> str:
    """Build one Db2 CREATE TABLE statement.

    The primary key is kept. A Db2 table without the key
    would accept duplicate rows that Postgres rejects.
    """
    parts = []
    key_columns = []
    for col in table.columns:
        suffix = "" if col.nullable else " NOT NULL"
        parts.append(f"{quote_ident(col.name)} {col.db2_type}{suffix}")
        if col.primary_key:
            key_columns.append(quote_ident(col.name))
    if key_columns:
        parts.append(f"PRIMARY KEY ({', '.join(key_columns)})")
    columns_sql = ", ".join(parts)
    return f"CREATE TABLE {quote_ident(table.name)} ({columns_sql})"


def introspect_postgres(settings: DatabaseSettings) -> tuple[TableDef, ...]:
    """Read all public tables from PostgreSQL."""
    settings.require_complete("PostgreSQL")
    import psycopg

    conninfo = (
        f"host={settings.host} port={settings.port} dbname={settings.database} "
        f"user={settings.user} password={settings.password}"
    )
    tables: list[TableDef] = []
    with psycopg.connect(conninfo, autocommit=True) as conn, conn.cursor() as cursor:
        cursor.execute(_PRIMARY_KEY_SQL)
        primary_keys = {(row[0], row[1]) for row in cursor.fetchall()}
        cursor.execute(_TABLES_SQL)
        names = [row[0] for row in cursor.fetchall()]
        for name in names:
            cursor.execute(_COLUMNS_SQL, (name,))
            columns = tuple(
                ColumnDef(
                    name=row[0],
                    db2_type=map_type(
                        row[1],
                        length=row[3],
                        precision=row[4],
                        scale=row[5],
                    ),
                    nullable=row[2] == "YES",
                    primary_key=(name, row[0]) in primary_keys,
                )
                for row in cursor.fetchall()
            )
            if not columns:
                raise ValueError(f"table has no columns: {name}")
            tables.append(TableDef(name=name, columns=columns))
    return tuple(tables)
