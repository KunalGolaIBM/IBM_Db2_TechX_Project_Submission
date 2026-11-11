"""JSON-safe value coercion shared by the SQL execution and DBA tool paths."""

from __future__ import annotations

from datetime import date, datetime, time as dt_time
from decimal import Decimal
from typing import Any


def json_safe(value: Any) -> Any:
    """Coerce driver values (Decimal/datetime/bytes/...) into JSON types."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return str(value)
