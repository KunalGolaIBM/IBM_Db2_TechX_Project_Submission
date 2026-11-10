"""Db2 access layer.

Two interchangeable drivers, selected with ``DB2_DRIVER``:

* ``ibm_db``      - the native IBM driver through its DB-API wrapper ``ibm_db_dbi`` (default)
* ``sqlalchemy``  - SQLAlchemy with the ``ibm_db_sa`` dialect (``db2+ibm_db://``)

Agents may only call :meth:`Db2Gateway.read`, which runs every statement through the
read-only SQL guard. :meth:`Db2Gateway.execute` is used by fixed, parameterised writers
(audit log, incident reports) and by the demo-data scripts.
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

from .config import Settings
from .sql_guard import validate_readonly
from .temporal_sql import ALLOWED_TABLES

_NAMED = re.compile(r"(?<![:\w'])(:[A-Za-z_]\w*)")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def _to_qmark(sql: str, params: dict) -> tuple[str, tuple]:
    order = []

    def repl(m):
        order.append(m.group(1)[1:])
        return "?"

    return _NAMED.sub(repl, sql), tuple(params[n] for n in order)


class Db2Gateway:
    def __init__(self, settings: Settings):
        if not _IDENT.match(settings.db_schema):
            raise ValueError("DB2_SCHEMA must be a plain identifier")
        self.s = settings
        self._local = threading.local()

    # -- connections -------------------------------------------------------
    def _connect(self):
        s = self.s
        if s.db_driver == "sqlalchemy":
            from sqlalchemy import create_engine  # imported lazily: optional path

            if not hasattr(self, "_engine"):
                url = f"db2+ibm_db://{s.db_user}:{quote_plus(s.db_password)}@{s.db_host}:{s.db_port}/{s.db_name}"
                self._engine = create_engine(url, pool_pre_ping=True)
            conn = self._engine.connect()
        else:
            import ibm_db_dbi  # installed with the ibm_db package

            conn_str = (f"DATABASE={s.db_name};HOSTNAME={s.db_host};PORT={s.db_port};PROTOCOL=TCPIP;"
                        f"UID={s.db_user};PWD={s.db_password};")
            conn = ibm_db_dbi.connect(conn_str, "", "")
        self._local.conn = conn
        self._run(conn, f"SET CURRENT SCHEMA = {s.db_schema}", None)
        return conn

    @property
    def conn(self):
        return getattr(self._local, "conn", None) or self._connect()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.conn = None

    # -- low-level execution ----------------------------------------------
    def _run(self, conn, sql: str, params: Optional[dict]):
        """Execute one statement; return (columns, rows)."""
        params = params or {}
        if self.s.db_driver == "sqlalchemy":
            from sqlalchemy import text

            res = conn.execute(text(sql), params)
            if res.returns_rows:
                cols = [c.lower() for c in res.keys()]
                return cols, [tuple(r) for r in res.fetchall()]
            return [], []
        cur = conn.cursor()
        try:
            if params:
                q, args = _to_qmark(sql, params)
                cur.execute(q, args)
            else:
                cur.execute(sql)
            if cur.description:
                cols = [d[0].lower() for d in cur.description]
                return cols, [tuple(r) for r in cur.fetchall()]
            return [], []
        finally:
            cur.close()

    def _commit(self, conn) -> None:
        conn.commit()

    def _rollback(self, conn) -> None:
        try:
            conn.rollback()
        except Exception:  # pragma: no cover - best effort
            pass

    # -- public API ---------------------------------------------------------
    def read(self, sql: str, params: Optional[dict] = None, *, extra_tables: Optional[set] = None) -> list[dict]:
        """Run a guarded, read-only query and return rows as dicts with lower-case keys."""
        safe = validate_readonly(sql, ALLOWED_TABLES | (extra_tables or set()), self.s.max_rows)
        conn = self.conn
        try:
            cols, rows = self._run(conn, safe, params)
            self._commit(conn)  # ends the read transaction, releases locks
        except Exception:
            self._rollback(conn)
            raise
        return [dict(zip(cols, r)) for r in rows]

    def execute(self, sql: str, params: Optional[dict] = None, *, commit: bool = True) -> list[dict]:
        """Run a fixed statement (writes / DDL). Not reachable from the agents' query path."""
        conn = self.conn
        try:
            cols, rows = self._run(conn, sql, params)
            if commit:
                self._commit(conn)
        except Exception:
            self._rollback(conn)
            raise
        return [dict(zip(cols, r)) for r in rows]

    def commit(self) -> None:
        self._commit(self.conn)

    def rollback(self) -> None:
        self._rollback(self.conn)

    def run_script(self, path: str | Path, *, ignore_errors: bool = False) -> int:
        """Execute a SQL file whose statements are separated by lines containing only ``--#``."""
        text_ = Path(path).read_text(encoding="utf-8")
        statements = [s.strip() for s in re.split(r"^--#\s*$", text_, flags=re.MULTILINE)]
        count = 0
        for stmt in statements:
            if not stmt or all(line.strip().startswith("--") or not line.strip() for line in stmt.splitlines()):
                continue
            try:
                self.execute(stmt)
                count += 1
            except Exception as exc:
                if not ignore_errors:
                    raise RuntimeError(f"{Path(path).name}: statement failed:\n{stmt[:300]}\n-> {exc}") from exc
        return count

    def ping(self) -> dict:
        t0 = time.perf_counter()
        rows = self.execute("VALUES (CURRENT SERVER, CURRENT SCHEMA, CURRENT TIMESTAMP)")
        first: Any = list(rows[0].values()) if rows else []
        return {"ok": True, "server": first[0] if first else None, "schema": first[1] if len(first) > 1 else None,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
