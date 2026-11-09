"""
Db2-Sentinel Unit & Integration Test Suite
Validates:
1. Destructive DDL Guardrail Enforcement (DROP, ALTER, TRUNCATE).
2. Db2 Dialect Transpilation (LIMIT -> FETCH FIRST n ROWS ONLY, DUAL -> SYSIBM.SYSDUMMY1).
3. Uppercase SYSCAT.TABLES and SYSCAT.COLUMNS Introspection.
4. Closed-Loop SQLSTATE Error Interception & Diagnostic Formatting.
5. Multi-Round Iterative Query Self-Correction.
6. Immutable Audit Log Commit.
"""

import unittest
import sys
import os

# Add db2-sentinel to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db2_engine import (
    Db2DialectEnforcer,
    Db2ErrorParser,
    Db2ConnectionManager,
)
from core.db2_tools import (
    run_execute_safe_db2_query,
    run_introspect_db2_schema,
    run_introspect_db2_tables,
    run_record_audit_action,
)
from core.agent_graph import (
    execute_self_correcting_query,
    run_simulated_audit_cycle,
)


class TestDb2SentinelGuardrails(unittest.TestCase):
    def test_reject_drop(self):
        query = "DROP TABLE INVOICES"
        res = run_execute_safe_db2_query(query)
        self.assertIn("GUARDRAIL_VIOLATION", res)
        self.assertIn("DROP", res)

    def test_reject_alter(self):
        query = "ALTER TABLE INVOICES ADD COLUMN EXTRA VARCHAR(10)"
        res = run_execute_safe_db2_query(query)
        self.assertIn("GUARDRAIL_VIOLATION", res)
        self.assertIn("ALTER", res)

    def test_reject_truncate(self):
        query = "TRUNCATE TABLE INVOICE_ITEMS IMMEDIATE"
        res = run_execute_safe_db2_query(query)
        self.assertIn("GUARDRAIL_VIOLATION", res)
        self.assertIn("TRUNCATE", res)

    def test_allow_safe_select(self):
        query = "SELECT INVOICE_ID FROM INVOICES FETCH FIRST 2 ROWS ONLY"
        res = run_execute_safe_db2_query(query)
        self.assertNotIn("GUARDRAIL_VIOLATION", res)


class TestDb2DialectConstraints(unittest.TestCase):
    def test_limit_transpilation(self):
        sql = "SELECT * FROM INVOICES LIMIT 5"
        transpiled, mods = Db2DialectEnforcer.transpile_or_flag_dialect(sql)
        self.assertEqual(transpiled, "SELECT * FROM INVOICES FETCH FIRST 5 ROWS ONLY")
        self.assertTrue(len(mods) > 0)

    def test_limit_with_offset_transpilation(self):
        sql = "SELECT * FROM INVOICES LIMIT 10 OFFSET 20"
        transpiled, mods = Db2DialectEnforcer.transpile_or_flag_dialect(sql)
        self.assertEqual(transpiled, "SELECT * FROM INVOICES OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY")

    def test_dual_replacement(self):
        sql = "SELECT CURRENT TIMESTAMP FROM DUAL"
        transpiled, mods = Db2DialectEnforcer.transpile_or_flag_dialect(sql)
        self.assertEqual(transpiled, "SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")


class TestDb2ErrorParserAndSQLSTATE(unittest.TestCase):
    def test_parse_sql0204n_undefined_table(self):
        raw = '[IBM][CLI Driver][DB2/LINUXX8664] SQL0204N  "DB2INST1.UNKNOWN_TBL" is an undefined name.  SQLSTATE=42704'
        info = Db2ErrorParser.parse(raw)
        self.assertEqual(info.sqlcode, -204)
        self.assertEqual(info.sqlstate, "42704")
        self.assertIn("UNDEFINED_OBJECT", info.category)
        self.assertIn("UPPERCASE", info.remediation_guidance)

    def test_parse_sql0206n_undefined_column(self):
        raw = '[IBM][CLI Driver][DB2/LINUXX8664] SQL0206N  "TOTAL_AMOUNT" is not valid in the context where it is used.  SQLSTATE=42703'
        info = Db2ErrorParser.parse(raw)
        self.assertEqual(info.sqlcode, -206)
        self.assertEqual(info.sqlstate, "42703")
        self.assertIn("UNDEFINED_COLUMN", info.category)
        self.assertIn("SYSCAT.COLUMNS", info.remediation_guidance)

    def test_parse_sql0104n_syntax_error(self):
        raw = '[IBM][CLI Driver][DB2/LINUXX8664] SQL0104N  An unexpected token "LIMIT" was found.  SQLSTATE=42601'
        info = Db2ErrorParser.parse(raw)
        self.assertEqual(info.sqlcode, -104)
        self.assertEqual(info.sqlstate, "42601")
        self.assertIn("FETCH FIRST n ROWS ONLY", info.remediation_guidance)


class TestDb2CatalogIntrospection(unittest.TestCase):
    def test_introspect_tables_uppercase(self):
        out = run_introspect_db2_tables("db2inst1")
        self.assertIn("INVOICES", out)
        self.assertIn("INVOICE_ITEMS", out)
        self.assertIn("ACCOUNTS_LEDGER", out)

    def test_introspect_columns_uppercase(self):
        out = run_introspect_db2_schema("invoices", "db2inst1")
        self.assertIn("REPORTED_TOTAL", out)
        self.assertIn("INVOICE_ID", out)


class TestClosedLoopSelfCorrection(unittest.TestCase):
    def test_self_correcting_column_mismatch(self):
        # Query uses invalid column 'TOTAL_PRICE'
        res = execute_self_correcting_query("SELECT INVOICE_ID, TOTAL_PRICE FROM INVOICES")
        self.assertEqual(res["final_status"], "SUCCESS")
        self.assertIn("REPORTED_TOTAL", res["final_sql"])

    def test_audit_cycle_anomaly_detection(self):
        cycle = run_simulated_audit_cycle("Verify invoice totals")
        self.assertIn("INV-2026-001", cycle["final_report"])
        self.assertIn("+$300.00", cycle["final_report"])
        self.assertIn("AUDIT_RECONCILIATION_LOG", cycle["final_report"])


    def test_sysibm_sysdummy1_scalar(self):
        res = run_execute_safe_db2_query("SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")
        self.assertIn("DB2_ONLINE", res)

    def test_dual_to_sysdummy1_execution(self):
        res = run_execute_safe_db2_query("SELECT CURRENT TIMESTAMP FROM DUAL")
        self.assertIn("DB2_ONLINE", res)
        self.assertIn("SYSIBM.SYSDUMMY1", res)

    def test_record_audit_action_persistence(self):
        audit_id = "AUD-TEST-999"
        res = run_record_audit_action(
            audit_id=audit_id,
            trigger_event="Unit Test Trigger",
            anomaly="Unit test anomaly detected",
            patch_sql="UPDATE INVOICES SET STATUS = 'TEST' WHERE INVOICE_ID = 'INV-999';"
        )
        self.assertIn("SUCCESS", res)
        self.assertIn(audit_id, res)

    def test_sqlstate_routine_not_found(self):
        raw = '[IBM][CLI Driver][DB2/LINUXX8664] SQL0440N No authorized routine named "CONCAT_WS" found. SQLSTATE=42884'
        info = Db2ErrorParser.parse(raw)
        self.assertEqual(info.sqlcode, -440)
        self.assertEqual(info.sqlstate, "42884")
        self.assertIn("ROUTINE_NOT_FOUND", info.category)

    def test_sqlstate_invalid_datetime(self):
        raw = '[IBM][CLI Driver][DB2/LINUXX8664] SQL0180N Datetime syntax error. SQLSTATE=22007'
        info = Db2ErrorParser.parse(raw)
        self.assertEqual(info.sqlcode, -180)
        self.assertEqual(info.sqlstate, "22007")
        self.assertIn("INVALID_DATETIME_FORMAT", info.category)


if __name__ == "__main__":
    unittest.main()
