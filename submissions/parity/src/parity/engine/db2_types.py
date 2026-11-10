"""Type conversion for Db2 results.

The ibm_db driver returns a DECIMAL column as text, for
example '1000.000000'. Postgres returns the same value as
a Decimal. Comparing a Decimal with a string reports a
false mismatch, so the values are converted first.

The driver also reports a BOOLEAN column as an integer.
Db2 has no separate boolean type in its result metadata,
so that case is handled by the comparator instead.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def convert_value(value: object, column_type: str) -> object:
    """Convert one Db2 value to the Python type the engine expects."""
    if value is None or column_type != "decimal":
        return value
    if isinstance(value, (Decimal, int, float)):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return value


def convert_row(row: tuple, column_types: list[str]) -> tuple:
    """Convert one row of Db2 values using the column types."""
    return tuple(
        convert_value(value, column_type)
        for value, column_type in zip(row, column_types)
    )
