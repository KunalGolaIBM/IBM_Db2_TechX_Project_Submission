"""Thin, typed wrapper around the native IBM Db2 driver (ibm_db).

Two connections are used by the application:

* ``admin``  - the manager / application identity. Used for setup, approvals,
  rollbacks and writing the agent audit trail.
* ``agent``  - the least-privileged identity used for every query the LLM
  agents run. It holds role HOTELOPS_AGENT (SELECT + CALL SP_PROPOSE_ACTION).
"""
from __future__ import annotations

import datetime as dt
import decimal
import re
import threading
from collections.abc import Iterable, Sequence
from typing import Any

import ibm_db

from .config import Db2Settings, load_settings

STATEMENT_DELIMITER = re.compile(r"^\s*@\s*$", re.MULTILINE)

# ibm_db sizes OUT string buffers from the placeholder value passed in, so OUT
# VARCHAR parameters need a placeholder at least as long as the longest result.
OUT_TEXT = " " * 1000


class Db2Error(RuntimeError):
    """Raised when Db2 rejects a statement; carries SQLSTATE/SQLCODE text."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _bindable(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    return value


class Db2:
    """One ibm_db connection plus convenience helpers. Thread-safe via a lock."""

    def __init__(self, conn_str: str, label: str, query_timeout: int = 30):
        self.label = label
        self._lock = threading.RLock()
        try:
            self.conn = ibm_db.connect(conn_str, "", "")
        except Exception as exc:  # ibm_db raises plain Exception
            raise Db2Error(f"[{label}] connection failed: {exc}") from exc
        self.query_timeout = query_timeout

    # -- basic operations ---------------------------------------------------
    def _prepare_execute(self, sql: str, params: Sequence[Any] | None):
        try:
            stmt = ibm_db.prepare(self.conn, sql)
            if self.query_timeout:
                ibm_db.set_option(stmt, {ibm_db.SQL_ATTR_QUERY_TIMEOUT: self.query_timeout}, 0)
            ibm_db.execute(stmt, tuple(_bindable(p) for p in (params or ())))
            return stmt
        except Exception as exc:
            msg = ibm_db.stmt_errormsg() or str(exc)
            raise Db2Error(msg) from exc

    def query(self, sql: str, params: Sequence[Any] | None = None, max_rows: int | None = None) -> list[dict]:
        with self._lock:
            stmt = self._prepare_execute(sql, params)
            rows: list[dict] = []
            try:
                # ibm_db returns DECIMAL as str: convert those columns to float
                decimal_cols = {
                    ibm_db.field_name(stmt, i)
                    for i in range(ibm_db.num_fields(stmt))
                    if str(ibm_db.field_type(stmt, i)).lower() in ("decimal", "numeric", "decfloat")
                }
                row = ibm_db.fetch_assoc(stmt)
                while row:
                    rows.append({k: (float(v) if k in decimal_cols and v is not None else _jsonable(v))
                                 for k, v in row.items()})
                    if max_rows and len(rows) >= max_rows:
                        break
                    row = ibm_db.fetch_assoc(stmt)
            except Exception as exc:  # errors raised while fetching (e.g. SQL16402N, SQL0802N)
                raise Db2Error(ibm_db.stmt_errormsg(stmt) or str(exc)) from exc
            finally:
                ibm_db.free_result(stmt)
            return rows

    def scalar(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        rows = self.query(sql, params, max_rows=1)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> int:
        with self._lock:
            stmt = self._prepare_execute(sql, params)
            count = ibm_db.num_rows(stmt)
            ibm_db.free_result(stmt)
            return count

    def bulk_insert(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        """Prepare once, execute per row, commit once (handles NULLs, unlike execute_many)."""
        count = 0
        with self._lock:
            ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
            try:
                stmt = ibm_db.prepare(self.conn, sql)
                for row in rows:
                    ibm_db.execute(stmt, tuple(_bindable(v) for v in row))
                    count += 1
                ibm_db.commit(self.conn)
            except Exception as exc:
                ibm_db.rollback(self.conn)
                raise Db2Error(ibm_db.stmt_errormsg() or str(exc)) from exc
            finally:
                ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_ON)
        return count

    def call(self, proc: str, *args: Any) -> tuple:
        """CALL a stored procedure; returns the (in + out) parameter tuple."""
        with self._lock:
            try:
                result = ibm_db.callproc(self.conn, proc, tuple(args))
            except Exception as exc:
                raise Db2Error(ibm_db.stmt_errormsg() or ibm_db.conn_errormsg() or str(exc)) from exc
            if isinstance(result, tuple):
                stmt, *params = result
                return tuple(p.strip() if isinstance(p, str) else p for p in params)
            return ()

    def run_script(self, script: str, replacements: dict[str, str] | None = None,
                   ignore_sqlstates: tuple[str, ...] = ()) -> int:
        """Execute a multi-statement script whose statements are separated by '@' lines."""
        for key, value in (replacements or {}).items():
            script = script.replace("{" + key + "}", value)
        done = 0
        for raw in STATEMENT_DELIMITER.split(script):
            sql = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--")).strip()
            if not sql:
                continue
            try:
                self.execute(sql)
            except Db2Error as exc:
                if any(state in str(exc) for state in ignore_sqlstates):
                    continue
                raise Db2Error(f"{exc}\n--- while running ---\n{sql[:600]}") from exc
            done += 1
        return done

    def close(self) -> None:
        try:
            ibm_db.close(self.conn)
        except Exception:
            pass


_connections: dict[str, Db2] = {}
_conn_lock = threading.Lock()


def get_db(role: str = "admin") -> Db2:
    """Return a cached connection for role 'admin' or 'agent'."""
    with _conn_lock:
        if role in _connections:
            return _connections[role]
        s: Db2Settings = load_settings().db2
        if role == "admin":
            conn = Db2(s.conn_str(s.admin_user, s.admin_password), "admin")
        elif role == "agent":
            conn = Db2(s.conn_str(s.agent_user, s.agent_password), "agent")
        else:
            raise ValueError(f"unknown role {role}")
        _connections[role] = conn
        return conn


def reset_connections() -> None:
    with _conn_lock:
        for conn in _connections.values():
            conn.close()
        _connections.clear()


def vector_literal(values: Sequence[float]) -> str:
    """Format an embedding as the text form accepted by Db2's VECTOR() function."""
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
