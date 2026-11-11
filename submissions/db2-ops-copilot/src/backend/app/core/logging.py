"""Centralized logging configuration.

- Single formatter with a request-id column (populated per request by middleware).
- Idempotent: safe to call multiple times (tests, reloads).
- Optional file handler (path from ``LOG_FILE``) — disabled by default.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from pathlib import Path

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_FORMAT = "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO", log_file: str = "") -> None:
    """Configure the root logger exactly once."""
    root = logging.getLogger()
    if getattr(root, "_db2copilot_configured", False):
        root.setLevel(level.upper())
        return

    formatter = logging.Formatter(_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(_RequestIdFilter())

    root.handlers.clear()
    root.addHandler(stream_handler)
    root.setLevel(level.upper())

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_RequestIdFilter())
        root.addHandler(file_handler)

    # Quiet noisy third-party loggers; keep our app visible.
    logging.getLogger("uvicorn.error").handlers.clear()
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    root._db2copilot_configured = True  # type: ignore[attr-defined]


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def get_request_id() -> str:
    return request_id_var.get()
