"""Read only safety guard.

Only SELECT statements (and WITH ... SELECT) may run
against a database. Anything else raises ValueError
before it reaches the database.
"""

from __future__ import annotations

import re

_BLOCKED = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "merge",
    "call",
    "grant",
    "revoke",
    "copy",
)

_FIRST_WORD = re.compile(r"^\s*([a-zA-Z]+)")


def assert_read_only(sql: str) -> None:
    """Raise ValueError when the SQL is not a read query."""
    if not sql or not sql.strip():
        raise ValueError("empty SQL")
    match = _FIRST_WORD.match(sql)
    if not match:
        raise ValueError("cannot read SQL start")
    first = match.group(1).lower()
    if first == "select":
        return
    if first == "with":
        if re.search(r"\bselect\b", sql, re.IGNORECASE):
            lowered = sql.lower()
            for word in _BLOCKED:
                if re.search(rf"\b{word}\b", lowered):
                    raise ValueError(f"blocked write statement in WITH query: {word}")
            return
        raise ValueError("WITH query without SELECT is not allowed")
    raise ValueError(f"only SELECT queries are allowed, got: {first}")


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_ROW_LIMIT = 100_000


def validate_timeout(timeout_seconds: float) -> None:
    """Raise ValueError when the timeout cannot work."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")


def validate_row_limit(row_limit: int) -> None:
    """Raise ValueError when the row limit cannot work."""
    if row_limit <= 0:
        raise ValueError("row_limit must be positive")
