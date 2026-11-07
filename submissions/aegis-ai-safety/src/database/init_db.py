#!/usr/bin/env python3
"""Initialize the AEGIS Db2 schema.

Usage (from the repository root, with the backend dependencies installed):

    python database/init_db.py            # create schema + tables if missing
    python database/init_db.py --drop     # drop AEGIS tables first (local only)
    python database/init_db.py --stats    # show table counts after init

Credentials are read from the environment / .env. Nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ibm_db  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.connection import validate_identifier  # noqa: E402

TABLES = [
    "EVIDENCE_LINKS",
    "VERIFICATION_RESULTS",
    "CLAIMS",
    "VERIFICATION_SESSIONS",
    "PASSAGES",
    "DOCUMENTS",
]
SCHEMA_FILE = Path(__file__).with_name("schema.sql")
INDEXES_FILE = Path(__file__).with_name("indexes.sql")

# Columns added after the initial release. init_db checks SYSCAT.COLUMNS and
# applies each migration once, so existing local databases are upgraded safely.
COLUMN_MIGRATIONS = [
    ("DOCUMENTS", "PROCESSING_STATUS", "VARCHAR(32) NOT NULL DEFAULT 'READY'"),
    ("DOCUMENTS", "EXTERNAL_ID", "VARCHAR(100)"),
    ("PASSAGES", "CHAR_START", "INTEGER"),
    ("PASSAGES", "CHAR_END", "INTEGER"),
    ("VERIFICATION_SESSIONS", "COMPLETED_AT", "TIMESTAMP"),
    ("VERIFICATION_SESSIONS", "DURATION_MS", "INTEGER"),
    ("VERIFICATION_RESULTS", "NUMERICAL_ANALYSIS", "VARCHAR(4000)"),
    ("VERIFICATION_RESULTS", "HUMAN_REVIEW_STATUS", "VARCHAR(32) NOT NULL DEFAULT 'PENDING'"),
    ("EVIDENCE_LINKS", "EVIDENCE_RELATIONSHIP", "VARCHAR(32)"),
]


def _error_code(exc: Exception) -> int | None:
    try:
        code = getattr(exc, "sqlcode", None)
        if code not in (None, 0):
            return int(code)
    except (TypeError, ValueError):
        pass
    match = re.search(r"SQLCODE=(-?\d+)", str(exc))
    return int(match.group(1)) if match else None


def _run(connection, sql: str, *, ignore: tuple[int, ...] = ()) -> None:
    try:
        statement = ibm_db.exec_immediate(connection, sql)
        ibm_db.free_stmt(statement)
    except Exception as exc:
        code = _error_code(exc)
        message = str(exc)
        # -601: object already exists. 605 / SQLSTATE 01550: a matching index
        # already exists (warning). Re-running init must be idempotent.
        if code in ignore or code == 605 or code == 612 or "01550" in message:
            print(f"  skipped (SQLCODE {code}): {' '.join(sql.split())[:70]}...")
            return
        raise RuntimeError(f"SQL failed ({code}): {' '.join(sql.split())[:160]}") from exc


def _schema_exists(connection, schema: str) -> bool:
    # `schema` has already passed validate_identifier, so inlining is safe and
    # avoids the parameter-marker crash in ibm_db.exec_immediate on arm64.
    statement = ibm_db.exec_immediate(
        connection,
        f"SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = '{schema}'",
    )
    try:
        return bool(ibm_db.fetch_assoc(statement))
    finally:
        ibm_db.free_stmt(statement)


def _drop_tables(connection) -> None:
    print("Dropping AEGIS tables (local reset)...")
    for table in TABLES:
        _run(connection, f"DROP TABLE {table}", ignore=(-204,))
    ibm_db.commit(connection)


def _column_exists(connection, schema: str, table: str, column: str) -> bool:
    statement = ibm_db.exec_immediate(
        connection,
        (
            "SELECT 1 FROM SYSCAT.COLUMNS "
            f"WHERE TABSCHEMA = '{schema}' AND TABNAME = '{table}' AND COLNAME = '{column}'"
        ),
    )
    try:
        return bool(ibm_db.fetch_assoc(statement))
    finally:
        ibm_db.free_stmt(statement)


def _apply_migrations(connection, schema: str) -> None:
    applied = 0
    for table, column, definition in COLUMN_MIGRATIONS:
        if _column_exists(connection, schema, table, column):
            continue
        print(f"  migrating {table}.{column} ...")
        _run(connection, f"ALTER TABLE {table} ADD COLUMN {column} {definition}", ignore=(-612,))
        applied += 1
    if applied:
        ibm_db.commit(connection)
        print(f"  applied {applied} column migration(s).")
    else:
        print("  schema columns are current.")


def _execute_file(connection, path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if not line.strip().startswith("--")]
    statements = [part.strip() for part in "\n".join(lines).split(";") if part.strip()]
    for statement in statements:
        _run(connection, statement, ignore=(-601,))
    ibm_db.commit(connection)


def _print_stats(connection, schema: str) -> None:
    print("\nAEGIS tables:")
    for table in TABLES:
        statement = ibm_db.exec_immediate(
            connection, f"SELECT COUNT(*) AS TOTAL FROM {table}"
        )
        row = ibm_db.fetch_assoc(statement)
        ibm_db.free_stmt(statement)
        print(f"  {table:<24} {row['TOTAL'] if row else 0:>6} rows")

    statement = ibm_db.exec_immediate(
        connection,
        f"SELECT TABNAME, TYPE FROM SYSCAT.TABLES WHERE TABSCHEMA = '{schema}' ORDER BY TABNAME",
    )
    found = []
    row = ibm_db.fetch_assoc(statement)
    while row:
        found.append(row["TABNAME"])
        row = ibm_db.fetch_assoc(statement)
    ibm_db.free_stmt(statement)
    missing = [table for table in TABLES if table not in found]
    if missing:
        print(f"  WARNING: missing tables: {', '.join(missing)}")
    else:
        print("  All six required tables are present.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the AEGIS IBM Db2 schema")
    parser.add_argument("--drop", action="store_true", help="Drop existing AEGIS tables first")
    parser.add_argument("--stats", action="store_true", help="Print table counts")
    args = parser.parse_args()

    settings = get_settings()
    schema = validate_identifier(settings.db2_schema)
    if not settings.db2_password:
        print("ERROR: DB2_PASSWORD is not set. Copy .env.example to .env and configure it.")
        return 2

    print(f"Connecting to {settings.db2_database} at {settings.db2_host}:{settings.db2_port} ...")
    try:
        connection = ibm_db.connect(settings.db2_dsn, "", "")
    except Exception as exc:
        code = _error_code(exc)
        print(f"ERROR: could not connect to IBM Db2 (SQLCODE {code}).")
        print("Check that the database is running and DB2_* credentials are correct.")
        return 1

    try:
        if not _schema_exists(connection, schema):
            print(f"Creating schema {schema} ...")
            _run(connection, f"CREATE SCHEMA {schema}")
            ibm_db.commit(connection)
        _run(connection, f'SET CURRENT SCHEMA "{schema}"')
        if args.drop:
            _drop_tables(connection)
        print(f"Applying {SCHEMA_FILE.name} ...")
        _execute_file(connection, SCHEMA_FILE)
        print("Checking schema migrations ...")
        _apply_migrations(connection, schema)
        print(f"Applying {INDEXES_FILE.name} ...")
        _execute_file(connection, INDEXES_FILE)
        print(f"Schema {schema} initialized.")
        if args.stats:
            _print_stats(connection, schema)
    finally:
        ibm_db.close(connection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
