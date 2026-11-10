"""Fail-closed SQLGlot validator for AI generated queries."""
import re
import sqlglot
import db2_sqlglot  # noqa: F401 — registers IBM's Db2 dialect through SQLGlot entry points
from sqlglot import exp

ALLOWED_TABLES = {"CUSTOMERS", "PRODUCTS", "ORDERS", "ORDER_ITEMS", "PAYMENTS"}
FORBIDDEN_WORDS = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|CALL|EXECUTE|COMMIT|ROLLBACK|SET|VALUES|NEXT\s+VALUE|INTO)\b", re.I)


class UnsafeQuery(ValueError):
    pass


def validate_sql(sql: str) -> str:
    if not sql or not sql.strip():
        raise UnsafeQuery("The generated SQL was empty.")
    try:
        parsed = sqlglot.parse(sql, read="db2")
    except Exception as exc:
        raise UnsafeQuery("The generated SQL is not valid Db2 SQL.") from exc
    if len(parsed) != 1 or parsed[0] is None:
        raise UnsafeQuery("Only one SQL statement is allowed.")
    tree = parsed[0]
    if not isinstance(tree, exp.Query) or not isinstance(tree, (exp.Select, exp.Subquery, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeQuery("Only SELECT queries are allowed.")
    if FORBIDDEN_WORDS.search(sql):
        raise UnsafeQuery("The SQL contains a forbidden operation or clause.")
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise UnsafeQuery("SQL comments are not accepted.")
    for table in tree.find_all(exp.Table):
        name = table.name.upper()
        if name not in ALLOWED_TABLES:
            raise UnsafeQuery(f"Access to table '{name}' is not allowed.")
        if table.db or table.catalog:
            raise UnsafeQuery("Qualified and system catalog table access is not allowed.")
    # Db2 SELECT extensions that can mutate data are excluded.
    if re.search(r"\bFOR\s+(UPDATE|READ\s+ONLY)\b", sql, re.I):
        raise UnsafeQuery("Locking SELECT clauses are not allowed.")
    return tree.sql(dialect="db2")
