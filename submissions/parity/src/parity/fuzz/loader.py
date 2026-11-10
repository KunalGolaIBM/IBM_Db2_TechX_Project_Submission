"""Load fuzz rows into both databases.

The same rows must land in Postgres and in Db2, byte for
byte. If the data differs, any result difference would come
from the data and not from the databases. Every insert uses
bound parameters.
"""

from __future__ import annotations

from parity.config import DatabaseSettings
from parity.sync.schema import TableDef

KEY_OFFSET = 1_000_000


def delete_fuzz_rows(settings: DatabaseSettings, admin, table: TableDef) -> int:
    """Remove the rows of an earlier fuzz run.

    The fuzzer writes rows with a key above the offset. A
    clean run keeps the fuzz dataset reproducible: the same
    seed gives the same rows.
    """
    key_columns = [column.name for column in table.columns if column.primary_key]
    if not key_columns:
        return 0
    key_column = key_columns[0]
    condition = f'"{key_column}" >= {KEY_OFFSET}'
    settings.require_complete("PostgreSQL")
    import psycopg

    conninfo = (
        f"host={settings.host} port={settings.port} dbname={settings.database} "
        f"user={settings.user} password={settings.password}"
    )
    with psycopg.connect(conninfo, autocommit=True) as conn, conn.cursor() as cursor:
        cursor.execute(f'DELETE FROM "{table.name}" WHERE {condition}')
        deleted = cursor.rowcount
    db2_condition = f'"{key_column.upper()}" >= {KEY_OFFSET}'
    admin.execute_ddl(f'DELETE FROM "{table.name.upper()}" WHERE {db2_condition}')
    return max(deleted, 0)


def load_postgres_rows(
    settings: DatabaseSettings, table: TableDef, rows: list[tuple]
) -> int:
    """Insert rows into Postgres. Return the row count."""
    settings.require_complete("PostgreSQL")
    import psycopg

    if not rows:
        return 0
    conninfo = (
        f"host={settings.host} port={settings.port} dbname={settings.database} "
        f"user={settings.user} password={settings.password}"
    )
    columns = ", ".join(f'"{c.name}"' for c in table.columns)
    marks = ", ".join("%s" for _ in table.columns)
    sql = f'INSERT INTO "{table.name}" ({columns}) VALUES ({marks})'
    with psycopg.connect(conninfo, autocommit=True) as conn, conn.cursor() as cursor:
        cursor.executemany(sql, rows)
    return len(rows)


def load_db2_rows(admin, table: TableDef, rows: list[tuple]) -> int:
    """Insert rows into Db2. Return the row count."""
    if not rows:
        return 0
    columns = tuple(column.name for column in table.columns)
    admin.insert_rows(table.name, columns, rows)
    return len(rows)


def read_base_rows(
    settings: DatabaseSettings, table: TableDef, limit: int = 1
) -> list[tuple]:
    """Read some rows from Postgres to use as a fuzz base."""
    settings.require_complete("PostgreSQL")
    import psycopg

    conninfo = (
        f"host={settings.host} port={settings.port} dbname={settings.database} "
        f"user={settings.user} password={settings.password}"
    )
    columns = ", ".join(f'"{c.name}"' for c in table.columns)
    sql = f'SELECT {columns} FROM "{table.name}" LIMIT {limit}'
    with psycopg.connect(conninfo, autocommit=True) as conn, conn.cursor() as cursor:
        cursor.execute(sql)
        return [tuple(row) for row in cursor.fetchall()]
