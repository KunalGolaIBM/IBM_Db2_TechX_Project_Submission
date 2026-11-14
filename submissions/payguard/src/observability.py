"""JSON logging with context propagation and bounded process-local metrics."""
from __future__ import annotations

import json
import logging
import math
import statistics
from collections import Counter, deque
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class JSONFormatter(logging.Formatter):
    def format(self, record):
        out = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
               "logger": record.name, "request_id": request_id.get(), "message": record.getMessage()}
        for key in ("path", "status", "duration_ms", "dependency", "error_type"):
            if hasattr(record, key):
                out[key] = getattr(record, key)
        return json.dumps(out, ensure_ascii=True)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
        if name == "uvicorn.access":
            # request_completed already records status/latency inside request context.
            logger.disabled = True


class Metrics:
    def __init__(self, window: int = 10000):
        self._lock = Lock()
        self._latencies: deque[float] = deque(maxlen=window)
        self._requests = 0
        self._statuses: Counter[str] = Counter()
        self._verdicts: Counter[str] = Counter()

    def observe(self, status: int, duration: float):
        with self._lock:
            self._requests += 1
            self._statuses[str(status)] += 1
            self._latencies.append(duration * 1000)

    def verdict(self, value: str):
        with self._lock:
            self._verdicts[value] += 1

    def snapshot(self) -> dict:
        with self._lock:
            values = sorted(self._latencies)
            return {"request_count": self._requests, "status_counts": dict(self._statuses),
                    "verdict_counts": dict(self._verdicts), "latency_window": len(values),
                    "p50_ms": statistics.median(values) if values else 0,
                    "p95_ms": values[max(0, math.ceil(0.95 * len(values)) - 1)] if values else 0}


runtime = Metrics()
