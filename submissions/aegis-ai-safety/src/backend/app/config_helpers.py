"""Shared small helpers used by the pipeline."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def truncate_bytes(text: str, limit: int) -> str:
    """Fit text inside a Db2 VARCHAR byte limit without breaking UTF-8."""
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    return encoded[:limit].decode("utf-8", errors="ignore").rstrip()


def json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())
