"""IBM Db2 executor.

Runs read queries with the official ibm_db driver.
Caps rows and returns a ResultSet. The driver is
imported lazily so tests need no Db2 server.
"""

from __future__ import annotations

from parity.config import DatabaseSettings
from parity.engine.db2_types import convert_row
from parity.engine.result import ResultSet
from parity.engine.safety import assert_read_only

_DEFAULT_ROW_LIMIT = 100_000


def _connection_string(settings: DatabaseSettings) -> str:
    return (
        f"DATABASE={settings.database};HOSTNAME={settings.host};"
        f"PORT={settings.port};PROTOCOL=TCPIP;UID={settings.user};"
        f"PWD={settings.password};"
    )


class Db2Executor:
    """Execute read queries on IBM Db2."""

    def __init__(self, settings: DatabaseSettings, row_limit: int = _DEFAULT_ROW_LIMIT) -> None:
        settings.require_complete("Db2")
        if row_limit <= 0:
            raise ValueError("row_limit must be positive")
        self._settings = settings
        self._row_limit = row_limit

    def execute(self, sql: str, timeout_seconds: float = 30.0) -> ResultSet:
        """Run SQL and return the result set.

        Db2 has no single statement timeout switch that
        works on every version, so the timeout parameter
        is kept for interface match and enforced by the
        caller with a hard deadline in later branches.
        """
        del timeout_seconds
        assert_read_only(sql)
        import ibm_db

        conn = ibm_db.connect(_connection_string(self._settings), "", "")
        try:
            stmt = ibm_db.exec_immediate(conn, sql)
            field_count = ibm_db.num_fields(stmt)
            columns = tuple(ibm_db.field_name(stmt, i) for i in range(field_count))
            column_types = [ibm_db.field_type(stmt, i) for i in range(field_count)]
            rows: list[tuple] = []
            while True:
                row = ibm_db.fetch_tuple(stmt)
                if row is False or row is None:
                    break
                rows.append(convert_row(tuple(row), column_types))
                if len(rows) > self._row_limit:
                    raise ValueError(f"result exceeds row limit of {self._row_limit}")
            return ResultSet(columns=columns, rows=tuple(rows))
        finally:
            ibm_db.close(conn)
