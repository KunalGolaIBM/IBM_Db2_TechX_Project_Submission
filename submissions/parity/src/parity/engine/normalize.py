"""Value normalization for comparison.

Normalization puts values from two databases into a form that
can be compared safely. It never hides a difference. Trailing
spaces, NULL, and empty text stay distinct.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any


def normalize_value(value: Any) -> Any:
    """Normalize one cell value for comparison.

    - bool stays bool. It is checked before int because bool
      is a subclass of int in Python.
    - Decimal stays Decimal. No float round trip.
    - datetime becomes UTC ISO text. Naive datetimes are
      treated as UTC so both sides use one rule.
    - date and time become ISO text.
    - bytes become hex text so two databases compare equal
      only when the bytes are equal.
    - str is returned as is. No trimming. No case change.
    - None stays None. It never becomes empty text.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        aware = value
        if aware.tzinfo is None:
            aware = aware.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if isinstance(value, str):
        return value
    return str(value)


def is_trailing_space_only(left: Any, right: Any) -> bool:
    """True when two text values differ only by trailing spaces."""
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    if left == right:
        return False
    return left.rstrip(" ") == right.rstrip(" ") and left != right
