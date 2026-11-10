"""
Deterministic SQL guardrail for erasure statements.

This is NOT an LLM - it's pure code-based validation.
Every destructive statement must pass through this guardrail.

Safety assumptions:
- Only DELETE and UPDATE statements allowed
- WHERE clause is mandatory
- Table names must be in approved list
- Parameterized values only (? placeholders)
- No DDL, no stacked statements, no SQL injection
"""
import re
from typing import Optional


class Blocked(PermissionError):
    """Raised when a statement is blocked by the guardrail."""
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Guardrail blocked: {reason}")


# Patterns for banned SQL tokens (case-insensitive)
BANNED_TOKENS = re.compile(
    r"\b(DROP|TRUNCATE|ALTER|GRANT|REVOKE|CREATE|CALL|EXEC|EXECUTE|"
    r"INSERT|MERGE|DECLARE|BEGIN|END)\b|;|--|/\*|\*/",
    re.IGNORECASE
)

# Allowed statement shapes (very strict)
DELETE_PATTERN = re.compile(
    r'^\s*DELETE\s+FROM\s+"[A-Z0-9_]+"\."[A-Z0-9_]+"\s+WHERE\s+.+\?\s*$',
    re.IGNORECASE | re.DOTALL
)

UPDATE_PATTERN = re.compile(
    r'^\s*UPDATE\s+"[A-Z0-9_]+"\."[A-Z0-9_]+"\s+SET\s+.+\s+WHERE\s+.+\?\s*$',
    re.IGNORECASE | re.DOTALL
)


def extract_table_name(sql: str) -> Optional[str]:
    """
    Extract the table name from a DELETE or UPDATE statement.
    
    Args:
        sql: SQL statement
        
    Returns:
        Table name in uppercase, or None if not found
    """
    # Look for "SCHEMA"."TABLE" pattern
    match = re.search(r'\"[A-Z0-9_]+\"\.\"([A-Z0-9_]+)\"', sql, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def check(
    sql: str,
    allowed_tables: set[str],
    approved: bool = False,
) -> None:
    """
    Validate an erasure/anonymisation SQL statement.
    
    This is the guardrail's main entry point.
    
    Args:
        sql: SQL statement to validate
        allowed_tables: Set of table names that are in the approved plan
        approved: Whether this execution has human approval
        
    Raises:
        Blocked: If the statement fails any validation check
        
    Examples:
        >>> check('DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?', 
        ...       {"PATIENT"}, approved=True)
        # Passes
        
        >>> check('DROP TABLE PATIENT', {"PATIENT"}, approved=True)
        Blocked: banned token
    """
    # Rule 1: Must have human approval
    if not approved:
        raise Blocked("human approval required")
    
    # Rule 2: No banned tokens
    if BANNED_TOKENS.search(sql):
        match = BANNED_TOKENS.search(sql)
        raise Blocked(f"banned token: {match.group()}")
    
    # Rule 3: Must match allowed statement shape
    sql_stripped = sql.strip()
    
    is_delete = DELETE_PATTERN.match(sql_stripped)
    is_update = UPDATE_PATTERN.match(sql_stripped)
    
    if not (is_delete or is_update):
        raise Blocked(
            "statement shape not allowed (must be DELETE or UPDATE with WHERE and parameterized values)"
        )
    
    # Rule 4: Must have WHERE clause
    if "WHERE" not in sql.upper():
        raise Blocked("missing WHERE clause")
    
    # Rule 5: Must use parameterized values
    if "?" not in sql:
        raise Blocked("must use parameterized values (?)")
    
    # Rule 6: Table must be in allowed list
    table = extract_table_name(sql)
    if not table:
        raise Blocked("could not extract table name")
    
    if table.upper() not in {t.upper() for t in allowed_tables}:
        raise Blocked(f"table {table} not in approved plan")
    
    # Rule 7: No unparameterized literals that look like injection attempts
    # Check for suspicious patterns like quotes or literals in WHERE clause
    where_clause = sql.upper().split("WHERE", 1)[1] if "WHERE" in sql.upper() else ""
    
    # Allow only ? in WHERE, and column names in quotes
    # This is a simplified check - real SQL parsing would be better
    if "'" in where_clause or re.search(r'\b\d+\s*=\s*\d+\b', where_clause):
        # Patterns like '1'='1' or 1=1 are injection attempts
        raise Blocked("suspicious pattern in WHERE clause")


def validate_plan(
    plan_steps: list[tuple[str, str, Optional[str]]],
    approved: bool = False,
) -> None:
    """
    Validate all statements in an erasure plan.
    
    Args:
        plan_steps: List of (table, action, sql) tuples
        approved: Whether the plan has human approval
        
    Raises:
        Blocked: If any statement fails validation
    """
    # Build allowed tables set
    allowed_tables = {table for table, action, sql in plan_steps if sql}
    
    # Validate each statement
    for table, action, sql in plan_steps:
        if sql:
            check(sql, allowed_tables, approved)


def check_plan_hash(
    current_plan: str,
    approved_hash: str,
) -> None:
    """
    Verify that the plan hasn't changed since approval.
    
    Args:
        current_plan: Current plan JSON string
        approved_hash: Hash that was approved
        
    Raises:
        Blocked: If hashes don't match
    """
    import hashlib
    
    current_hash = hashlib.sha256(current_plan.encode()).hexdigest()
    
    if current_hash != approved_hash:
        raise Blocked("plan has changed since approval (hash mismatch)")


# Additional validation functions

def check_retention_rule_exists(table: str, rules: dict[str, str]) -> None:
    """
    Verify that a retention rule exists for a table.
    
    Args:
        table: Table name
        rules: Dict mapping table names to actions
        
    Raises:
        Blocked: If no rule exists for the table
    """
    if table.upper() not in {t.upper() for t in rules.keys()}:
        raise Blocked(f"no retention rule defined for table {table}")


def check_transaction_size(row_count: int, max_rows: int = 100000) -> None:
    """
    Verify that the transaction isn't too large.
    
    This prevents accidental mass deletions.
    
    Args:
        row_count: Estimated number of rows to modify
        max_rows: Maximum allowed rows
        
    Raises:
        Blocked: If row count exceeds limit
    """
    if row_count > max_rows:
        raise Blocked(
            f"transaction too large: {row_count} rows exceeds limit of {max_rows}"
        )


if __name__ == "__main__":
    """Demonstrate guardrail blocking various attacks."""
    print("=" * 60)
    print("Guardrail Security Tests")
    print("=" * 60)
    
    # Valid statement (should pass)
    print("\n✓ Testing valid DELETE statement...")
    try:
        check(
            'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?',
            {"PATIENT"},
            approved=True
        )
        print("  PASSED - Valid statement allowed")
    except Blocked as e:
        print(f"  FAILED - {e.reason}")
    
    # Test banned tokens
    attacks = [
        ('DROP TABLE "DB2INST1"."PATIENT"', "DROP statement"),
        ('DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?; DROP TABLE X', "stacked statement"),
        ('DELETE FROM "DB2INST1"."PATIENT"', "missing WHERE"),
        ('DELETE FROM "DB2INST1"."PATIENT" WHERE 1=1', "missing parameter"),
        ('DELETE FROM "DB2INST1"."OTHER" WHERE "ID" = ?', "wrong table"),
        ('UPDATE "DB2INST1"."PATIENT" SET "NAME"=NULL WHERE "ID"=? --comment', "SQL comment"),
        ('TRUNCATE TABLE "DB2INST1"."PATIENT"', "TRUNCATE"),
        ('ALTER TABLE "DB2INST1"."PATIENT" DROP COLUMN "NAME"', "ALTER"),
    ]
    
    print("\n✗ Testing attack scenarios (should all be BLOCKED)...")
    for sql, description in attacks:
        try:
            check(sql, {"PATIENT"}, approved=True)
            print(f"  FAILED - {description} was NOT blocked!")
        except Blocked as e:
            print(f"  PASSED - {description} blocked: {e.reason}")
    
    # Test approval requirement
    print("\n✗ Testing without approval...")
    try:
        check(
            'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?',
            {"PATIENT"},
            approved=False
        )
        print("  FAILED - Statement executed without approval!")
    except Blocked as e:
        print(f"  PASSED - Blocked: {e.reason}")
    
    print("\n" + "=" * 60)
    print("Guardrail tests complete")
    print("=" * 60)
