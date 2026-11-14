"""Bounded, thread-safe DB-API pool. Leases own a connection exclusively.

No write is automatically replayed: a broken connection can have an ambiguous commit.
The next checkout replaces it. Health probes and rollback prevent session leakage.
"""
from __future__ import annotations

import time
from collections import deque
from contextlib import contextmanager
from threading import Condition
from typing import Any, Callable, Iterator


class PoolTimeout(TimeoutError):
    pass


class ConnectionPool:
    def __init__(self, factory: Callable[[], Any], min_size: int = 2, max_size: int = 10,
                 timeout: float = 5, healthcheck: Callable[[Any], None] | None = None):
        if not 0 <= min_size <= max_size or max_size < 1 or timeout <= 0:
            raise ValueError("Invalid pool limits")
        self.factory, self.min_size, self.max_size = factory, min_size, max_size
        self.timeout, self.healthcheck = timeout, healthcheck
        self._condition = Condition()
        self._idle: deque[Any] = deque()
        self._size = self._borrowed = self._reconnects = self._waiters = 0
        self._closed = False

    def warm(self) -> None:
        """Create the configured minimum on startup, without opening at import time."""
        leases = []
        try:
            for _ in range(self.min_size):
                leases.append(self.acquire())
        finally:
            for conn in leases:
                self.release(conn)

    def acquire(self) -> Any:
        deadline = time.monotonic() + self.timeout
        while True:
            with self._condition:
                if self._closed:
                    raise RuntimeError("Pool is closed")
                if self._idle:
                    conn = self._idle.popleft()
                    self._borrowed += 1
                    create = False
                elif self._size < self.max_size:
                    self._size += 1  # reserve before connecting outside the mutex
                    self._borrowed += 1
                    conn, create = None, True
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise PoolTimeout("Db2 connection pool exhausted")
                    self._waiters += 1
                    try:
                        self._condition.wait(remaining)
                    finally:
                        self._waiters -= 1
                    continue
            if create:
                try:
                    conn = self.factory()
                except BaseException:
                    with self._condition:
                        self._size -= 1
                        self._borrowed -= 1
                        self._condition.notify()
                    raise
            try:
                if self.healthcheck:
                    self.healthcheck(conn)
                return conn
            except Exception:
                self.release(conn, broken=True)
                with self._condition:
                    self._reconnects += 1
                if time.monotonic() >= deadline:
                    raise PoolTimeout("Db2 health check failed") from None

    def release(self, conn: Any, broken: bool = False) -> None:
        try:
            if not broken:
                conn.rollback()
        except Exception:
            broken = True
        with self._condition:
            self._borrowed -= 1
            if self._closed or broken:
                self._size -= 1
                try:
                    conn.close()
                except Exception:
                    pass
            else:
                self._idle.append(conn)
            self._condition.notify_all()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        conn = self.acquire()
        broken = False
        try:
            yield conn
        except Exception as exc:
            broken = any(code in str(exc) for code in ("SQLSTATE=08", "SQLSTATE 08", "08001", "08003", "08006", "58009"))
            raise
        finally:
            self.release(conn, broken)

    def stats(self) -> dict:
        with self._condition:
            return {"size": self._size, "idle": len(self._idle), "borrowed": self._borrowed,
                    "waiting": self._waiters, "min": self.min_size, "max": self.max_size,
                    "reconnects": self._reconnects, "closed": self._closed}

    def close(self) -> None:
        with self._condition:
            self._closed = True
            while self._idle:
                conn = self._idle.popleft()
                try:
                    conn.close()
                finally:
                    self._size -= 1
            self._condition.notify_all()
