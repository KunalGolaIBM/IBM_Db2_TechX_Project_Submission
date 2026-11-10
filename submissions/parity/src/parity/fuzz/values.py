"""Edge case value library.

Each category returns tricky values for one kind of
column. Values are plain Python values. They load into
both databases unchanged, so any result difference
comes from the databases, not from the data.

The values fit the column. A rounding value never goes
into an integer column, and a text value is cut to the
column width. A wrong value would only produce a data
error and hide the difference we look for.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

CATEGORIES: tuple[str, ...] = (
    "null",
    "empty_string",
    "single_space",
    "trailing_space",
    "mixed_case",
    "unicode",
    "long_string",
    "extreme_int",
    "rounding_number",
    "dst_date",
    "timezone_date",
)

_TEXT_TYPES = ("CHAR", "VARCHAR", "CLOB", "TEXT", "BLOB")


def _kind_of(db2_type: str) -> str:
    """Return the kind of a Db2 column type."""
    upper = db2_type.upper()
    if upper.startswith(("DECIMAL", "DEC", "NUMERIC")):
        return "decimal"
    if "DOUBLE" in upper or "REAL" in upper or "FLOAT" in upper:
        return "float"
    if "BIGINT" in upper:
        return "bigint"
    if "INT" in upper:
        return "int"
    if "TIMESTAMP" in upper:
        return "timestamp"
    if "TIME" in upper:
        return "time"
    if "DATE" in upper:
        return "date"
    if "BOOL" in upper:
        return "boolean"
    if upper.startswith(_TEXT_TYPES):
        return "text"
    return "other"


def _scale_of(db2_type: str) -> int:
    """Return the number of decimal places of a decimal column."""
    match = re.search(r"\(\s*\d+\s*,\s*(\d+)\s*\)", db2_type)
    return int(match.group(1)) if match else 6


def _precision_of(db2_type: str) -> int:
    """Return the total number of digits of a decimal column."""
    match = re.search(r"\(\s*(\d+)\s*,", db2_type)
    return int(match.group(1)) if match else 18


def _width_of(db2_type: str) -> int | None:
    """Return the length inside VARCHAR(n), or None."""
    match = re.search(r"\(\s*(\d+)\s*\)", db2_type.upper())
    return int(match.group(1)) if match else None


def _quantize(value: Decimal, scale: int) -> Decimal:
    """Round a decimal to the scale of the column."""
    step = Decimal(1).scaleb(-scale) if scale else Decimal(1)
    return value.quantize(step, rounding=ROUND_HALF_UP)


def _fit_text(value: str, db2_type: str) -> str:
    """Cut a text value to the column width.

    Db2 counts the bytes of a VARCHAR, Postgres counts the
    characters. A value is cut on a character boundary so
    that the byte count fits. The value must load into both
    databases, otherwise the test would only show a data
    error.
    """
    width = _width_of(db2_type)
    if width is None:
        return value
    if len(value.encode("utf-8")) <= width:
        return value
    kept: list[str] = []
    used = 0
    for char in value:
        size = len(char.encode("utf-8"))
        if used + size > width:
            break
        kept.append(char)
        used += size
    return "".join(kept)


def _max_decimal(db2_type: str) -> Decimal:
    """Return the largest value a decimal column can hold."""
    precision = _precision_of(db2_type)
    scale = _scale_of(db2_type)
    whole = precision - scale
    return _quantize(Decimal(10) ** whole - Decimal(1), scale)


def values_for_category(category: str) -> tuple[Any, ...]:
    """Return edge case values for one category."""
    builders: dict[str, tuple[Any, ...]] = {
        "null": (None,),
        "empty_string": ("",),
        "single_space": (" ",),
        "trailing_space": ("alice ", "bob  "),
        "mixed_case": ("Alice", "ALICE", "aLiCe"),
        "unicode": ("café", "naïve", "日本", "emoji 😀"),
        "long_string": ("x" * 40,),
        "extreme_int": (0, -1, 2147483647, -2147483648),
        "rounding_number": (Decimal("2.5"), Decimal("3.5"), Decimal("0.125"), Decimal("-2.5")),
        "dst_date": (
            date(2024, 3, 10),
            date(2024, 11, 3),
            date(2024, 2, 29),
        ),
        "timezone_date": (
            datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
            datetime(2024, 7, 15, 12, 0, tzinfo=UTC),
        ),
    }
    if category not in builders:
        raise ValueError(f"unknown category: {category}")
    return builders[category]


def categories_for_db2_type(db2_type: str) -> tuple[str, ...]:
    """Pick categories that fit one Db2 column type.

    A rounding value only fits a decimal column. A date
    value only fits a date column. A text value only fits
    a text column.
    """
    kind = _kind_of(db2_type)
    if kind == "int" or kind == "bigint":
        return ("null", "extreme_int")
    if kind == "decimal" or kind == "float":
        return ("null", "extreme_int", "rounding_number")
    if kind == "date":
        return ("null", "dst_date")
    if kind == "timestamp":
        return ("null", "timezone_date")
    if kind == "text":
        return (
            "null",
            "empty_string",
            "single_space",
            "trailing_space",
            "mixed_case",
            "unicode",
            "long_string",
        )
    return ("null",)


def values_for_column(db2_type: str, category: str) -> tuple[Any, ...]:
    """Return edge case values for one category, fitted to the column."""
    kind = _kind_of(db2_type)
    values = values_for_category(category)
    if kind == "int" or kind == "bigint":
        return tuple(int(value) for value in values if value is not None)
    if kind == "decimal":
        scale = _scale_of(db2_type)
        largest = _max_decimal(db2_type)
        fitted: list[Any] = []
        for value in values:
            if value is None:
                fitted.append(None)
                continue
            number = _quantize(Decimal(value), scale)
            if abs(number) > largest:
                number = largest if number > 0 else -largest
            fitted.append(number)
        return tuple(fitted)
    if kind == "float":
        return tuple(float(value) for value in values if value is not None)
    if kind == "date":
        return tuple(value for value in values if value is None or isinstance(value, date))
    if kind == "timestamp":
        return tuple(
            value
            for value in values
            if value is None or isinstance(value, (datetime, date))
        )
    if kind == "text":
        return tuple(
            _fit_text(value, db2_type) if isinstance(value, str) else value
            for value in values
        )
    return values


def max_value_for(db2_type: str) -> Decimal:
    """Return the largest decimal value the column can hold."""
    try:
        return _max_decimal(db2_type)
    except InvalidOperation:
        return Decimal(0)
