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
    def __init__(self, config: Db2Config, size: int = 4, connect_retries: int = 2, checkout_timeout: float = 30.0):
        self.config = config
        self.size = max(1, size)
        self.connect_retries = connect_retries
        self.checkout_timeout = checkout_timeout
        self._idle: "queue.LifoQueue[Db2Repository]" = queue.LifoQueue(maxsize=self.size)
        self._slots = threading.BoundedSemaphore(self.size)
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def _new_repository(self) -> Db2Repository:
        conn = connect_db2(self.config, retries=self.connect_retries)
        with self._schema_lock:
            repo = Db2Repository(self.config, conn=conn, init_schema=not self._schema_ready)
            self._schema_ready = True
        return repo

    def _checkout_idle(self) -> Optional[Db2Repository]:
        try:
            repo = self._idle.get_nowait()
        except queue.Empty:
            return None
        try:
            repo.ping()
            return repo
        except Exception:
            log.warning("discarding stale Db2 connection")
            repo.close()
            return None

    @contextmanager
    def repository(self) -> Iterator[Db2Repository]:
        """Check out a healthy repository; returns it to the pool afterwards."""
        if not self._slots.acquire(timeout=self.checkout_timeout):
            raise Db2Unavailable("Timed out waiting for a free Db2 connection")
        try:
            repo = self._checkout_idle()
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
