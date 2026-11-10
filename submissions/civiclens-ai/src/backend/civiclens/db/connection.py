"""Thin, explicit wrapper around the native ``ibm_db`` driver.

Design rules:
* Every statement goes through ``ibm_db.prepare`` + ``ibm_db.execute`` with bound
  parameters. Callers never interpolate values into SQL text.
* The only text substitution performed is the schema name, which is validated
  as a Db2 identifier in :mod:`civiclens.config`.
* Writes that span several statements run inside :meth:`Db2Session.transaction`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from civiclens.config import Settings, get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when the native driver is installed
    import ibm_db  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    ibm_db = None  # type: ignore[assignment]


class Db2UnavailableError(RuntimeError):
    """Raised when the driver is missing or a connection cannot be established."""


class Db2Session:
    """A single ibm_db connection with helpers for parameterized statements."""

    def __init__(self, conn: Any, schema: str) -> None:
        self._conn = conn
        self.schema = schema
        self._tx_depth = 0

    # -- SQL helpers ------------------------------------------------------------
    def sql(self, template: str) -> str:
        """Substitute the validated schema name into a static SQL template."""
        return template.replace("{schema}", self.schema)

    def _run(self, sql: str, params: Sequence[Any] = ()) -> Any:
        stmt = ibm_db.prepare(self._conn, sql)
        if params:
            ibm_db.execute(stmt, tuple(params))
        else:
            ibm_db.execute(stmt)
        return stmt

    def execute(self, template: str, params: Sequence[Any] = ()) -> int:
        stmt = self._run(self.sql(template), params)
        rows = ibm_db.num_rows(stmt)
        ibm_db.free_stmt(stmt)
        return rows

    def fetch_all(self, template: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        stmt = self._run(self.sql(template), params)
        rows: list[dict[str, Any]] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            rows.append({k.lower(): v for k, v in row.items()})
            row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_stmt(stmt)
        return rows

    def fetch_one(self, template: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.fetch_all(template, params)
        return rows[0] if rows else None

    def execute_raw_ddl(self, ddl: str) -> None:
        """Execute trusted DDL from schema.sql (never user or LLM input)."""
        ibm_db.exec_immediate(self._conn, ddl)

    # -- transactions ------------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[Db2Session]:
        """Run the block atomically. Re-entrant: only the outermost block commits/rolls back,
        so repository functions can open their own ``transaction()`` and still compose."""
        if self._tx_depth > 0:
            self._tx_depth += 1
            try:
                yield self
            finally:
                self._tx_depth -= 1
            return
        ibm_db.autocommit(self._conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        self._tx_depth = 1
        try:
            yield self
            ibm_db.commit(self._conn)
        except Exception:
            ibm_db.rollback(self._conn)
            raise
        finally:
            self._tx_depth = 0
            ibm_db.autocommit(self._conn, ibm_db.SQL_AUTOCOMMIT_ON)

    def server_info(self) -> dict[str, str]:
        info = ibm_db.server_info(self._conn)
        return {
            "dbms_name": str(getattr(info, "DBMS_NAME", "")),
            "dbms_ver": str(getattr(info, "DBMS_VER", "")),
            "db_name": str(getattr(info, "DB_NAME", "")),
        }

    def close(self) -> None:
        try:
            ibm_db.close(self._conn)
        except Exception:  # pragma: no cover - best effort
            logger.debug("Error while closing Db2 connection", exc_info=True)


def connect(settings: Settings | None = None) -> Db2Session:
    settings = settings or get_settings()
    if ibm_db is None:
        raise Db2UnavailableError("The ibm_db driver is not installed.")
    try:
        conn = ibm_db.connect(settings.db2_connection_string(), "", "")
    except Exception as exc:  # ibm_db raises plain Exception with SQLSTATE text
        # Never log the connection string: it contains the password.
        raise Db2UnavailableError(
            f"Could not connect to {settings.redacted_target()}: {_safe_error(exc)}"
        ) from None
    try:  # Db2's default is to wait forever on a lock; fail fast instead.
        ibm_db.exec_immediate(conn, "SET CURRENT LOCK TIMEOUT 10")
    except Exception:  # pragma: no cover - older servers
        logger.warning("Could not set CURRENT LOCK TIMEOUT")
    return Db2Session(conn, settings.db2_schema)


@contextmanager
def session(settings: Settings | None = None) -> Iterator[Db2Session]:
    db = connect(settings)
    try:
        yield db
    finally:
        db.close()


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    # ibm_db error text does not include PWD, but strip defensively.
    if "PWD=" in text:
        text = text.split("PWD=")[0] + "PWD=***"
    return text[:500]
