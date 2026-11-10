"""Thin ibm_db helpers. Every statement with user data uses prepare + bound '?' parameters.

Connections are short-lived (opened per operation, closed in finally); nothing is shared
across Streamlit sessions.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Iterator, Sequence

import ibm_db

from config import get_settings


class Db2Error(RuntimeError):
    pass


def _err(conn: Any = None) -> str:
    msg = ibm_db.conn_errormsg(conn) if conn is not None else ibm_db.conn_errormsg()
    return msg or ibm_db.stmt_errormsg() or "unknown Db2 error"


@contextmanager
def connect(autocommit: bool = True, admin: bool = False) -> Iterator[Any]:
    """admin=True uses DB2_ADMIN_UID (schema setup / seed / tests only); the app uses the least-privilege DB2_UID."""
    settings = get_settings()
    if not settings.database or not settings.hostname:
        raise Db2Error("Db2 connection is not configured (set DB_ENV_FILE / DB2_* values).")
    try:
        conn = ibm_db.connect(settings.dsn(admin=admin), "", "")
    except Exception as exc:  # ibm_db raises a bare Exception with SQLSTATE text
        raise Db2Error(f"Db2 connect failed: {str(exc).splitlines()[0][:200]}") from None
    try:
        if not autocommit:
            ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        yield conn
    finally:
        try:
            if not autocommit:
                ibm_db.rollback(conn)  # no-op after commit; discards anything uncommitted
                ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
        finally:
            ibm_db.close(conn)


def execute(conn: Any, sql: str, params: Sequence[Any] = ()) -> Any:
    stmt = ibm_db.prepare(conn, sql)
    if not stmt:
        raise Db2Error(_err(conn))
    if not ibm_db.execute(stmt, tuple(_bind(p) for p in params)):
        raise Db2Error(ibm_db.stmt_errormsg(stmt))
    return stmt


def query(conn: Any, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    stmt = execute(conn, sql, params)
    rows: list[dict[str, Any]] = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        rows.append({k.upper(): v for k, v in row.items()})
        row = ibm_db.fetch_assoc(stmt)
    ibm_db.free_result(stmt)
    return rows


def _bind(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def server_identity() -> dict[str, Any]:
    """Run a real query and return non-secret server identity."""
    with connect() as conn:
        rows = query(
            conn,
            "SELECT CURRENT SERVER AS SERVER, CURRENT SCHEMA AS SCHEMA_NAME, SESSION_USER AS DB_USER, CURRENT TIMESTAMP AS NOW FROM SYSIBM.SYSDUMMY1",
        )
        info = ibm_db.server_info(conn)
        rows[0]["DBMS_VER"] = getattr(info, "DBMS_VER", None)
        rows[0]["DBMS_NAME"] = getattr(info, "DBMS_NAME", None)
        return rows[0]
