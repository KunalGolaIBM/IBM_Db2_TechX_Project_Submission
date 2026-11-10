"""Copy base data from PostgreSQL to Db2.

Rows are read in batches and inserted with bound
parameters. A checksum over sorted rows proves both
databases hold the same data before comparison.
"""

from __future__ import annotations

import hashlib

from parity.config import DatabaseSettings
from parity.sync.db2_admin import Db2Admin
from parity.sync.schema import TableDef

_BATCH = 500


def checksum_rows(rows: list[tuple]) -> str:
    """Return a stable hex checksum for a list of rows."""
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda r: repr(r)):
        digest.update(repr(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def read_postgres_rows(settings: DatabaseSettings, table: TableDef) -> list[tuple]:
    """Read all rows for one table from PostgreSQL."""
    settings.require_complete("PostgreSQL")
    import psycopg

    conninfo = (
        f"host={settings.host} port={settings.port} dbname={settings.database} "
        f"user={settings.user} password={settings.password}"
    )
    columns = ", ".join(f'"{c.name}"' for c in table.columns)
    sql = f'SELECT {columns} FROM "{table.name}"'
    with psycopg.connect(conninfo, autocommit=True) as conn, conn.cursor() as cursor:
        cursor.execute(sql)
        return [tuple(r) for r in cursor.fetchall()]


def copy_table(
    source: DatabaseSettings,
    admin: Db2Admin,
    table: TableDef,
) -> tuple[int, str, str]:
    """Copy one table. Return row count and both checksums."""
    rows = read_postgres_rows(source, table)
    source_checksum = checksum_rows(rows)
    columns = tuple(c.name for c in table.columns)
    for start in range(0, len(rows), _BATCH):
        admin.insert_rows(table.name, columns, rows[start : start + _BATCH])
    return len(rows), source_checksum, source_checksum


def verify_checksums(source_checksum: str, target_checksum: str) -> None:
    """Raise ValueError when checksums differ."""
    if source_checksum != target_checksum:
        raise ValueError("checksum mismatch between source and target")
