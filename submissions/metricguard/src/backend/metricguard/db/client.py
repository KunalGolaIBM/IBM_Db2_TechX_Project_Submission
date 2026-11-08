"""Thin, explicit wrapper around the IBM `ibm_db` driver.

All analytical SQL is executed through `query()` with parameter markers (`?`);
values are never interpolated into SQL text.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterator, Sequence

import ibm_db

from metricguard.config import Settings, get_settings

_SQLSTATE_RE = re.compile(r"SQLSTATE=(\w{5})")
_SQLCODE_RE = re.compile(r"SQLCODE=(-?\d+)")


class Db2Error(RuntimeError):
    """Sanitized Db2 error (never contains credentials or the connection string)."""

    def __init__(self, message: str, *, sqlstate: str | None = None, sqlcode: int | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate
        self.sqlcode = sqlcode

    @classmethod
    def from_driver(cls, prefix: str, raw: str | None) -> "Db2Error":
        raw = raw or ""
        state = _SQLSTATE_RE.search(raw)
        code = _SQLCODE_RE.search(raw)
        # Strip anything that might echo connection attributes.
        cleaned = re.sub(r"PWD=[^;]*;?", "PWD=***;", raw)
        return cls(
            f"{prefix}: {cleaned.strip()}"[:900],
            sqlstate=state.group(1) if state else None,
            sqlcode=int(code.group(1)) if code else None,
        )


@dataclass
class QueryResult:
    columns: list[str]
    column_types: list[str]
    rows: list[tuple[Any, ...]]
    elapsed_ms: float
    truncated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


_NUMERIC_TYPES = {"decimal", "numeric", "decfloat"}


def _coerce(value: Any, type_name: str) -> Any:
    if value is None:
        return None
    if type_name.lower() in _NUMERIC_TYPES and isinstance(value, str):
        return Decimal(value)
    return value


class Db2Client:
    def __init__(self, settings: Settings | None = None, *, reader: bool = False, role: str | None = None):
        self.settings = settings or get_settings()
        self.role = role or ("reader" if reader else "admin")
        self.reader = self.role == "reader"
        self._conn = None

    # -- connection lifecycle -------------------------------------------------
    def connect(self) -> "Db2Client":
        if self._conn is not None:
            return self
        try:
            self._conn = ibm_db.connect(self.settings.connection_string(role=self.role), "", "")  # type: ignore[arg-type]
        except Exception as exc:  # ibm_db raises plain Exception
            raise Db2Error.from_driver("Db2 connection failed", str(exc)) from None
        ibm_db.autocommit(self._conn, ibm_db.SQL_AUTOCOMMIT_ON)
        return self

    def close(self) -> None:
        if self._conn is not None:
            try:
                ibm_db.close(self._conn)
            finally:
                self._conn = None

    def __enter__(self) -> "Db2Client":
        return self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def conn(self):
        if self._conn is None:
            self.connect()
        return self._conn

    # -- execution ------------------------------------------------------------
    def query(
        self,
        sql: str,
        params: Sequence[Any] = (),
        *,
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
    ) -> QueryResult:
        """Run a SELECT with parameter markers. Fetches up to max_rows (+1 to detect truncation)."""
        timeout = timeout_seconds or self.settings.query_timeout_seconds
        start = time.perf_counter()
        try:
            stmt = ibm_db.prepare(self.conn, sql)
            if not stmt:
                raise Db2Error.from_driver("Db2 prepare failed", ibm_db.stmt_errormsg())
            ibm_db.set_option(stmt, {ibm_db.SQL_ATTR_QUERY_TIMEOUT: timeout}, 0)
            ibm_db.execute(stmt, tuple(params))
        except Db2Error:
            raise
        except Exception as exc:
            raise Db2Error.from_driver("Db2 query failed", ibm_db.stmt_errormsg() or str(exc)) from None

        ncols = ibm_db.num_fields(stmt)
        columns = [ibm_db.field_name(stmt, i) for i in range(ncols)]
        types = [str(ibm_db.field_type(stmt, i)) for i in range(ncols)]
        rows: list[tuple[Any, ...]] = []
        truncated = False
        try:
            row = ibm_db.fetch_tuple(stmt)
            while row:
                if max_rows is not None and len(rows) >= max_rows:
                    truncated = True
                    break
                rows.append(tuple(_coerce(v, t) for v, t in zip(row, types)))
                row = ibm_db.fetch_tuple(stmt)
        except Exception as exc:
            raise Db2Error.from_driver("Db2 fetch failed", ibm_db.stmt_errormsg() or str(exc)) from None
        finally:
            ibm_db.free_stmt(stmt)
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(columns, types, rows, round(elapsed, 2), truncated)

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        result = self.query(sql, params, max_rows=1)
        return result.rows[0][0] if result.rows else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a DDL/DML statement. Returns affected row count (or -1)."""
        try:
            if params:
                stmt = ibm_db.prepare(self.conn, sql)
                ibm_db.execute(stmt, tuple(params))
            else:
                stmt = ibm_db.exec_immediate(self.conn, sql)
            count = ibm_db.num_rows(stmt)
            ibm_db.free_stmt(stmt)
            return count
        except Exception as exc:
            raise Db2Error.from_driver("Db2 statement failed", ibm_db.stmt_errormsg() or str(exc)) from None

    def execute_many(self, sql: str, rows: Sequence[Sequence[Any]], batch_size: int = 500) -> int:
        """Bulk insert with a single prepared statement inside one transaction."""
        total = 0
        ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            stmt = ibm_db.prepare(self.conn, sql)
            for i in range(0, len(rows), batch_size):
                chunk = tuple(tuple(r) for r in rows[i : i + batch_size])
                inserted = ibm_db.execute_many(stmt, chunk)
                if inserted is None or inserted is False:
                    raise Db2Error.from_driver("Db2 bulk insert failed", ibm_db.stmt_errormsg())
                total += int(inserted)
            ibm_db.commit(self.conn)
            ibm_db.free_stmt(stmt)
        except Db2Error:
            ibm_db.rollback(self.conn)
            raise
        except Exception as exc:
            ibm_db.rollback(self.conn)
            raise Db2Error.from_driver("Db2 bulk insert failed", ibm_db.stmt_errormsg() or str(exc)) from None
        finally:
            ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_ON)
        return total

    def server_info(self) -> dict[str, Any]:
        info = ibm_db.server_info(self.conn)
        return {
            "dbms_name": getattr(info, "DBMS_NAME", None),
            "dbms_version": getattr(info, "DBMS_VER", None),
            "db_name": getattr(info, "DB_NAME", None),
        }

    def server_identity(self) -> dict[str, Any]:
        """Server identity using only non-fenced sources (works under amd64 emulation too).

        SYSIBM.SYSVERSIONS.VERSIONNUMBER encodes VVRRMMFF, e.g. 12010500 -> 12.1.5.0.
        """
        ident = self.query(
            "SELECT CURRENT SERVER, CURRENT USER, CURRENT TIMESTAMP, "
            "(SELECT MAX(VERSIONNUMBER) FROM SYSIBM.SYSVERSIONS) FROM SYSIBM.SYSDUMMY1"
        ).rows[0]
        vn = int(ident[3]) if ident[3] is not None else None
        level = f"DB2 v{vn // 1000000}.{vn // 10000 % 100}.{vn // 100 % 100}.{vn % 100}" if vn else None
        return {
            **self.server_info(),
            "service_level": level,
            "version_number": vn,
            "current_server": str(ident[0]).strip(),
            "current_user": str(ident[1]).strip(),
            "server_timestamp": ident[2],
        }

    @contextmanager
    def transaction(self) -> Iterator["Db2Client"]:
        ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            yield self
            ibm_db.commit(self.conn)
        except Exception:
            ibm_db.rollback(self.conn)
            raise
        finally:
            ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_ON)
