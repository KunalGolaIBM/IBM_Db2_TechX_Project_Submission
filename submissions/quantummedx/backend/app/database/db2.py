"""IBM Db2 access layer: small connection pool, transactions, parameterized SQL."""
import queue
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Sequence

import ibm_db_dbi

from app.core.config import Db2Settings, load_db2_settings


class Db2Pool:
    def __init__(self, settings: Optional[Db2Settings] = None):
        self.settings = settings or load_db2_settings()
        self._pool: "queue.LifoQueue[Any]" = queue.LifoQueue(maxsize=self.settings.pool_size)
        self._lock = threading.Lock()
        self._created = 0

    def _new_connection(self):
        return ibm_db_dbi.connect(self.settings.conn_str, "", "")

    def acquire(self):
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            with self._lock:
                if self._created < self.settings.pool_size:
                    self._created += 1
                    return self._new_connection()
            return self._pool.get(timeout=10)

    def release(self, conn) -> None:
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Yield a cursor; commit on success, roll back on any error."""
        conn = self.acquire()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            self.release(conn)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self.transaction() as cur:
            cur.execute(sql, tuple(params))

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list:
        with self.transaction() as cur:
            cur.execute(sql, tuple(params))
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict]:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def health_check(self) -> dict:
        """Real round-trip to Db2; never reports 'connected' without querying it."""
        row = self.fetch_one(
            "SELECT SERVICE_LEVEL AS service_level FROM SYSIBMADM.ENV_INST_INFO FETCH FIRST 1 ROWS ONLY"
        )
        return {"connected": True, "server": row["service_level"] if row else None,
                "database": self.settings.database}
