"""
backend/db.py
-------------
IBM Db2 connection pool + helper for the FastAPI backend.
Reuses the same DSN pattern as src/db/connection.py but is
designed for FastAPI's async/thread lifecycle.
"""

from __future__ import annotations
import os
import threading
import ibm_db
from dotenv import load_dotenv

load_dotenv()

SCHEMA = "MOODMUSIC"

_lock = threading.Lock()
_conn = None   # single shared connection (ibm_db is thread-safe for reads)


def _dsn() -> str:
    def req(k: str) -> str:
        v = os.getenv(k)
        if not v:
            raise RuntimeError(f"Missing required env var: {k}")
        return v
    return (
        f"DATABASE={req('DB2_DATABASE')};"
        f"HOSTNAME={req('DB2_HOST')};"
        f"PORT={req('DB2_PORT')};"
        "PROTOCOL=TCPIP;"
        f"UID={req('DB2_USER')};"
        f"PWD={req('DB2_PASSWORD')};"
    )


def get_conn():
    """
    Return a live ibm_db connection.
    Reconnects automatically if the connection has dropped.
    """
    global _conn
    with _lock:
        if _conn is None or not ibm_db.active(_conn):
            _conn = ibm_db.connect(_dsn(), "", "")
            ibm_db.exec_immediate(_conn, f"SET CURRENT SCHEMA {SCHEMA}")
        return _conn


def fetch_all(stmt) -> list[dict]:
    """Drain an ibm_db statement into a list of dicts."""
    rows: list[dict] = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        # ibm_db returns uppercase keys; convert values to Python types
        rows.append({k: v for k, v in row.items()})
        row = ibm_db.fetch_assoc(stmt)
    return rows


def fetch_one(stmt) -> dict | None:
    row = ibm_db.fetch_assoc(stmt)
    return dict(row) if row else None


def exec_sql(sql: str, params: tuple = ()) -> any:
    """
    Prepare + execute a parameterised SQL statement.
    Returns the ibm_db statement handle (use fetch_* to read results).
    """
    conn = get_conn()
    stmt = ibm_db.prepare(conn, sql)
    for i, val in enumerate(params, start=1):
        ibm_db.bind_param(stmt, i, val)
    ibm_db.execute(stmt)
    return stmt


def exec_immediate(sql: str):
    """Execute a non-parameterised SQL string directly."""
    conn = get_conn()
    return ibm_db.exec_immediate(conn, sql)

