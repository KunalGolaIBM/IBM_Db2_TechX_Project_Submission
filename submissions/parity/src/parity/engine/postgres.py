"""PostgreSQL executor.

Runs read queries with psycopg. Sets a statement timeout
on the server side, caps rows, and returns a ResultSet.
"""

from __future__ import annotations

from parity.config import DatabaseSettings
from parity.engine.result import ResultSet
from parity.engine.safety import assert_read_only

_DEFAULT_ROW_LIMIT = 100_000


class PostgresExecutor:
    """Execute read queries on PostgreSQL."""

    def __init__(self, settings: DatabaseSettings, row_limit: int = _DEFAULT_ROW_LIMIT) -> None:
        settings.require_complete("PostgreSQL")
        if row_limit <= 0:
            raise ValueError("row_limit must be positive")
        self._settings = settings
        self._row_limit = row_limit

    def execute(self, sql: str, timeout_seconds: float = 30.0) -> ResultSet:
        """Run SQL and return the result set."""
        assert_read_only(sql)
        import psycopg

        timeout_ms = max(1, int(timeout_seconds * 1000))
        conninfo = (
            f"host={self._settings.host} port={self._settings.port} "
            f"dbname={self._settings.database} user={self._settings.user} "
            f"password={self._settings.password}"
        )
        with psycopg.connect(conninfo, autocommit=True) as conn, conn.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {timeout_ms}")
            cursor.execute(sql)
            columns = tuple(col.name for col in cursor.description)
            rows = cursor.fetchmany(self._row_limit + 1)
            if len(rows) > self._row_limit:
                raise ValueError(f"result exceeds row limit of {self._row_limit}")
            return ResultSet(columns=columns, rows=tuple(tuple(r) for r in rows))
