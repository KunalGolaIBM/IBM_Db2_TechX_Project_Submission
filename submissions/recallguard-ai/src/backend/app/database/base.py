"""Database abstraction shared by the IBM Db2 driver and the labelled dev-mode engine.

Both implementations accept the SAME SQL text with qmark ('?') parameter markers
and return rows as dicts with lower-case keys and JSON-friendly values.
"""
from __future__ import annotations

import datetime as dt
import decimal
import re
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(\.\d+)?$")


class DatabaseError(RuntimeError):
    """Raised for any driver-level failure (connection, SQL, constraint)."""


class IntegrityViolation(DatabaseError):
    """Raised when a PK / FK / UNIQUE / CHECK constraint rejects a write."""


def normalize_value(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dt.datetime):
        return v.replace(microsecond=0).isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        m = _TS_RE.match(v)
        if m:
            return f"{m.group(1)}T{m.group(2)}"
        return v
    if isinstance(v, (bytes, bytearray)):
        return v.decode("utf-8", errors="replace")
    return v


def rows_to_dicts(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    cols = [c.lower() for c in columns]
    return [{c: normalize_value(v) for c, v in zip(cols, r)} for r in rows]


class Database(ABC):
    """Minimal repository interface used by every service."""

    mode: str = "abstract"
    label: str = ""

    def __init__(self) -> None:
        self._tx = threading.local()

    @abstractmethod
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...

    @abstractmethod
    def execute(self, sql: str, params: Sequence[Any] = ()) -> int: ...

    @abstractmethod
    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> None: ...

    @abstractmethod
    def execute_script(self, script: str) -> int: ...

    @abstractmethod
    @contextmanager
    def transaction(self) -> Iterator[None]: ...

    @abstractmethod
    def ping(self) -> dict[str, Any]: ...

    @abstractmethod
    def close(self) -> None: ...

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self.query_one(sql, params)
        return next(iter(row.values())) if row else None

    def table_exists(self, name: str) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError


def split_sql(script: str) -> list[str]:
    """Split a migration script on ';' line terminators, dropping comment-only chunks."""
    out = []
    for chunk in re.split(r";\s*\n|;\s*$", script):
        body = "\n".join(l for l in chunk.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            out.append(body)
    return out
