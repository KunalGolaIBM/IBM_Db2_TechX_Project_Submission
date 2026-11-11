"""Read-only guard for any SQL written by the LLM."""
from __future__ import annotations

import re

FORBIDDEN = ("INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE",
             "GRANT", "REVOKE", "TRUNCATE", "CALL")
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN) + r")\b", re.IGNORECASE)
_STRINGS = re.compile(r"'(?:[^']|'')*'")
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


class UnsafeSQL(ValueError):
    pass


def check_readonly(sql: str) -> str:
    """Return the cleaned statement or raise UnsafeSQL."""
    if not sql or not sql.strip():
        raise UnsafeSQL("empty statement")
    cleaned = _COMMENTS.sub(" ", sql).strip().rstrip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    bare = _STRINGS.sub("''", cleaned)  # keywords inside string literals are harmless
    if ";" in bare:
        raise UnsafeSQL("multiple statements are not allowed")
    if not re.match(r"^\(*\s*(SELECT|WITH)\b", bare, re.IGNORECASE):
        raise UnsafeSQL("only SELECT/WITH statements are allowed")
    m = _FORBIDDEN_RE.search(bare)
    if m:
        raise UnsafeSQL(f"forbidden keyword: {m.group(1).upper()}")
    return cleaned


def is_safe(sql: str) -> bool:
    try:
        check_readonly(sql)
        return True
    except UnsafeSQL:
        return False
