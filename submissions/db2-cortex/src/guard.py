"""Guardrail agent: AST validation (sqlglot) + role-aware PII policy + Db2 PREPARE. Read-only, allow-listed, row-capped."""
import re
import sqlglot
from sqlglot import exp
from config import ALLOWED_TABLES, MAX_ROWS, PII_COLUMNS
import db

FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Merge)
SYSTEM = re.compile(r"\b(SYSPROC|SYSIBM|SYSCAT|SYSSTAT|SYSTOOLS|SYSIBMADM|ADMIN_CMD)\b", re.I)
FATAL = re.compile(r"^(Write/DDL|Multiple statements|Only SELECT|System objects|Comments)")


def is_fatal(reason: str) -> bool:
    """Fatal = policy violation; retrying with the LLM is pointless."""
    return bool(FATAL.match(reason or ""))


def validate(sql: str, role: str = "analyst"):
    """Returns (ok, sql_or_reason)."""
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        return False, "Empty SQL."
    if "--" in sql or "/*" in sql:
        return False, "Comments are not allowed in generated SQL."
    if ";" in sql:
        return False, "Multiple statements are not allowed."
    if SYSTEM.search(sql):
        return False, "System objects and administrative routines are blocked."
    try:
        tree = sqlglot.parse_one(sql)
    except Exception as e:
        return False, f"SQL parse error: {e}"
    if not isinstance(tree, exp.Query):
        return False, "Only SELECT statements are allowed."
    if any(tree.find(t) for t in FORBIDDEN):
        return False, "Write/DDL operations are blocked."
    ctes = {c.alias.upper() for c in tree.find_all(exp.CTE)}
    tables = set()
    for t in tree.find_all(exp.Table):
        name = t.name.upper()
        if name in ctes:
            continue
        if name not in ALLOWED_TABLES or (t.db and t.db.upper() != "BANKING"):
            return False, f"Table {t.sql()} is not in the governed semantic layer."
        tables.add(name)
    if role != "admin":
        for c in tree.find_all(exp.Column):
            if c.name.upper() in PII_COLUMNS:
                return False, "Access denied: personal-data columns (FULL_NAME, EMAIL) require the admin role. Use CUSTOMER_ID instead."
        if "CUSTOMERS" in tables:
            for sel in tree.find_all(exp.Select):
                for e in sel.expressions:
                    if isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star)):
                        return False, "SELECT * on CUSTOMERS would expose personal data; list columns explicitly."
    if not re.search(r"FETCH\s+FIRST|\bLIMIT\b", sql, re.I):
        sql += f" FETCH FIRST {MAX_ROWS} ROWS ONLY"
    try:
        if not db.prepare_ok(sql):
            return False, "Db2 rejected the statement at PREPARE."
    except Exception as e:
        return False, f"Db2 PREPARE failed: {str(e)[:200]}"
    return True, sql
