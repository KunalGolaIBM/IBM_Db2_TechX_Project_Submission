"""Create the TechX Db2 schema and its four tables.

Run from the repository root:
    python -m backend.scripts.init_db
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import ibm_db

from . import close_quietly, connect, db2_schema, failure_label


_EXPECTED_TABLES = {
    "CHESS_GAMES",
    "CHESS_MOVES",
    "CHESS_GAME_ANALYSIS",
    "CHESS_OPENING_STATISTICS",
}
_TABLE_PATTERN = re.compile(r"^CREATE\s+TABLE\s+[A-Z][A-Z0-9_]*\.([A-Z][A-Z0-9_]*)\s*\(", re.IGNORECASE)


def _exists(connection: Any, query: str, *values: str) -> bool:
    statement = ibm_db.prepare(connection, query)
    ibm_db.execute(statement, values)
    return bool(ibm_db.fetch_tuple(statement))


def _statements(schema: str) -> list[tuple[str, str]]:
    sql_path = Path(__file__).resolve().parents[1] / "schema.sql"
    source = "\n".join(
        line for line in sql_path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ).replace("${SCHEMA}", schema)
    parsed: list[tuple[str, str]] = []
    for raw in source.split(";"):
        sql = raw.strip()
        if not sql:
            continue
        match = _TABLE_PATTERN.match(sql)
        if not match:
            raise RuntimeError("schema.sql may contain only CREATE TABLE statements")
        parsed.append((match.group(1).upper(), sql))
    if {name for name, _ in parsed} != _EXPECTED_TABLES or len(parsed) != 4:
        raise RuntimeError("schema.sql must define exactly the four expected tables")
    return parsed


def initialize() -> None:
    schema = db2_schema()
    connection = None
    try:
        connection = connect()
        schema_exists = _exists(
            connection,
            "SELECT 1 FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ? FETCH FIRST 1 ROW ONLY",
            schema,
        )
        if not schema_exists:
            ibm_db.exec_immediate(connection, f"CREATE SCHEMA {schema}")

        for table_name, sql in _statements(schema):
            table_exists = _exists(
                connection,
                "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ? FETCH FIRST 1 ROW ONLY",
                schema,
                table_name,
            )
            if not table_exists:
                ibm_db.exec_immediate(connection, sql)
        ibm_db.commit(connection)
        print(f"Db2 schema {schema} is ready with four chess tables.")
    except Exception:
        if connection is not None:
            ibm_db.rollback(connection)
        raise SystemExit(failure_label("Db2 schema initialization", connection)) from None
    finally:
        close_quietly(connection)


if __name__ == "__main__":
    initialize()
