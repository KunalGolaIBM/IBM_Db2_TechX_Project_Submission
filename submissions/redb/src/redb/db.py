"""Thin wrapper over the ibm_db driver."""
from __future__ import annotations

import statistics
import time
from typing import Any

from .config import Settings, get_settings

TAG = "/*REDB*/ "  # prefix for internal statements so the monitor can ignore them


def conn_string(s: Settings) -> str:
    cs = (f"DATABASE={s.db2_database};HOSTNAME={s.db2_host};PORT={s.db2_port};"
          f"PROTOCOL=TCPIP;UID={s.db2_user};PWD={s.db2_password};")
    return cs + ("SECURITY=SSL;" if s.ssl else "")


class Db:
    def __init__(self, settings: Settings | None = None):
        import ibm_db  # imported lazily so tests run without the driver

        self._ibm_db = ibm_db
        self.settings = settings or get_settings()
        self.conn = ibm_db.connect(conn_string(self.settings), "", "")
        ibm_db.autocommit(self.conn, ibm_db.SQL_AUTOCOMMIT_ON)

    # -- helpers ---------------------------------------------------------
    def _stmt(self, sql: str, params: tuple | list | None):
        if params:
            stmt = self._ibm_db.prepare(self.conn, sql)
            self._ibm_db.execute(stmt, tuple(params))
            return stmt
        return self._ibm_db.exec_immediate(self.conn, sql)

    def query(self, sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
        stmt = self._stmt(TAG + sql, params)
        rows, row = [], self._ibm_db.fetch_assoc(stmt)
        while row:
            rows.append(row)
            row = self._ibm_db.fetch_assoc(stmt)
        self._ibm_db.free_result(stmt)
        return rows

    def execute(self, sql: str, params: tuple | list | None = None) -> int:
        stmt = self._stmt(TAG + sql, params)
        n = self._ibm_db.num_rows(stmt)
        self._ibm_db.free_result(stmt)
        return n

    def exec_immediate(self, sql: str) -> None:
        """Run a statement verbatim (no tag). Used for workload and advisor compile."""
        stmt = self._ibm_db.exec_immediate(self.conn, sql)
        if stmt:
            self._ibm_db.free_result(stmt)

    def scalar(self, sql: str, params: tuple | list | None = None) -> Any:
        rows = self.query(sql, params)
        return next(iter(rows[0].values())) if rows else None

    def run_untagged(self, sql: str) -> int:
        """Execute SQL exactly as written and fetch every row; returns row count."""
        stmt = self._ibm_db.exec_immediate(self.conn, sql)
        n = 0
        while self._ibm_db.fetch_tuple(stmt):
            n += 1
        self._ibm_db.free_result(stmt)
        return n

    def timed(self, sql: str, runs: int = 5) -> float:
        """Median wall-clock ms over `runs` executions, all rows fetched (one warm-up)."""
        self.run_untagged(TAG + sql)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            self.run_untagged(TAG + sql)
            times.append((time.perf_counter() - t0) * 1000)
        return statistics.median(times)

    def close(self) -> None:
        try:
            self._ibm_db.close(self.conn)
        except Exception:
            pass
