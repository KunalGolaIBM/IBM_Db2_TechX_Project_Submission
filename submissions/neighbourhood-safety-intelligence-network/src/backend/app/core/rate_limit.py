"""Sliding-window throttle for failed logins (per client IP + email).

In-process by design: it protects a single backend instance without extra infrastructure.
A multi-instance deployment would back this with a shared store.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict


class LoginThrottle:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed, or 0 if the key is not blocked."""
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now)
            if len(q) < self.max_attempts:
                return 0
            return max(1, int(self.window - (now - q[0])))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
