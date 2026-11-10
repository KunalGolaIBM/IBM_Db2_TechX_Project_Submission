"""The bridge client. Runs inside a Linux container.

Reads one statement from stdin and writes the result as
JSON to stdout.

Two forms are accepted:

- Plain SQL text. The statement runs without parameters.
  This is the read only form used by the query executor.
- A JSON envelope with a `sql` text and a `params` list.
  The parameters are bound in the container, never pasted
  into the SQL text. This is the form used for writes.

Values are encoded as text so dates and decimals survive
the trip. NULL stays JSON null.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def encode_value(value: Any) -> Any:
    """Encode one cell value for JSON transport."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _is_query(sql: str) -> bool:
    """True when the statement returns a result set.

    A statement that changes data has no result set, and
    the driver cannot read the columns of such a
    statement.
    """
    return sql.strip().upper().startswith(("SELECT", "WITH", "VALUES"))


def _run_statement(conn, sql: str, params: list[Any]) -> dict[str, Any]:
    """Run one statement with bound parameters."""
    import ibm_db

    if params:
        stmt = ibm_db.prepare(conn, sql)
        for index, value in enumerate(params, start=1):
            ibm_db.bind_param(stmt, index, value)
        ibm_db.execute(stmt)
    else:
        stmt = ibm_db.exec_immediate(conn, sql)
    if not _is_query(sql):
        return {"columns": [], "types": [], "rows": []}
    field_count = ibm_db.num_fields(stmt)
    columns = [ibm_db.field_name(stmt, i) for i in range(field_count)]
    types = [ibm_db.field_type(stmt, i) for i in range(field_count)]
    rows: list[list[Any]] = []
    while True:
        row = ibm_db.fetch_tuple(stmt)
        if row is False or row is None:
            break
        rows.append([encode_value(value) for value in row])
    return {"columns": columns, "types": types, "rows": rows}


def run_and_encode(sql: str, settings, params: list[Any] | None = None) -> dict[str, Any]:
    """Run SQL on Db2. Return a JSON safe dict."""
    import ibm_db

    from parity.engine.db2 import _connection_string

    conn = ibm_db.connect(_connection_string(settings), "", "")
    try:
        return _run_statement(conn, sql, list(params or []))
    finally:
        ibm_db.close(conn)


def parse_request(text: str) -> tuple[str, list[Any]]:
    """Read the request. Return the SQL text and the parameters."""
    stripped = text.strip()
    if not stripped:
        return "", []
    if not stripped.startswith("{"):
        return stripped, []
    payload = json.loads(stripped)
    return str(payload.get("sql", "")), list(payload.get("params", []))


def main() -> int:
    """Read the request from stdin. Write the result as JSON."""
    text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty SQL on stdin"}))
        return 2
    from parity.config import load_settings

    _, db2_settings = load_settings()
    try:
        sql, params = parse_request(text)
        if not sql:
            raise ValueError("empty SQL on stdin")
        result = run_and_encode(sql, db2_settings, params)
    except Exception as exc:  # noqa: BLE001 - any Db2 failure becomes error JSON
        print(json.dumps({"error": str(exc)[:500]}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
