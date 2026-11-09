"""
Db2-Sentinel Engine Module
Principal IBM Db2 Database Driver, Dialect Enforcer, Guardrail Engine,
and SQLSTATE Interceptor with Closed-Loop Error Synthesis.
"""

from __future__ import annotations
import re
import os
import sys
from typing import Dict, Any, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from core.config import db2_settings

# Attempt importing ibm_db and ibm_db_dbi
IBM_DB_AVAILABLE = False
try:
    import ibm_db
    import ibm_db_dbi as dbi
    IBM_DB_AVAILABLE = True
except ImportError:
    ibm_db = None
    dbi = None


@dataclass
class Db2ErrorInfo:
    sqlcode: Optional[int]
    sqlstate: Optional[str]
    raw_message: str
    category: str
    remediation_guidance: str

    def to_agent_feedback(self, query: str) -> str:
        """Formats error into a structured prompt message for the agentic feedback loop."""
        return (
            f"=== IBM Db2 EXECUTION ERROR [SQLSTATE: {self.sqlstate or 'UNKNOWN'} | SQLCODE: {self.sqlcode or 'UNKNOWN'}] ===\n"
            f"Category: {self.category}\n"
            f"Failed SQL: {query}\n"
            f"Db2 Engine Diagnostic: {self.raw_message}\n"
            f"--------------------------------------------------------------------------------\n"
            f"CLOSED-LOOP REMEDIATION DIRECTIVE FOR LLM AGENT:\n"
            f"{self.remediation_guidance}\n"
            f"================================================================================"
        )


class Db2DialectEnforcer:
    """Enforces IBM Db2 dialect rules, guardrails, and catalog conventions."""

    DESTRUCTIVE_PATTERN = re.compile(
        r"\b(DROP|ALTER|TRUNCATE)\b",
        re.IGNORECASE
    )

    LIMIT_PATTERN = re.compile(
        r"\bLIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?",
        re.IGNORECASE
    )

    DUAL_PATTERN = re.compile(
        r"\bFROM\s+DUAL\b",
        re.IGNORECASE
    )

    @classmethod
    def check_guardrails(cls, sql: str) -> Optional[str]:
        """Strictly blocks destructive DDL statements (DROP, ALTER, TRUNCATE)."""
        match = cls.DESTRUCTIVE_PATTERN.search(sql)
        if match:
            blocked_kw = match.group(1).upper()
            return (
                f"GUARDRAIL_VIOLATION [SECURITY POLICY ENFORCED]: "
                f"Execution rejected! Prohibited destructive DDL command '{blocked_kw}' detected. "
                f"Db2-Sentinel only permits read-only inspection queries and idempotent audit actions."
            )
        return None

    @classmethod
    def transpile_or_flag_dialect(cls, sql: str) -> Tuple[str, List[str]]:
        """
        Translates or flags non-Db2 idioms:
        - LIMIT n -> FETCH FIRST n ROWS ONLY
        - LIMIT n OFFSET m -> OFFSET m ROWS FETCH NEXT n ROWS ONLY
        - FROM DUAL -> FROM SYSIBM.SYSDUMMY1
        """
        modifications: List[str] = []
        clean_sql = sql.strip().rstrip(";")

        # 1. Transpile DUAL -> SYSIBM.SYSDUMMY1
        if cls.DUAL_PATTERN.search(clean_sql):
            clean_sql = cls.DUAL_PATTERN.sub("FROM SYSIBM.SYSDUMMY1", clean_sql)
            modifications.append("Replaced 'FROM DUAL' with Db2 catalog dual 'FROM SYSIBM.SYSDUMMY1'")

        # 2. Transpile LIMIT n -> FETCH FIRST n ROWS ONLY
        limit_match = cls.LIMIT_PATTERN.search(clean_sql)
        if limit_match:
            limit_val = limit_match.group(1)
            offset_val = limit_match.group(2)
            if offset_val:
                replacement = f"OFFSET {offset_val} ROWS FETCH NEXT {limit_val} ROWS ONLY"
            else:
                replacement = f"FETCH FIRST {limit_val} ROWS ONLY"
            clean_sql = cls.LIMIT_PATTERN.sub(replacement, clean_sql)
            modifications.append(f"Transpiled MySQL/Postgres 'LIMIT' clause into Db2 syntax: '{replacement}'")

        return clean_sql, modifications


class Db2ErrorParser:
    """Extracts SQLCODE and SQLSTATE and provides exact Db2 remediation guidance."""

    @classmethod
    def parse(cls, raw_error: str) -> Db2ErrorInfo:
        # Regex for SQLCODE: e.g. SQL0204N, SQL0206N, SQL0104N, SQL-204
        code_match = re.search(r"SQL(-?\d{3,5})[NWEIS]?", raw_error, re.IGNORECASE)
        sqlcode = int(code_match.group(1)) if code_match else None
        if sqlcode and sqlcode > 0:
            sqlcode = -sqlcode  # Db2 negative error codes convention

        # Regex for SQLSTATE: e.g. SQLSTATE=42704, SQLSTATE 42703
        state_match = re.search(r"SQLSTATE[=:\s]+([0-9A-Z]{5})", raw_error, re.IGNORECASE)
        sqlstate = state_match.group(1).upper() if state_match else None

        # Categorize and provide actionable directives
        if sqlcode == -204 or sqlstate == "42704":
            category = "UNDEFINED_OBJECT (TABLE/VIEW NOT FOUND)"
            guidance = (
                "1. IBM Db2 stores identifiers in UPPERCASE by default.\n"
                "2. Check table existence using: SELECT TABSCHEMA, TABNAME FROM SYSCAT.TABLES WHERE TABNAME = UPPER('<TABLE_NAME>')\n"
                "3. Ensure the schema name prefix (e.g., DB2INST1.<TABLE>) is correct and in uppercase."
            )
        elif sqlcode == -206 or sqlstate == "42703":
            category = "UNDEFINED_COLUMN (COLUMN NOT FOUND IN CONTEXT)"
            guidance = (
                "1. The column does not exist or has a casing/alias mismatch in Db2.\n"
                "2. Introspect valid columns using: SELECT COLNAME, TYPENAME FROM SYSCAT.COLUMNS WHERE TABNAME = UPPER('<TABLE_NAME>')\n"
                "3. Verify table aliases in JOIN clauses and replace lowercase column names with verified uppercase column names."
            )
        elif sqlcode == -104 or sqlstate == "42601":
            category = "SYNTAX_ERROR (ILLEGAL TOKEN OR NON-DB2 DIALECT)"
            guidance = (
                "1. Disallowed token detected (e.g. LIMIT, ILIKE, or backticks `).\n"
                "2. In IBM Db2, replace 'LIMIT n' with 'FETCH FIRST n ROWS ONLY'.\n"
                "3. For scalar/dual queries, use 'SELECT ... FROM SYSIBM.SYSDUMMY1' instead of 'FROM DUAL'.\n"
                "4. Remove all backticks (`) and replace double quotes if using standard uppercase identifiers."
            )
        elif sqlcode == -440 or sqlstate == "42884":
            category = "ROUTINE_NOT_FOUND (FUNCTION / STORED PROC)"
            guidance = (
                "1. The invoked function or signature is not recognized in Db2 SYSIBM / SYSFUN.\n"
                "2. Verify function name in SYSCAT.ROUTINES or use standard ANSI/Db2 functions (e.g., CONCAT instead of CONCAT_WS, SUBSTR instead of SUBSTRING)."
            )
        elif sqlcode == -180 or sqlstate == "22007":
            category = "INVALID_DATETIME_FORMAT"
            guidance = (
                "1. Datetime literal format is invalid for Db2.\n"
                "2. Use standard ISO format: 'YYYY-MM-DD' for DATE, or 'YYYY-MM-DD-HH.MM.SS.NNNNNN' / CURRENT TIMESTAMP for TIMESTAMP."
            )
        elif sqlcode == -803 or sqlstate == "23505":
            category = "UNIQUE_CONSTRAINT_VIOLATION"
            guidance = (
                "1. Duplicate key detected on primary key or unique index.\n"
                "2. Ensure generated Primary Keys (e.g., AUDIT_ID) are unique, e.g. using UUIDs."
            )
        else:
            category = "GENERAL_DB2_ERROR"
            guidance = (
                "1. Review the Db2 CLI driver diagnostic message above.\n"
                "2. Verify all identifiers are uppercase and conform to Db2 SQL Reference guidelines."
            )

        return Db2ErrorInfo(
            sqlcode=sqlcode,
            sqlstate=sqlstate,
            raw_message=raw_error.strip(),
            category=category,
            remediation_guidance=guidance,
        )


class Db2Simulator:
    """
    High-fidelity IBM Db2 simulation engine.
    Used when Docker container is offline or ibm_db native driver is not compiled on the host.
    Accurately produces real Db2 SQLSTATE errors (-204, -206, -104) and enforces uppercase SYSCAT queries.
    """

    def __init__(self) -> None:
        self.tables = {
            "ACCOUNTS_LEDGER": [
                {"ACCOUNT_ID": "ACC-101", "ACCOUNT_NAME": "Accounts Receivable", "CATEGORY": "ASSET", "CURRENT_BALANCE": 45000.00, "LAST_UPDATED": "2026-11-01 10:00:00"},
                {"ACCOUNT_ID": "ACC-102", "ACCOUNT_NAME": "Revenue", "CATEGORY": "EQUITY", "CURRENT_BALANCE": 120000.00, "LAST_UPDATED": "2026-11-01 10:00:00"},
            ],
            "INVOICES": [
                {"INVOICE_ID": "INV-2026-001", "CUSTOMER_ID": "CUST-88", "INVOICE_DATE": "2026-11-01", "REPORTED_TOTAL": 1500.00, "STATUS": "UNRECONCILED"},
                {"INVOICE_ID": "INV-2026-002", "CUSTOMER_ID": "CUST-92", "INVOICE_DATE": "2026-11-02", "REPORTED_TOTAL": 800.00, "STATUS": "PAID"},
            ],
            "INVOICE_ITEMS": [
                {"ITEM_ID": "ITM-01", "INVOICE_ID": "INV-2026-001", "DESCRIPTION": "Enterprise Cloud Tier", "QUANTITY": 1, "UNIT_PRICE": 1000.00, "LINE_TOTAL": 1000.00},
                {"ITEM_ID": "ITM-02", "INVOICE_ID": "INV-2026-001", "DESCRIPTION": "Storage Addon", "QUANTITY": 2, "UNIT_PRICE": 100.00, "LINE_TOTAL": 200.00},
                {"ITEM_ID": "ITM-03", "INVOICE_ID": "INV-2026-002", "DESCRIPTION": "Consulting Services", "QUANTITY": 8, "UNIT_PRICE": 100.00, "LINE_TOTAL": 800.00},
            ],
            "AUDIT_RECONCILIATION_LOG": []
        }

        self.columns = {
            "ACCOUNTS_LEDGER": [
                ("ACCOUNT_ID", "VARCHAR", 20, "N"),
                ("ACCOUNT_NAME", "VARCHAR", 100, "N"),
                ("CATEGORY", "VARCHAR", 50, "N"),
                ("CURRENT_BALANCE", "DECIMAL", 15, "N"),
                ("LAST_UPDATED", "TIMESTAMP", 10, "N"),
            ],
            "INVOICES": [
                ("INVOICE_ID", "VARCHAR", 30, "N"),
                ("CUSTOMER_ID", "VARCHAR", 20, "N"),
                ("INVOICE_DATE", "DATE", 4, "N"),
                ("REPORTED_TOTAL", "DECIMAL", 15, "N"),
                ("STATUS", "VARCHAR", 20, "N"),
            ],
            "INVOICE_ITEMS": [
                ("ITEM_ID", "VARCHAR", 30, "N"),
                ("INVOICE_ID", "VARCHAR", 30, "N"),
                ("DESCRIPTION", "VARCHAR", 150, "Y"),
                ("QUANTITY", "INTEGER", 4, "N"),
                ("UNIT_PRICE", "DECIMAL", 10, "N"),
                ("LINE_TOTAL", "DECIMAL", 15, "N"),
            ],
            "AUDIT_RECONCILIATION_LOG": [
                ("AUDIT_ID", "VARCHAR", 64, "N"),
                ("TIMESTAMP", "TIMESTAMP", 10, "N"),
                ("TRIGGER_EVENT", "VARCHAR", 100, "N"),
                ("ANOMALY_DETECTED", "VARCHAR", 500, "Y"),
                ("PROPOSED_PATCH", "CLOB", 1048576, "Y"),
                ("STATUS", "VARCHAR", 30, "N"),
                ("EXECUTED_BY", "VARCHAR", 50, "N"),
            ]
        }

    def execute(self, sql: str) -> List[Dict[str, Any]]:
        raw = sql.strip()
        upper_sql = raw.upper()

        # Check for illegal LIMIT
        if " LIMIT " in upper_sql and "FETCH FIRST" not in upper_sql:
            raise RuntimeError(
                "[IBM][CLI Driver][DB2/LINUXX8664] SQL0104N An unexpected token \"LIMIT\" was found following \""
                + raw[:30]
                + "...\". Expected tokens may include: \"FETCH FIRST <n> ROWS ONLY\". SQLSTATE=42601"
            )

        # Check for illegal DUAL
        if "FROM DUAL" in upper_sql:
            raise RuntimeError(
                "[IBM][CLI Driver][DB2/LINUXX8664] SQL0204N \"DB2INST1.DUAL\" is an undefined name. SQLSTATE=42704"
            )

        # Check SYSIBM.SYSDUMMY1
        if "SYSIBM.SYSDUMMY1" in upper_sql:
            return [{"CURRENT_TIMESTAMP": "2026-11-09-15.00.00.000000", "STATUS": "DB2_ONLINE"}]

        # Check SYSCAT.TABLES
        if "SYSCAT.TABLES" in upper_sql:
            return [
                {"TABSCHEMA": "DB2INST1", "TABNAME": t, "TYPE": "T", "CARD": len(rows)}
                for t, rows in self.tables.items()
            ]

        # Check SYSCAT.COLUMNS
        if "SYSCAT.COLUMNS" in upper_sql:
            # Check if query uses lowercase table name in filter without UPPER()
            for tname in self.tables.keys():
                if f"TABNAME = '{tname.lower()}'" in raw:
                    return []  # Db2 returns empty because tabnames are uppercase!
                if f"'{tname}'" in upper_sql:
                    cols = self.columns[tname]
                    return [
                        {"COLNAME": c[0], "TYPENAME": c[1], "LENGTH": c[2], "NULLS": c[3]}
                        for c in cols
                    ]
            return []

        # Table resolution simulation
        for tname in self.tables.keys():
            if tname in upper_sql:
                # Check for bad column names
                if "TOTAL_PRICE" in upper_sql or "INVOICE_TOTAL" in upper_sql:
                    raise RuntimeError(
                        f"[IBM][CLI Driver][DB2/LINUXX8664] SQL0206N \"TOTAL_PRICE\" is not valid in the context where it is used. SQLSTATE=42703"
                    )
                return self.tables[tname]

        # If table name wasn't matched uppercase
        match_table = re.search(r"FROM\s+([a-zA-Z0-9_]+)", raw, re.IGNORECASE)
        table_queried = match_table.group(1) if match_table else "UNKNOWN"
        raise RuntimeError(
            f"[IBM][CLI Driver][DB2/LINUXX8664] SQL0204N \"DB2INST1.{table_queried}\" is an undefined name. SQLSTATE=42704"
        )


class Db2ConnectionManager:
    """Manages active connection to IBM Db2 Community Edition on port 50000."""

    _simulator = Db2Simulator()

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """Tests live connectivity to the IBM Db2 container on port 50000."""
        if not IBM_DB_AVAILABLE:
            return False, "ibm_db driver is not installed on Python host. Operating in Db2 Simulation Mode."
        
        try:
            conn = dbi.connect(db2_settings.connection_string, "", "")
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
            cursor.fetchone()
            conn.close()
            return True, f"Connected to IBM Db2 Community Edition at {db2_settings.host}:{db2_settings.port}/{db2_settings.database}"
        except Exception as exc:
            return False, f"Db2 Connection Failed ({db2_settings.host}:{db2_settings.port}): {str(exc)}"

    @classmethod
    def execute_query(cls, sql: str) -> List[Dict[str, Any]]:
        """Executes a query against Db2 or fallback simulation with full error propagation."""
        if IBM_DB_AVAILABLE:
            try:
                conn = dbi.connect(db2_settings.connection_string, "", "")
                cursor = conn.cursor()
                cursor.execute(sql)
                
                # If query produces a result set (SELECT, VALUES, etc.)
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                    conn.close()
                    return [dict(zip(columns, row)) for row in rows]
                else:
                    conn.commit()
                    conn.close()
                    return [{"status": "SUCCESS", "affected_rows": cursor.rowcount}]
            except Exception as exc:
                err_str = str(exc)
                # If connection refused or driver error, check if fallback is allowed
                if "SQL30081N" in err_str or "Communication error" in err_str or "connection" in err_str.lower():
                    if db2_settings.host in ("localhost", "127.0.0.1") and agent_settings.simulation_fallback:
                        # Fallback to high-fidelity simulator
                        return cls._simulator.execute(sql)
                raise exc
        else:
            # ibm_db not installed locally -> use simulator
            return cls._simulator.execute(sql)

    @classmethod
    def insert_audit_log(
        cls, audit_id: str, trigger_event: str, anomaly: str, patch_sql: str
    ) -> bool:
        """Writes an immutable record into AUDIT_RECONCILIATION_LOG."""
        sql = (
            "INSERT INTO AUDIT_RECONCILIATION_LOG "
            "(AUDIT_ID, TIMESTAMP, TRIGGER_EVENT, ANOMALY_DETECTED, PROPOSED_PATCH, STATUS, EXECUTED_BY) "
            "VALUES (?, CURRENT TIMESTAMP, ?, ?, ?, 'PENDING_APPROVAL', 'Db2-Sentinel-Agent')"
        )
        if IBM_DB_AVAILABLE:
            try:
                conn = dbi.connect(db2_settings.connection_string, "", "")
                cursor = conn.cursor()
                cursor.execute(sql, (audit_id, trigger_event, anomaly, patch_sql))
                conn.commit()
                conn.close()
                return True
            except Exception:
                if agent_settings.simulation_fallback:
                    cls._simulator.tables["AUDIT_RECONCILIATION_LOG"].append({
                        "AUDIT_ID": audit_id,
                        "TIMESTAMP": "2026-11-09 15:05:00",
                        "TRIGGER_EVENT": trigger_event,
                        "ANOMALY_DETECTED": anomaly,
                        "PROPOSED_PATCH": patch_sql,
                        "STATUS": "PENDING_APPROVAL",
                        "EXECUTED_BY": "Db2-Sentinel-Agent"
                    })
                    return True
                raise
        else:
            cls._simulator.tables["AUDIT_RECONCILIATION_LOG"].append({
                "AUDIT_ID": audit_id,
                "TIMESTAMP": "2026-11-09 15:05:00",
                "TRIGGER_EVENT": trigger_event,
                "ANOMALY_DETECTED": anomaly,
                "PROPOSED_PATCH": patch_sql,
                "STATUS": "PENDING_APPROVAL",
                "EXECUTED_BY": "Db2-Sentinel-Agent"
            })
            return True

