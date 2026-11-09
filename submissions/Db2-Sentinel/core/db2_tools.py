"""
Db2-Sentinel LangChain & CrewAI Tools Module
Provides strictly-typed, error-handled database inspection, execution, and audit tools.
Enforces uppercase SYSCAT catalog queries, Db2 dialect constraints, read-only guardrails,
and returns structured SQLSTATE error diagnostics for closed-loop self-correction.
"""

from __future__ import annotations
import json
import uuid
from typing import Optional, List, Dict, Any, Callable

# Defensive import for LangChain / CrewAI tool decorator
try:
    from langchain.tools import tool
except ImportError:
    # Graceful fallback decorator matching LangChain @tool signature
    def tool(func: Optional[Callable] = None, **kwargs: Any) -> Any:
        def decorator(f: Callable) -> Callable:
            setattr(f, "func", f)
            setattr(f, "name", f.__name__)
            setattr(f, "description", f.__doc__ or "")
            return f
        if func is not None:
            return decorator(func)
        return decorator

from core.config import db2_settings
from core.db2_engine import (
    Db2ConnectionManager,
    Db2DialectEnforcer,
    Db2ErrorParser,
    Db2ErrorInfo,
)


def _format_table_output(rows: List[Dict[str, Any]]) -> str:
    """Formats query result rows into a clean, markdown-friendly string."""
    if not rows:
        return "Query executed successfully. Result set is empty (0 rows returned)."
    
    # Check if single status row
    if len(rows) == 1 and "status" in rows[0]:
        return f"Result: {rows[0]}"

    headers = list(rows[0].keys())
    output_lines = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for r in rows[:50]:  # Cap at 50 rows for agent context safety
        output_lines.append(" | ".join(str(r.get(h, "NULL")) for h in headers))
    
    if len(rows) > 50:
        output_lines.append(f"... (truncated, {len(rows)} total rows returned. Use FETCH FIRST n ROWS ONLY to paginate)")
    return "\n".join(output_lines)


def run_introspect_db2_tables(schema_name: Optional[str] = None) -> str:
    """Core function to query SYSCAT.TABLES with uppercase identifiers."""
    target_schema = (schema_name or db2_settings.schema).strip().upper()
    
    # Db2 dialect constraint: Always query SYSCAT.TABLES using UPPERCASE identifiers
    sql = (
        f"SELECT TABSCHEMA, TABNAME, TYPE, CREATE_TIME "
        f"FROM SYSCAT.TABLES "
        f"WHERE TABSCHEMA = '{target_schema}' AND TYPE = 'T' "
        f"ORDER BY TABNAME "
        f"FETCH FIRST 100 ROWS ONLY"
    )

    try:
        rows = Db2ConnectionManager.execute_query(sql)
        if not rows:
            return f"No user tables found in schema '{target_schema}'. Verify that the schema name is in UPPERCASE."
        
        table_summary = [f"=== IBM Db2 TABLES IN SCHEMA [{target_schema}] ==="]
        for r in rows:
            table_summary.append(f"  • {r.get('TABSCHEMA')}.{r.get('TABNAME')} (Type: {r.get('TYPE')})")
        return "\n".join(table_summary)
    except Exception as exc:
        parsed_err = Db2ErrorParser.parse(str(exc))
        return parsed_err.to_agent_feedback(sql)


@tool
def introspect_db2_tables(schema_name: Optional[str] = None) -> str:
    """
    Queries IBM Db2 SYSCAT.TABLES using strictly UPPERCASE schema identifiers.
    Returns all relational tables available in the current database schema.
    """
    return run_introspect_db2_tables(schema_name)


def run_introspect_db2_schema(table_name: str, schema_name: Optional[str] = None) -> str:
    """Core function to query SYSCAT.COLUMNS with uppercase identifiers."""
    clean_table = table_name.strip().upper()
    target_schema = (schema_name or db2_settings.schema).strip().upper()

    # Strip schema prefix if included in table_name (e.g. DB2INST1.INVOICES -> INVOICES)
    if "." in clean_table:
        parts = clean_table.split(".", 1)
        target_schema = parts[0]
        clean_table = parts[1]

    # Db2 dialect constraint: Always query SYSCAT.COLUMNS using UPPERCASE identifiers
    sql = (
        f"SELECT COLNAME, TYPENAME, LENGTH, SCALE, NULLS, DEFAULT "
        f"FROM SYSCAT.COLUMNS "
        f"WHERE TABNAME = '{clean_table}' AND TABSCHEMA = '{target_schema}' "
        f"ORDER BY COLNO "
        f"FETCH FIRST 100 ROWS ONLY"
    )

    try:
        rows = Db2ConnectionManager.execute_query(sql)
        if not rows:
            return (
                f"=== IBM Db2 SCHEMA INTROSPECTION WARNING ===\n"
                f"Table '{clean_table}' not found in schema '{target_schema}'.\n"
                f"Directives:\n"
                f"  1. Ensure table name '{clean_table}' is capitalized.\n"
                f"  2. Use introspect_db2_tables to list valid table names.\n"
                f"  3. Note: In Db2, unquoted table identifiers are always stored in UPPERCASE in SYSCAT."
            )

        schema_lines = [f"=== IBM Db2 SCHEMA FOR TABLE [{target_schema}.{clean_table}] ==="]
        for col in rows:
            null_flag = "NULLABLE" if col.get("NULLS") == "Y" else "NOT NULL"
            scale_info = f", scale: {col.get('SCALE')}" if col.get("SCALE") else ""
            default_val = f", default: {col.get('DEFAULT')}" if col.get("DEFAULT") else ""
            schema_lines.append(
                f"  • {col.get('COLNAME')} | Type: {col.get('TYPENAME')}({col.get('LENGTH')}{scale_info}) | {null_flag}{default_val}"
            )
        return "\n".join(schema_lines)
    except Exception as exc:
        parsed_err = Db2ErrorParser.parse(str(exc))
        return parsed_err.to_agent_feedback(sql)


@tool
def introspect_db2_schema(table_name: str, schema_name: Optional[str] = None) -> str:
    """
    Queries IBM Db2 SYSCAT.COLUMNS using strictly UPPERCASE table and schema identifiers.
    Returns exact column names, data types, lengths, nullability, and defaults for the given table.
    """
    return run_introspect_db2_schema(table_name, schema_name)


def run_execute_safe_db2_query(query: str) -> str:
    """
    Executes a validated read-only SQL query against IBM Db2.
    1. Guardrails: Strictly rejects DROP, ALTER, TRUNCATE.
    2. Dialect: Automatically converts LIMIT -> FETCH FIRST n ROWS ONLY and DUAL -> SYSIBM.SYSDUMMY1.
    3. Closed-Loop: Intercepts all SQLSTATE error codes and returns structured remediation feedback.
    """
    # 1. Enforce Read-Only Inspection Guardrails
    guardrail_error = Db2DialectEnforcer.check_guardrails(query)
    if guardrail_error:
        return guardrail_error

    # 2. Enforce Dialect Constraints
    transpiled_sql, modifications = Db2DialectEnforcer.transpile_or_flag_dialect(query)

    # 3. Execute and Intercept SQLSTATE errors
    try:
        rows = Db2ConnectionManager.execute_query(transpiled_sql)
        output = _format_table_output(rows)
        if modifications:
            notes = "\n".join([f"[DIALECT AUTO-FIX]: {m}" for m in modifications])
            return f"{notes}\n\n{output}"
        return output
    except Exception as exc:
        raw_error_message = str(exc)
        parsed_error = Db2ErrorParser.parse(raw_error_message)
        # Closed-loop self-correction feedback loop
        return parsed_error.to_agent_feedback(query)


@tool
def execute_safe_db2_query(query: str) -> str:
    """
    Executes a SELECT inspection query on IBM Db2.
    - Strictly prohibits destructive DDL: DROP, ALTER, TRUNCATE.
    - Enforces Db2 dialect: uses FETCH FIRST n ROWS ONLY instead of LIMIT, and SYSIBM.SYSDUMMY1 for dual/scalar queries.
    - On failure, intercepts SQLSTATE error codes (e.g. -204 undefined name, -206 column not found, -104 syntax error)
      and returns detailed remediation directives for closed-loop self-correction.
    """
    return run_execute_safe_db2_query(query)


def run_record_audit_action(audit_id: str, trigger_event: str, anomaly: str, patch_sql: str) -> str:
    """Inserts an immutable audit trace into Db2 AUDIT_RECONCILIATION_LOG table."""
    try:
        clean_id = audit_id.strip() or f"AUD-{uuid.uuid4().hex[:8].upper()}"
        success = Db2ConnectionManager.insert_audit_log(
            audit_id=clean_id,
            trigger_event=trigger_event,
            anomaly=anomaly,
            patch_sql=patch_sql
        )
        if success:
            return (
                f"SUCCESS: Immutable audit record committed to Db2 AUDIT_RECONCILIATION_LOG.\n"
                f"  • Audit ID: {clean_id}\n"
                f"  • Trigger Event: {trigger_event}\n"
                f"  • Anomaly: {anomaly}\n"
                f"  • Status: PENDING_APPROVAL\n"
                f"  • Proposed Patch: {patch_sql}"
            )
        return "Failed to commit audit record."
    except Exception as exc:
        parsed_err = Db2ErrorParser.parse(str(exc))
        return parsed_err.to_agent_feedback("INSERT INTO AUDIT_RECONCILIATION_LOG ...")


@tool
def record_audit_action(audit_id: str, trigger_event: str, anomaly: str, patch_sql: str) -> str:
    """
    Records an immutable audit trace into the IBM Db2 AUDIT_RECONCILIATION_LOG table.
    Use this to persist identified anomalies, mathematical variances, and proposed idempotent SQL reconciliation patches.
    """
    return run_record_audit_action(audit_id, trigger_event, anomaly, patch_sql)
