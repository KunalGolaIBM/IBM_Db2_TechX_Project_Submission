"""Application-side guard for LLM-generated SQL.

This is the first layer of defence; the second (and authoritative) one is the
Db2 privilege model - the agent user simply has no write privileges.
"""
from __future__ import annotations

import re

FORBIDDEN = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE", "GRANT",
    "REVOKE", "CALL", "TRUNCATE", "EXECUTE", "EXEC", "LOCK", "EXPORT", "IMPORT",
    "LOAD", "ADMIN_CMD", "RENAME", "COMMENT", "DECLARE", "REFRESH", "SET",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN) + r")\b", re.IGNORECASE)
_STRING_RE = re.compile(r"'(?:[^']|'')*'")
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LIMIT_RE = re.compile(r"\bFETCH\s+FIRST\b|\bLIMIT\s+\d+", re.IGNORECASE)


class UnsafeSqlError(ValueError):
    pass


def _strip(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(" ", sql)
    sql = _LINE_COMMENT_RE.sub(" ", sql)
    return sql.strip()


def validate_select(sql: str, row_limit: int = 200) -> str:
    """Return a safe, row-limited version of ``sql`` or raise UnsafeSqlError."""
    if not sql or not sql.strip():
        raise UnsafeSqlError("empty query")
    cleaned = _strip(sql).rstrip(";").strip()
    without_strings = _STRING_RE.sub("''", cleaned)

    if ";" in without_strings:
        raise UnsafeSqlError("only a single statement is allowed")
    first = without_strings.split(None, 1)[0].upper() if without_strings.split() else ""
    if first not in {"SELECT", "WITH", "VALUES"}:
        raise UnsafeSqlError("only SELECT / WITH queries are allowed")
    hit = _FORBIDDEN_RE.search(without_strings)
    if hit:
        raise UnsafeSqlError(f"keyword '{hit.group(1).upper()}' is not allowed in read-only queries")
    if not _LIMIT_RE.search(without_strings):
        cleaned = f"{cleaned}\nFETCH FIRST {int(row_limit)} ROWS ONLY"
    return cleaned
