"""Server-to-server authentication and bounded, per-IP request admission."""
from __future__ import annotations

import hmac
import math
import time
from collections import OrderedDict, deque
from threading import Lock

from fastapi import Header, HTTPException

from config import settings


def require_platform_key(x_api_key: str = Header("")) -> None:
    if not settings.platform_api_key:
        raise HTTPException(503, "Platform API key is not configured.")
    if not hmac.compare_digest(x_api_key.encode(), settings.platform_api_key.encode()):
        raise HTTPException(401, "Invalid platform API key.")


class PerIPRateLimiter:
    """Sliding 60-second window shared by expensive endpoints and their aliases.

    Use the socket peer (or a trusted reverse proxy configured in Uvicorn), never
    parse forwarded headers here. At capacity, reject new IPs instead of evicting
    active clients, which would let attackers reset their allowance.
    """
    def __init__(self, limit: int = 60, max_ips: int = 10000, clock=time.monotonic):
        self.limit, self.max_ips, self.clock = limit, max_ips, clock
        self._clients: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def admit(self, ip: str) -> int:
        now = self.clock()
        with self._lock:
            while self._clients:
                first = next(iter(self._clients))
                if self._clients[first][-1] > now - 60:
                    break
                self._clients.pop(first)
            if ip not in self._clients:
                if len(self._clients) >= self.max_ips:
                    return 60
                self._clients[ip] = deque()
            window = self._clients[ip]
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= self.limit:
                return max(1, math.ceil(window[0] + 60 - now))
            window.append(now)
            self._clients.move_to_end(ip)
            return 0
