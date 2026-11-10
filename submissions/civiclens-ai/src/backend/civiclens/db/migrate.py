"""Idempotent schema migration driven by ``schema.sql`` and the Db2 catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from civiclens.db.connection import Db2Session

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
_CREATE = re.compile(
    r"^\s*CREATE\s+(?P<kind>TABLE|INDEX|UNIQUE\s+INDEX|VIEW)\s+\{schema\}\.(?P<name>[A-Z0-9_]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DdlStatement:
    kind: str  # TABLE | INDEX | VIEW
    name: str
    template: str


def load_statements(path: Path = SCHEMA_FILE) -> list[DdlStatement]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.strip().startswith("--")]
    statements: list[DdlStatement] = []
    for chunk in "\n".join(lines).split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _CREATE.match(chunk)
        if not match:
            raise ValueError(f"Unsupported statement in schema.sql: {chunk[:80]!r}")
        kind = "INDEX" if "INDEX" in match["kind"].upper() else match["kind"].upper()
        statements.append(DdlStatement(kind=kind, name=match["name"].upper(), template=chunk))
    return statements


_CATALOG_SQL = {
    "SCHEMA": "SELECT 1 FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?",
    "TABLE": "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
    "VIEW": "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
    "INDEX": "SELECT 1 FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ?",
}


def _exists(db: Db2Session, kind: str, name: str | None = None) -> bool:
    params = (db.schema,) if name is None else (db.schema, name)
    return db.fetch_one(_CATALOG_SQL[kind], params) is not None


# Column additions for databases created by an earlier phase (CREATE TABLE above already
# contains these columns for fresh databases). (table, column, ADD COLUMN DDL tail)
COLUMN_UPGRADES: list[tuple[str, str, str]] = [
    (
        "RECOMMENDATIONS",
        "GENERATOR_TYPE",
        "GENERATOR_TYPE VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN'",
    ),
]


def _column_exists(db: Db2Session, table: str, column: str) -> bool:
    return (
        db.fetch_one(
            "SELECT 1 FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TABNAME = ? AND COLNAME = ?",
            (db.schema, table, column),
        )
        is not None
    )


def apply_column_upgrades(db: Db2Session) -> tuple[list[str], list[str]]:
    """Add columns introduced after Phase 00 to pre-existing tables. Returns (skipped, added)."""
    skipped: list[str] = []
    added: list[str] = []
    for table, column, ddl in COLUMN_UPGRADES:
        label = f"COLUMN {db.schema}.{table}.{column}"
        if not _table_exists(db, table):
            continue  # a fresh CREATE TABLE (executed by migrate) already includes the column
        if _column_exists(db, table, column):
            skipped.append(label)
            continue
        db.execute_raw_ddl(f"ALTER TABLE {db.schema}.{table} ADD COLUMN {ddl}")
        added.append(label)
    return skipped, added


def _table_exists(db: Db2Session, table: str) -> bool:
    return _exists(db, "TABLE", table)


def migrate(db: Db2Session) -> dict[str, list[str]]:
    """Create any missing schema objects. Returns created/skipped object names."""
    created: list[str] = []
    skipped: list[str] = []
    if not _exists(db, "SCHEMA"):
        db.execute_raw_ddl(f"CREATE SCHEMA {db.schema}")
        created.append(f"SCHEMA {db.schema}")
    for stmt in load_statements():
        label = f"{stmt.kind} {db.schema}.{stmt.name}"
        if _exists(db, stmt.kind, stmt.name):
            skipped.append(label)
            continue
        db.execute_raw_ddl(db.sql(stmt.template))
        created.append(label)
    col_skipped, col_added = apply_column_upgrades(db)
    created += col_added
    skipped += col_skipped
    return {"created": created, "skipped": skipped}
