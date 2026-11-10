"""
SQL Security Validator for Db2 Copilot.
Enforces read-only execution:
- Allows only a single SELECT statement.
- Only references allow-listed tables.
- Rejects any DDL, DML, multi-statement injection, comments, or unauthorized table access.
"""
import re
import sys
from typing import Tuple, List, Set

ALLOWED_TABLES = {
    "CUSTOMERS",
    "ORDERS",
    "PAYMENTS",
    "REFUNDS",
    "POLICIES",
    "SYSIBM.SYSDUMMY1",
}

FORBIDDEN_KEYWORDS = {
    "DELETE",
    "DROP",
    "INSERT",
    "UPDATE",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXEC",
    "EXECUTE",
    "MERGE",
    "INTO",
    "LOCK",
    "RENAME",
}


def clean_sql(raw_sql: str) -> str:
    """Extract and trim SQL from markdown code fences or raw text."""
    text = raw_sql.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
    if text.endswith("```"):
        text = re.sub(r"\s*```$", "", text)

    if "```sql" in text:
        match = re.search(r"```sql\s*(.*?)(?:```|$)", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
    elif "```" in text:
        match = re.search(r"```\s*(.*?)(?:```|$)", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Remove trailing semicolon
    text = text.strip()
    if text.endswith(";"):
        text = text[:-1].strip()

    return text


def extract_table_names(sql: str) -> List[str]:
    """Extract table references from FROM and JOIN clauses."""
    # Normalize whitespace
    s = " " + re.sub(r"\s+", " ", sql).strip() + " "
    tables = []

    # 1. Match FROM clause up to next clause keyword
    from_match = re.search(
        r"\bFROM\s+(.*?)(?=\bWHERE\b|\bJOIN\b|\bLEFT\b|\bRIGHT\b|\bINNER\b|\bFULL\b|\bCROSS\b|\bGROUP\b|\bORDER\b|\bHAVING\b|\bFETCH\b|\bUNION\b|$)",
        s,
        re.IGNORECASE,
    )
    if from_match:
        raw_from = from_match.group(1).strip()
        for part in raw_from.split(","):
            token = part.strip().split()[0] if part.strip() else ""
            if token and not token.startswith("("):
                tables.append(token.upper())

    # 2. Match JOIN clauses
    join_matches = re.finditer(
        r"\b(?:JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|CROSS\s+JOIN|FULL\s+JOIN)\s+([A-Za-z0-9_\.]+)",
        s,
        re.IGNORECASE,
    )
    for jm in join_matches:
        token = jm.group(1).strip().split()[0]
        if token and not token.startswith("("):
            tables.append(token.upper())

    return tables


def validate_sql(raw_sql: str) -> Tuple[bool, str, str]:
    """
    Validate that the SQL query is strictly a single SELECT statement on allow-listed tables.
    Returns: (is_valid: bool, error_message: str, cleaned_sql: str)
    """
    sql = clean_sql(raw_sql)

    if not sql:
        return False, "SQL query cannot be empty.", ""

    # Check for disallowed comments that might hide payloads
    if "--" in sql or "/*" in sql or "*/" in sql:
        return False, "SQL comments ('--', '/*') are forbidden for security reasons.", sql

    # Check for multi-statement execution (semicolons outside of quoted strings)
    sql_no_strings = re.sub(r"'(?:''|[^'])*'", "''", sql).strip()
    if sql_no_strings.endswith(";"):
        sql_no_strings = sql_no_strings[:-1].strip()
    if ";" in sql_no_strings:
        return False, "Multiple SQL statements are strictly forbidden.", sql

    # Must start with SELECT (or WITH CTE followed by SELECT)
    upper_sql = sql.upper().strip()
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        return False, "Only read-only SELECT queries are allowed.", sql

    # Check for forbidden keywords anywhere in token stream
    tokens = re.findall(r"\b[A-Z_]+\b", upper_sql)
    for token in tokens:
        if token in FORBIDDEN_KEYWORDS:
            return False, f"Forbidden SQL keyword detected: '{token}'. Mutation and administration commands are blocked.", sql

    # Check table allow-list
    tables = extract_table_names(sql)
    if not tables:
        pass
    else:
        for tbl in tables:
            parts = tbl.split(".")
            if len(parts) == 1:
                name = parts[0]
                if name not in ALLOWED_TABLES:
                    return (
                        False,
                        f"Unauthorized table access attempt: '{tbl}'. Allowed tables are: {', '.join(sorted(ALLOWED_TABLES))}.",
                        sql,
                    )
            elif len(parts) == 2:
                schema, name = parts
                if schema in ("SYSCAT", "SYSIBM", "SYSSTAT") and tbl != "SYSIBM.SYSDUMMY1":
                    return False, f"Access to system catalog table '{tbl}' is forbidden.", sql
                if name not in ALLOWED_TABLES:
                    return (
                        False,
                        f"Unauthorized table access attempt: '{tbl}'. Allowed tables are: {', '.join(sorted(ALLOWED_TABLES))}.",
                        sql,
                    )

    return True, "", sql


if __name__ == "__main__":
    test_cases = [
        ("SELECT * FROM CUSTOMERS WHERE customer_id = 1", True),
        ("SELECT o.order_id, c.name FROM ORDERS o JOIN CUSTOMERS c ON o.customer_id = c.customer_id", True),
        ("DELETE FROM ORDERS WHERE order_id = 101", False),
        ("DROP TABLE CUSTOMERS", False),
        ("SELECT * FROM ORDERS; DROP TABLE CUSTOMERS;", False),
        ("UPDATE PAYMENTS SET amount = 0", False),
        ("SELECT * FROM SYSCAT.TABLES", False),
        ("SELECT * FROM ORDERS -- secret delete", False),
    ]

    print("=" * 60)
    print("Testing SQL Validator")
    print("=" * 60)
    all_passed = True
    for query, expected_valid in test_cases:
        is_val, err, cleaned = validate_sql(query)
        passed = (is_val == expected_valid)
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} Expected valid={expected_valid}, Got valid={is_val}")
        print(f"   Query: {query}")
        if err:
            print(f"   Rejection reason: {err}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("ALL VALIDATOR TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)
