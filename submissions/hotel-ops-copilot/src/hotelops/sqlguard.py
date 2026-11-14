"""Application-side guard for LLM-generated SQL.

Two application layers check every query the agent writes before Db2 sees it:

1. a lexical screen (single statement, starts with SELECT / WITH / VALUES, no write or admin keyword);
2. an AST check with SQLGlot and IBM's Db2 dialect (``db2-sqlglot-dialect``): the query is parsed into a
   syntax tree, which must be exactly one read-only query, contain no write / DDL / command node anywhere
   (including inside CTEs and subqueries), and read only tables in the application schema. Anything that
   cannot be parsed is refused (fail closed).

The authoritative layers are in Db2 itself: the EXPLAIN cost guard (costguard.py), and the agent's Db2 user,
which has no write privileges at all.
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import SqlglotError

# IBM's Db2 dialect for SQLGlot (pip install db2-sqlglot-dialect) registers itself as "db2" through a
# sqlglot.dialects entry point. It is required: the guard never falls back to a generic SQL grammar.
try:
    DB2_DIALECT = Dialect.get_or_raise("db2")
except ValueError as exc:  # pragma: no cover - only when the package is missing
    raise ImportError("IBM's Db2 SQLGlot dialect is missing: pip install db2-sqlglot-dialect") from exc

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

# Db2 syntax that the Db2 dialect (1.1) does not parse yet: CURRENT DATE / TIMESTAMP / TIME special registers
# inside expressions, labelled durations in most positions (CURRENT DATE + 1 DAY, ... - 2 HOURS, + ? DAYS),
# FOR BUSINESS_TIME, and a leading "VALUES expr". Rewritten into an equivalent shape only for the structural
# check; Db2 always runs the original text. tests/test_sqlguard.py pins each case.
_CURRENT_RE = re.compile(r"\bCURRENT\s+(DATE|TIMESTAMP|TIME)\b", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?|\?|\b[A-Z_][A-Z0-9_.]*\b|\([^()]*\))\s+"
    r"(DAY|MONTH|YEAR|HOUR|MINUTE|SECOND|MICROSECOND)S?\b(?!\s*\()", re.IGNORECASE)
_BUSINESS_TIME_RE = re.compile(r"\bFOR\s+BUSINESS_TIME\b", re.IGNORECASE)
_LEADING_VALUES_RE = re.compile(r"^\s*VALUES\s+", re.IGNORECASE)

APP_SCHEMA = "HOTELOPS"
ALLOWED_SYSTEM_TABLES = {("SYSIBM", "SYSDUMMY1")}
_WRITE_NODES = tuple(getattr(exp, n) for n in (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "Command", "TruncateTable",
    "Grant", "Revoke", "Set", "Use", "Copy", "LoadData", "Pragma", "Transaction", "Commit", "Rollback",
) if hasattr(exp, n))


class UnsafeSqlError(ValueError):
    pass


def _strip(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(" ", sql)
    sql = _LINE_COMMENT_RE.sub(" ", sql)
    return sql.strip()


def _for_parser(sql: str) -> str:
    """Db2-only syntax rewritten into an equivalent shape SQLGlot can parse (string contents blanked)."""
    s = _STRING_RE.sub("'s'", sql)
    s = _CURRENT_RE.sub(lambda m: "CURRENT_" + m.group(1).upper(), s)
    s = _DURATION_RE.sub(lambda m: f"INTERVAL '1' {m.group(2).upper()}", s)
    s = _LEADING_VALUES_RE.sub("SELECT ", s)  # Db2 "VALUES expr" has the shape of a SELECT list
    return _BUSINESS_TIME_RE.sub("FOR SYSTEM_TIME", s)


def check_ast(sql: str, schema: str = APP_SCHEMA) -> exp.Expression:
    """Parse ``sql`` and enforce the read-only shape on the syntax tree. Returns the tree or raises."""
    try:
        trees = [t for t in sqlglot.parse(_for_parser(sql), read=DB2_DIALECT) if t is not None]
    except SqlglotError as exc:
        raise UnsafeSqlError("the query could not be parsed for verification; write one plain Db2 SELECT "
                             f"({str(exc).splitlines()[0][:80]})") from exc
    if len(trees) != 1:
        raise UnsafeSqlError("only a single statement is allowed")
    tree = trees[0]
    if not isinstance(tree, (exp.Query, exp.Values)):
        raise UnsafeSqlError(f"only read queries are allowed, not {type(tree).__name__.upper()}")
    bad = next(iter(tree.find_all(*_WRITE_NODES)), None) if _WRITE_NODES else None
    if bad is not None:
        raise UnsafeSqlError(f"{type(bad).__name__.upper()} is not allowed anywhere in a read-only query")
    ctes = {c.alias_or_name.upper() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name, db = table.name.upper(), (table.db or "").upper()
        if not name:
            raise UnsafeSqlError("table functions and derived table sources are not allowed")
        if not db and name in ctes:
            continue
        if (db, name) in ALLOWED_SYSTEM_TABLES:
            continue
        if db not in ("", schema.upper()):
            raise UnsafeSqlError(f"reading {db}.{name} is not allowed; only {schema} tables and views")
    return tree


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
    check_ast(cleaned)
    if not _LIMIT_RE.search(without_strings):
        cleaned = f"{cleaned}\nFETCH FIRST {int(row_limit)} ROWS ONLY"
    return cleaned
