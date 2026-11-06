"""SQL files are the single source of truth for every statement the app runs.

Sections are marked with ``-- name: <key>``. Named parameters (``:state``)
are rewritten into positional markers in the order they appear, so a
statement and its parameter list can never silently drift apart.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from .config import SQL_DIR

_SECTION = re.compile(r"^--\s*name:\s*([A-Za-z0-9_]+)\s*$", re.MULTILINE)
_TOKEN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


class SqlAssetError(RuntimeError):
    pass


def strip_comments(sql: str) -> str:
    """Remove ``--`` comments while respecting single-quoted literals."""
    out: list[str] = []
    in_quote = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            in_quote = not in_quote
            out.append(ch)
        elif not in_quote and ch == "-" and i + 1 < len(sql) and sql[i + 1] == "-":
            while i < len(sql) and sql[i] != "\n":
                i += 1
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _read(path: Path) -> str:
    if not path.is_file():
        raise SqlAssetError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def section(path: Path, name: str) -> str:
    text = _read(path)
    matches = list(_SECTION.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1) != name:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = strip_comments(text[match.end():end]).strip()
        return body.rstrip(";").strip()
    available = ", ".join(m.group(1) for m in matches) or "<none>"
    raise SqlAssetError(f"Section '{name}' not found in {path.name}. Available: {available}")


def bind(sql: str, values: Mapping[str, Any]) -> tuple[str, tuple[Any, ...]]:
    """Replace ``:name`` markers with ``?`` and build the ordered parameters."""
    tokens = _TOKEN.findall(sql)
    missing = sorted({t for t in tokens if t not in values})
    if missing:
        raise SqlAssetError(f"Missing SQL parameters: {', '.join(missing)}")
    rewritten = _TOKEN.sub("?", sql)
    return rewritten, tuple(values[t] for t in tokens)


def query(name: str, values: Mapping[str, Any], filename: str = "03_queries.sql"):
    sql, params = bind(section(SQL_DIR / filename, name), values)
    return sql, params


def split_statements(sql: str, terminator: str = ";") -> list[str]:
    """Split a script on its terminator, ignoring quoted text."""
    statements: list[str] = []
    buffer: list[str] = []
    in_quote = False
    for ch in sql:
        if ch == "'":
            in_quote = not in_quote
            buffer.append(ch)
        elif not in_quote and ch == terminator:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(ch)
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def script_statements(path: Path) -> list[str]:
    """Load a DDL script honouring an optional ``-- TERMINATOR x`` marker."""
    raw = _read(path)
    terminator = ";"
    marker = re.search(r"^--\s*TERMINATOR\s+(\S+)\s*$", raw, re.MULTILINE)
    if marker:
        terminator = marker.group(1)
    cleaned = strip_comments(raw)
    cleaned = re.sub(r"^--.*$", "", cleaned, flags=re.MULTILINE)
    return [s for s in split_statements(cleaned, terminator) if s.strip()]
