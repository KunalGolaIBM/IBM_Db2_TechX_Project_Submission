"""DEV MODE engine — NOT IBM Db2.

Used only when DB_MODE=dev (no Db2 credentials / no Db2 container available).
It executes the *same* migration files and the *same* recursive traceability
SQL as the Db2 path, on Python's embedded SQLite, so the application and its
tests can run anywhere. Every API response and the UI banner label this mode
explicitly; it is never presented as data from a live IBM Db2 instance.

The only dialect translation applied is CLOB(n) -> CLOB (size suffixes are
Db2-specific). No query text is rewritten.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .base import Database, DatabaseError, IntegrityViolation, rows_to_dicts, split_sql

_CLOB = re.compile(r"CLOB\(\s*\d+[KMG]?\s*\)", re.IGNORECASE)


def _ddl_compat(sql: str) -> str:
    return _CLOB.sub("CLOB", sql)


class DevModeDatabase(Database):
    mode = "dev"
    label = "DEV MODE — embedded engine, NOT IBM Db2"

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL" if path != ":memory:" else "PRAGMA journal_mode = MEMORY")
        self._lock = threading.RLock()

    def _wrap(self, exc: Exception) -> DatabaseError:
        if isinstance(exc, sqlite3.IntegrityError):
            return IntegrityViolation(str(exc))
        return DatabaseError(str(exc))

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            try:
                cur = self._conn.execute(sql, tuple(params))
                cols = [d[0] for d in (cur.description or [])]
                return rows_to_dicts(cols, cur.fetchall())
            except sqlite3.Error as exc:
                raise self._wrap(exc) from exc

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._lock:
            try:
                return self._conn.execute(_ddl_compat(sql), tuple(params)).rowcount
            except sqlite3.Error as exc:
                raise self._wrap(exc) from exc

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> None:
        with self._lock:
            try:
                self._conn.executemany(sql, [tuple(p) for p in seq])
            except sqlite3.Error as exc:
                raise self._wrap(exc) from exc

    def execute_script(self, script: str) -> int:
        n = 0
        with self.transaction():
            for stmt in split_sql(script):
                self.execute(stmt)
                n += 1
        return n

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            depth = getattr(self._tx, "depth", 0)
            if depth == 0:
                self._conn.execute("BEGIN")
            self._tx.depth = depth + 1
            try:
                yield
                if depth == 0:
                    self._conn.execute("COMMIT")
            except Exception:
                if depth == 0:
                    self._conn.execute("ROLLBACK")
                raise
            finally:
                self._tx.depth = depth

    def table_exists(self, name: str) -> bool:
        row = self.query_one("SELECT COUNT(*) AS n FROM sqlite_master WHERE type IN ('table','view') AND lower(name) = ?", (name.lower(),))
        return bool(row and row["n"])

    def ping(self) -> dict[str, Any]:
        t0 = time.perf_counter()
        self.query("SELECT 1 AS ok")
        return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "server": f"embedded sqlite {sqlite3.sqlite_version} (dev mode)", "fixpack": None}

    def supports_vector(self) -> bool:
        return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()
