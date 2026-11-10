"""Read-only SQL guard.

Every query the agents run against Db2 passes through :func:`validate_readonly`.
It enforces: a single SELECT/WITH/VALUES statement, no data-changing keywords,
a table allow-list, and a hard row limit.
"""
from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|CALL|EXEC|EXECUTE|"
    r"RENAME|COMMIT|ROLLBACK|LOCK|LOAD|IMPORT|EXPORT|SET|DECLARE|EXPLAIN|ATTACH|CONNECT)\b",
    re.IGNORECASE,
)
TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w$#@]*(?:\.[A-Za-z_][\w$#@]*)?)", re.IGNORECASE)
FETCH_FIRST = re.compile(r"\bFETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY\b", re.IGNORECASE)


class UnsafeSQL(ValueError):
    """Raised when a query is rejected by the guard."""


def _strip_comments_and_literals(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)  # keywords inside string literals are harmless


def validate_readonly(sql: str, allowed_tables: set[str], max_rows: int = 500) -> str:
    """Return the query (with a row limit applied) or raise :class:`UnsafeSQL`."""
    if not sql or not sql.strip():
        raise UnsafeSQL("empty query")
    original = sql.strip().rstrip(";").strip()
    probe = _strip_comments_and_literals(original)

    if ";" in probe:
        raise UnsafeSQL("multiple statements are not allowed")
    head = probe.lstrip().split(None, 1)[0].upper() if probe.strip() else ""
    if head not in {"SELECT", "WITH", "VALUES"}:
        raise UnsafeSQL(f"only SELECT/WITH/VALUES statements are allowed (got {head or 'nothing'})")
    match = FORBIDDEN.search(probe)
    if match:
        raise UnsafeSQL(f"forbidden keyword: {match.group(1).upper()}")

    allowed = {t.upper() for t in allowed_tables}
    # "FOR SYSTEM_TIME FROM <ts> TO <ts>" is a period clause, not a table reference
    table_probe = re.sub(r"\bFOR\s+SYSTEM_TIME\s+FROM\b", "FOR SYSTEM_TIME START", probe, flags=re.IGNORECASE)
    for ref in TABLE_REF.findall(table_probe):
        name = ref.split(".")[-1].upper()
        schema = ref.split(".")[0].upper() if "." in ref else None
        if schema == "SYSCAT" or schema == "SYSIBM":
            continue  # read-only system catalog
        if name not in allowed:
            raise UnsafeSQL(f"table not in allow-list: {ref}")

    if head != "VALUES" and not FETCH_FIRST.search(probe):
        original += f" FETCH FIRST {int(max_rows)} ROWS ONLY"
    return original
