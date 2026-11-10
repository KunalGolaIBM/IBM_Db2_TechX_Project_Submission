"""Find the items of a top level SELECT list.

The translator needs to know which part of the SQL is the
select list, and which items already carry a name. A regex
cannot do this safely. A comma inside a function call is not
a separator, and an expression in a WHERE clause is not a
select item.

This scanner tracks string literals, quoted identifiers,
comments, and parenthesis depth. It only looks at the first
top level SELECT, so a WITH clause is handled because the
CTE body sits inside parentheses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FUNCTION = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
_COLUMN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$")
_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_CAST = re.compile(
    r"^CAST\s*\(\s*.+?\s+AS\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)\s*(?:\([^)]*\))?\s*\)$",
    re.IGNORECASE | re.DOTALL,
)
_CAST_DOUBLE = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*\s*::\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)*)\s*(?:\([^)]*\))?$",
    re.IGNORECASE | re.DOTALL,
)

# Postgres names a cast result with its internal type name.
_CAST_LABELS = {
    "integer": "int4",
    "int": "int4",
    "int4": "int4",
    "bigint": "int8",
    "int8": "int8",
    "smallint": "int2",
    "text": "text",
    "varchar": "varchar",
    "character varying": "varchar",
    "boolean": "bool",
    "bool": "bool",
    "numeric": "numeric",
    "decimal": "numeric",
    "real": "float4",
    "double precision": "float8",
    "date": "date",
    "time": "time",
    "timestamp": "timestamp",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamptz",
}


@dataclass(frozen=True)
class SelectItem:
    """One item of the select list."""

    text: str
    start: int
    end: int


def _skip_string(sql: str, index: int) -> int:
    """Return the index after a string literal."""
    index += 1
    while index < len(sql):
        if sql[index] == "'":
            if index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            return index + 1
        index += 1
    return index


def _skip_quoted(sql: str, index: int) -> int:
    """Return the index after a quoted identifier."""
    index += 1
    while index < len(sql):
        if sql[index] == '"':
            return index + 1
        index += 1
    return index


def _skip_comment(sql: str, index: int) -> int:
    """Return the index after a comment."""
    if sql.startswith("--", index):
        end = sql.find("\n", index)
        return len(sql) if end == -1 else end
    end = sql.find("*/", index)
    return len(sql) if end == -1 else end + 2


def _select_span(sql: str) -> tuple[int, int] | None:
    """Return the span of the select list of the first top level SELECT."""
    depth = 0
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char == "'":
            index = _skip_string(sql, index)
            continue
        if char == '"':
            index = _skip_quoted(sql, index)
            continue
        if char == "-" and sql.startswith("--", index):
            index = _skip_comment(sql, index)
            continue
        if char == "/" and sql.startswith("/*", index):
            index = _skip_comment(sql, index)
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth -= 1
            index += 1
            continue
        if depth == 0 and sql[index : index + 6].upper() == "SELECT":
            start = index + 6
            end = _find_clause_end(sql, start)
            return start, end
        index += 1
    return None


def _find_clause_end(sql: str, start: int) -> int:
    """Return the index where the select list ends."""
    depth = 0
    index = start
    length = len(sql)
    while index < length:
        char = sql[index]
        if char == "'":
            index = _skip_string(sql, index)
            continue
        if char == '"':
            index = _skip_quoted(sql, index)
            continue
        if char == "-" and sql.startswith("--", index):
            index = _skip_comment(sql, index)
            continue
        if char == "/" and sql.startswith("/*", index):
            index = _skip_comment(sql, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and sql[index : index + 4].upper() == "FROM":
            return index
        index += 1
    return length


def select_items(sql: str) -> tuple[SelectItem, ...]:
    """Return the items of the top level select list."""
    span = _select_span(sql)
    if span is None:
        return ()
    start, end = span
    items: list[SelectItem] = []
    depth = 0
    item_start = start
    index = start
    while index < end:
        char = sql[index]
        if char == "'":
            index = _skip_string(sql, index)
            continue
        if char == '"':
            index = _skip_quoted(sql, index)
            continue
        if char == "-" and sql.startswith("--", index):
            index = _skip_comment(sql, index)
            continue
        if char == "/" and sql.startswith("/*", index):
            index = _skip_comment(sql, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(SelectItem(sql[item_start:index], item_start, index))
            item_start = index + 1
        index += 1
    items.append(SelectItem(sql[item_start:end], item_start, end))
    return tuple(items)


def _has_top_level_as(text: str) -> bool:
    """True when the item has an AS keyword outside any brackets.

    The AS inside a cast does not name the item. It names
    the type of the cast.
    """
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            index = _skip_string(text, index)
            continue
        if char == '"':
            index = _skip_quoted(text, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and text[index : index + 2].upper() == "AS":
            before_ok = index == 0 or not text[index - 1].isalnum()
            after_ok = index + 2 >= len(text) or not text[index + 2].isalnum()
            if before_ok and after_ok:
                return True
        index += 1
    return False


def _has_alias(text: str) -> bool:
    """True when the item already carries a name."""
    stripped = text.strip()
    if not stripped:
        return False
    if _has_top_level_as(stripped):
        return True
    parts = stripped.split()
    return len(parts) == 2 and bool(_IDENTIFIER.match(parts[1])) and not _IDENTIFIER.match(parts[0])


def postgres_label(text: str) -> str | None:
    """Return the column name Postgres gives this item.

    Returns None when the item needs no alias. That is the
    case for a plain column reference and for an item that
    already has a name.
    """
    stripped = text.strip()
    if not stripped:
        return None
    if stripped == "*" or stripped.endswith(".*"):
        return None
    if _COLUMN.match(stripped):
        return None
    if _has_alias(stripped):
        return None
    cast = _CAST.match(stripped)
    if cast:
        return _CAST_LABELS.get(cast.group(1).strip().lower(), "?column?")
    double_cast = _CAST_DOUBLE.match(stripped)
    if double_cast:
        return _CAST_LABELS.get(double_cast.group(1).strip().lower(), "?column?")
    function = _FUNCTION.match(stripped)
    if function:
        return function.group(1).lower()
    return "?column?"
