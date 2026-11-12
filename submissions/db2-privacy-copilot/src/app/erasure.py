"""
Erasure/anonymisation planner and executor.

Key principles:
1. Dry-run planning first (never executes)
2. Human approval required
3. Guardrail validates every statement
4. Single transaction (all-or-nothing)
5. Audit trail for everything

Safety assumptions:
- All SQL comes from plan generator (not user input)
- Identifiers come from discovery module (catalog)
- Guardrail validates before execution
- Executor runs under restricted DB user
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from app import audit, discovery, guardrail
from app.config import settings
from app.db import conn, query
from app.sql import quote_identifier


@dataclass
class Step:
    """Single step in an erasure plan."""
    
    table: str
    action: str  # ERASE, ANONYMISE, RETAIN
    sql: Optional[str]
    reason: str
    est_rows: int
    rule_verified: bool = False


class ErasureError(Exception):
    """Base exception for erasure operations."""
    pass


class PlanChanged(ErasureError):
    """Raised when plan hash doesn't match approval."""
    pass


def get_retention_rules() -> dict[str, tuple[str, str, bool]]:
    """
    Load retention rules from the database.
    
    Returns:
        Dict mapping table name to (action, reason, verified)
    """
    result = query("SELECT TABNAME, ACTION, REASON, VERIFIED FROM RETENTION_RULES")
    
    if not result:
        return {}
    
    rules = {}
    for row in result:
        table = row[0].strip().upper()
        action = row[1].strip()
        reason = row[2].strip()
        verified = row[3].strip() == "Y"
        rules[table] = (action, reason, verified)
    
    return rules


def rule_for(table: str) -> tuple[str, str, bool]:
    """
    Get the retention rule for a specific table.
    
    Args:
        table: Table name
        
    Returns:
        Tuple of (action, reason, verified)
        
    Raises:
        ErasureError: If no rule exists
    """
    rules = get_retention_rules()
    
    if table.upper() not in rules:
        raise ErasureError(f"No retention rule defined for table {table}")
    
    return rules[table.upper()]


def count_rows(schema: str, table: str, fk_column: str, subject_id: int) -> int:
    """
    Estimate number of rows that would be affected.
    
    Args:
        schema: Schema name
        table: Table name
        fk_column: Foreign key column name
        subject_id: Subject ID
        
    Returns:
        Row count
    """
    quoted_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    quoted_fk = quote_identifier(fk_column)
    # Identifiers are validated; subject_id is parameterized.
    sql = f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_fk} = ?"  # nosec B608
    result = query(sql, (subject_id,))
    return result[0][0] if result else 0


def get_pii_columns(table: str) -> list[str]:
    """
    Get list of PII columns for a table from PII_MAP.
    
    Args:
        table: Table name
        
    Returns:
        List of column names classified as PII
    """
    result = query("""
        SELECT COLNAME FROM PII_MAP
        WHERE TABNAME = ? AND LABEL != 'NOT_PII'
    """, (table.upper(),))
    
    if not result:
        return []
    
    return [row[0].strip() for row in result]


def is_nullable(schema: str, table: str, column: str) -> bool:
    """
    Check if a column is nullable.
    
    Args:
        schema: Schema name
        table: Table name
        column: Column name
        
    Returns:
        True if nullable, False otherwise
    """
    result = query("""
        SELECT NULLS FROM SYSCAT.COLUMNS
        WHERE TABSCHEMA = ? AND TABNAME = ? AND COLNAME = ?
    """, (schema.upper(), table.upper(), column.upper()))
    
    if result and len(result) > 0:
        return result[0][0].strip() == "Y"
    
    return False


def plan(
    subject_id: int,
    schema: str = None,
    root: str = "PATIENT",
) -> list[Step]:
    """
    Generate a dry-run erasure plan.
    
    This DOES NOT execute anything - it only plans.
    
    Args:
        subject_id: Subject ID (e.g., patient ID)
        schema: Schema name (defaults to config)
        root: Root table name
        
    Returns:
        List of Step objects describing the plan
        
    Raises:
        ErasureError: If planning fails
    """
    if schema is None:
        schema = settings.db2_schema

    quoted_schema = quote_identifier(schema)

    # Get deletion order (children first)
    try:
        order = discovery.delete_order(schema, root)
    except Exception as e:
        raise ErasureError(f"Could not compute deletion order: {e}")
    
    # Build plan steps
    steps = []
    
    for table in order:
        # Get retention rule
        try:
            action, reason, verified = rule_for(table)
        except ErasureError:
            # No rule - default to ERASE with warning
            action = "ERASE"
            reason = "No retention rule defined - defaulting to erasure"
            verified = False
        
        # Get FK column to root
        fk_column = discovery.fk_column_to_root(schema, table, root)
        
        if not fk_column:
            # Skip tables with no relationship to root
            continue
        
        # Estimate affected rows
        est_rows = count_rows(schema, table, fk_column, subject_id)
        
        # Generate SQL based on action
        sql = None
        quoted_table = quote_identifier(table)
        quoted_fk = quote_identifier(fk_column)

        if action == "ERASE":
            # Identifiers are catalog-derived and validated; values are parameterized.
            sql = f"DELETE FROM {quoted_schema}.{quoted_table} WHERE {quoted_fk} = ?"  # nosec B608
        
        elif action == "ANONYMISE":
            # Get PII columns that are nullable
            pii_cols = get_pii_columns(table)
            if not pii_cols and table.upper() == root.upper():
                raise ErasureError(
                    f"No PII classification for {table}. Run classification first."
                )
            nullable_pii = [c for c in pii_cols if is_nullable(schema, table, c)]
            
            if nullable_pii:
                sets = ", ".join(f"{quote_identifier(c)} = NULL" for c in nullable_pii)
                # Identifiers are catalog-derived and validated; values are parameterized.
                sql = f"UPDATE {quoted_schema}.{quoted_table} SET {sets} WHERE {quoted_fk} = ?"  # nosec B608
            else:
                # No nullable PII columns - treat as RETAIN
                sql = None
                reason = f"{reason} (no nullable PII columns to anonymise)"
        
        elif action == "RETAIN":
            sql = None  # Don't generate SQL for retained tables
        
        # Create step
        step = Step(
            table=table,
            action=action,
            sql=sql,
            reason=reason,
            est_rows=est_rows,
            rule_verified=verified,
        )
        
        steps.append(step)
    
    return steps


def plan_hash(steps: list[Step]) -> str:
    """
    Compute a hash of the plan for approval binding.
    
    Args:
        steps: List of plan steps
        
    Returns:
        SHA256 hash of the plan
    """
    plan_dict = {
        "steps": [
            {
                "table": s.table,
                "action": s.action,
                "sql": s.sql,
                "reason": s.reason,
            }
            for s in steps
        ]
    }
    
    plan_json = json.dumps(plan_dict, sort_keys=True)
    return hashlib.sha256(plan_json.encode()).hexdigest()


def execute(
    steps: list[Step],
    subject_id: int,
    approver: str,
    approval_id: str,
    approved_hash: str,
) -> None:
    """
    Execute an approved erasure plan.
    
    This is the ONLY function that actually modifies data.
    
    Args:
        steps: Approved plan steps
        subject_id: Subject ID
        approver: Email/username of approver
        approval_id: Unique approval ID
        approved_hash: Hash of the approved plan
        
    Raises:
        PlanChanged: If plan hash doesn't match
        guardrail.Blocked: If guardrail blocks any statement
        ErasureError: If execution fails
    """
    # Verify plan hasn't changed
    current_hash = plan_hash(steps)
    if current_hash != approved_hash:
        raise PlanChanged("Plan has changed since approval")
    
    # Build allowed tables set
    allowed_tables = {s.table.upper() for s in steps if s.sql}
    
    # Validate all statements with guardrail
    print("Validating statements with guardrail...")
    for step in steps:
        if step.sql:
            guardrail.check(step.sql, allowed_tables, approved=True)
    
    print("All statements passed guardrail [OK]")
    
    # Execute in a single transaction
    c = conn()
    c.set_autocommit(False)
    
    try:
        cur = c.cursor()
        
        print(f"Executing {len([s for s in steps if s.sql])} statements...")
        
        for step in steps:
            if not step.sql:
                continue
            
            print(f"  {step.action} {step.table}...", end=" ")
            
            # Execute statement
            cur.execute(step.sql, (subject_id,))
            rows_affected = cur.rowcount
            
            print(f"{rows_affected} rows")
        
        # Record in audit log
        print("Recording audit trail...")
        
        detail = {
            "approval_id": approval_id,
            "plan_hash": approved_hash,
            "steps": [
                {
                    "table": s.table,
                    "action": s.action,
                    "est_rows": s.est_rows,
                }
                for s in steps
            ],
        }
        
        # Include the audit row in the same transaction as the data changes.
        audit.append(approver, "ERASURE", subject_id, detail, connection=c)
        
        # Update request status (if request exists)
        cur.execute("""
            UPDATE REQUESTS 
            SET STATUS = 'COMPLETED', COMPLETED_AT = CURRENT TIMESTAMP
            WHERE SUBJECT_ID = ? AND STATUS = 'APPROVED'
        """, (subject_id,))
        
        # Commit transaction
        c.commit()
        print("Transaction committed [OK]")
        
    except Exception as e:
        c.rollback()
        print(f"[ERROR] Transaction rolled back: {e}")
        raise ErasureError(f"Execution failed: {e}")
    
    finally:
        c.close()


def simulate(steps: list[Step]) -> dict[str, any]:
    """
    Simulate execution without actually running it.
    
    Returns statistics about what would happen.
    
    Args:
        steps: Plan steps to simulate
        
    Returns:
        Dict with statistics
    """
    total_rows = sum(s.est_rows for s in steps)
    
    by_action = {}
    for step in steps:
        if step.action not in by_action:
            by_action[step.action] = {"tables": 0, "rows": 0}
        by_action[step.action]["tables"] += 1
        by_action[step.action]["rows"] += step.est_rows
    
    unverified_rules = sum(1 for s in steps if not s.rule_verified)
    
    return {
        "total_steps": len(steps),
        "total_rows": total_rows,
        "by_action": by_action,
        "unverified_rules": unverified_rules,
        "has_unverified": unverified_rules > 0,
    }


if __name__ == "__main__":
    """Demonstrate erasure planning (dry run only)."""
    import sys
    
    print("=" * 60)
    print("Erasure Planner Demo (DRY RUN)")
    print("=" * 60)
    
    # Get a patient ID
    result = query("SELECT ID FROM PATIENT FETCH FIRST 1 ROW ONLY")
    if not result:
        print("Error: No patients in database. Run seed.py first.")
        sys.exit(1)
    
    patient_id = result[0][0]
    print(f"\nGenerating plan for patient ID: {patient_id}")
    
    # Generate plan
    print("\nPlanning...")
    steps = plan(patient_id, settings.db2_schema, "PATIENT")
    
    print(f"\n{'=' * 60}")
    print("ERASURE PLAN (DRY RUN)")
    print("=" * 60)
    
    for i, step in enumerate(steps, 1):
        verified_mark = "✓" if step.rule_verified else "⚠️"
        print(f"\n{i}. {step.table}")
        print(f"   Action: {step.action}")
        print(f"   Reason: {step.reason}")
        print(f"   Estimated rows: {step.est_rows}")
        print(f"   Rule verified: {verified_mark}")
        
        if step.sql:
            print(f"   SQL: {step.sql[:80]}...")
    
    # Simulate
    print(f"\n{'=' * 60}")
    print("SIMULATION")
    print("=" * 60)
    
    sim = simulate(steps)
    print(f"\nTotal steps: {sim['total_steps']}")
    print(f"Total rows affected: {sim['total_rows']}")
    
    print("\nBy action:")
    for action, stats in sim['by_action'].items():
        print(f"  {action}: {stats['tables']} tables, {stats['rows']} rows")
    
    if sim['has_unverified']:
        print(f"\n⚠️  WARNING: {sim['unverified_rules']} unverified retention rules")
        print("   These rules must be verified against the DPDP Act before production use")
    
    # Show plan hash
    print(f"\nPlan hash: {plan_hash(steps)}")
    print("(This hash would be bound to the approval)")
    
    print("\n" + "=" * 60)
    print("NOTE: This was a DRY RUN - no data was modified")
    print("=" * 60)
