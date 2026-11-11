"""Thread-safe connection pool for IBM Db2.

ibm_db connections must not be shared between threads, so the API server checks
out one validated connection per request. A connection that fails validation
(e.g. Db2 restarted) is discarded and replaced transparently.
"""

import logging
import queue
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from ..config import Db2Config
from .repository import Db2Repository, connect_db2

log = logging.getLogger("shipsafe.db2.pool")


class Db2Unavailable(RuntimeError):
    """Raised when no healthy Db2 connection can be obtained."""


class ConnectionPool:
    def __init__(self, config: Db2Config, backend: str = "db2", size: int = 4,
                 sqlite_path: str = ":memory:", connect_retries: int = 2):
        self.config = config
        self.backend = backend
        self.size = max(1, size)
        self.connect_retries = connect_retries
        self._idle: "queue.LifoQueue" = queue.LifoQueue(maxsize=self.size)
        self._slots = threading.BoundedSemaphore(self.size)
        self._schema_ready = False
        self._schema_lock = threading.Lock()
        self._sqlite_conn = None
        self._sqlite_lock = threading.RLock()
        if backend == "sqlite":
            import sqlite3

            # A single shared in-memory database, serialised by a lock (tests / offline only).
            self._sqlite_conn = sqlite3.connect(sqlite_path, check_same_thread=False)

    def _new_repository(self, conn=None) -> Db2Repository:
        if conn is None:
            conn = connect_db2(self.config, retries=self.connect_retries)
        with self._schema_lock:
            init = not self._schema_ready
            repo = Db2Repository(self.config, backend="db2", conn=conn, init_schema=init)
            self._schema_ready = True
        return repo

    @contextmanager
    def repository(self) -> Iterator[Db2Repository]:
        """Check out a healthy repository; returns it to the pool afterwards."""
        if self.backend == "sqlite":
            with self._sqlite_lock:
                with self._schema_lock:
                    init = not self._schema_ready
                    self._schema_ready = True
                yield Db2Repository(self.config, backend="sqlite", conn=self._sqlite_conn, init_schema=init)
            return

        if not self._slots.acquire(timeout=30):
            raise Db2Unavailable("Timed out waiting for a free Db2 connection")
        repo: Optional[Db2Repository] = None
        try:
            try:
                repo = self._idle.get_nowait()
                repo.ping()
            except queue.Empty:
                repo = None
            except Exception:
                log.warning("discarding stale Db2 connection")
                repo.close()
                repo = None
            if repo is None:
                try:
                    repo = self._new_repository()
                except Exception as exc:
                    raise Db2Unavailable(str(exc)) from exc
            try:
                yield repo
            finally:
                # Never leak an open transaction; only return connections that still work.
                try:
                    repo.rollback()
                    repo.ping()
                    self._idle.put_nowait(repo)
                except Exception:
                    repo.close()
        finally:
            self._slots.release()

    def healthy(self) -> bool:
        try:
            with self.repository() as repo:
                repo.ping()
            return True
        except Exception:
            return False

    def close(self) -> None:
        while True:
            try:
                self._idle.get_nowait().close()
            except queue.Empty:
                break
        if self._sqlite_conn is not None:
            self._sqlite_conn.close()
