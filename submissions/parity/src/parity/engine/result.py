"""Result types for the Parity Engine.

These types are plain data. They hold no logic except for small
helpers. The compare module is the only place that decides if
two result sets match.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ComparisonStatus(str, Enum):
    """Outcome of one comparison."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    ERROR = "ERROR"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class DiffKind(str, Enum):
    """Why two result sets differ."""

    COLUMN_NAME = "COLUMN_NAME"
    COLUMN_ORDER = "COLUMN_ORDER"
    COLUMN_COUNT = "COLUMN_COUNT"
    ROW_COUNT = "ROW_COUNT"
    VALUE = "VALUE"
    NULL_VS_VALUE = "NULL_VS_VALUE"
    TRAILING_SPACE = "TRAILING_SPACE"
    TYPE = "TYPE"
    TIE_ORDER = "TIE_ORDER"


@dataclass(frozen=True)
class ResultSet:
    """One database result set.

    columns holds column names in order. rows holds one tuple
    per row. Values keep their Python types so the normalizer
    can handle Decimal, datetime, and text correctly.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]

    def __post_init__(self) -> None:
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError("row width does not match column count")


@dataclass(frozen=True)
class RowDiff:
    """One difference between two result sets."""

    kind: DiffKind
    detail: str
    row_index: int | None = None
    column: str | None = None
    source_value: Any = None
    target_value: Any = None


@dataclass(frozen=True)
class ComparisonResult:
    """Full outcome of one comparison."""

    status: ComparisonStatus
    diffs: tuple[RowDiff, ...] = ()
    settings: tuple[tuple[str, str], ...] = ()
    note: str = ""

    @property
    def is_match(self) -> bool:
        """True only when the status is MATCH."""
        return self.status is ComparisonStatus.MATCH
