"""Static safety checks applied to every SQL text before it reaches Db2.

Defense in depth: compiled SQL is already whitelisted, but the guard is applied
uniformly (and is the gate for any future model-proposed SQL).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_TABLES = frozenset(
    {"METRICGUARD.ORDERS", "METRICGUARD.ORDER_ITEMS", "METRICGUARD.PRODUCTS", "METRICGUARD.REFUNDS"}
)
FORBIDDEN_KEYWORDS = frozenset(
    {
        "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE", "GRANT", "REVOKE",
        "TRUNCATE", "CALL", "EXECUTE", "EXEC", "LOAD", "IMPORT", "EXPORT", "ADMIN_CMD",
        "SET", "DECLARE", "COMMIT", "ROLLBACK", "LOCK", "RENAME", "COMMENT", "REORG", "RUNSTATS",
    }
)
FORBIDDEN_SCHEMAS = ("SYSIBM", "SYSCAT", "SYSPROC", "SYSIBMADM", "SYSFUN", "SYSTOOLS", "SYSSTAT")

_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$#@]*")
_FROM_JOIN = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)
_CTE_NAME = re.compile(r"(?:\bWITH|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", re.IGNORECASE)


@dataclass(frozen=True)
class GuardFinding:
    code: str
    message: str


def check_sql(sql: str) -> list[GuardFinding]:
    findings: list[GuardFinding] = []
    body = sql.strip()
    if body.endswith(";"):
        body = body[:-1]
    # Comments are rejected (the compiler only emits '--' explanatory comments, stripped below).
    without_literals = _STRING_LITERAL.sub("''", body)
    if "/*" in without_literals:
        findings.append(GuardFinding("SQL_BLOCK_COMMENT", "Block comments are not allowed."))
    without_comments = re.sub(r"--[^\n]*", "", without_literals)

    if ";" in without_comments:
        findings.append(GuardFinding("SQL_MULTI_STATEMENT", "Only a single statement is allowed."))
    first = _WORD.search(without_comments)
    if not first or first.group(0).upper() not in {"SELECT", "WITH"}:
        findings.append(GuardFinding("SQL_NOT_SELECT", "Only SELECT / WITH ... SELECT queries are allowed."))

    words = {w.upper() for w in _WORD.findall(without_comments)}
    bad = sorted(words & FORBIDDEN_KEYWORDS)
    if bad:
        findings.append(GuardFinding("SQL_FORBIDDEN_KEYWORD", f"Forbidden keywords: {', '.join(bad)}."))

    upper = without_comments.upper()
    for schema in FORBIDDEN_SCHEMAS:
        if re.search(rf"\b{schema}\s*\.", upper):
            findings.append(GuardFinding("SQL_SYSTEM_CATALOG", f"Access to {schema} is not allowed."))

    ctes = {m.group(1).upper() for m in _CTE_NAME.finditer(without_comments)}
    for m in _FROM_JOIN.finditer(without_comments):
        name = m.group(1).upper()
        if name in ctes:
            continue
        if name not in ALLOWED_TABLES:
            findings.append(GuardFinding("SQL_TABLE_NOT_ALLOWED", f"Table '{name}' is not on the allow-list."))
    return findings
