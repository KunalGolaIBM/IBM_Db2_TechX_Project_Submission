"""Live IBM Db2 integration test.

Runs only when SHIPSAFE_DB2_INTEGRATION=1 and the DB2_* variables point at a
running Db2 12.1.2+ instance (for example the Docker container from the README).
"""
import os
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@unittest.skipUnless(os.getenv("SHIPSAFE_DB2_INTEGRATION") == "1", "set SHIPSAFE_DB2_INTEGRATION=1 to run against live Db2")
class TestLiveDb2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from shipsafe.runtime import build_runtime

        cls.rt = build_runtime()

    def test_connection_reports_real_db2(self):
        st = self.rt.repository.check_connection()
        self.assertEqual(st["engine"], "IBM Db2")
        self.assertGreaterEqual(st["tables_in_schema"], 8)

    def test_vector_search_returns_sql_policy(self):
        hits = self.rt.knowledge_base.retrieve("query built with an f-string is vulnerable to SQL injection", top_k=1)
        self.assertEqual(hits[0]["doc_id"], "POL-DB2-001")

    def test_vulnerable_scan_is_blocked_and_persisted(self):
        res = self.rt.orchestrator.run_assessment(str(FIXTURES / "vulnerable_project"))
        self.assertEqual(res.gate.status.value, "BLOCKED")
        stored = self.rt.repository.get_assessment(res.assessment.assessment_id)
        self.assertEqual(stored["STATUS"], "BLOCKED")
        rules = {f["RULE_ID"] for f in self.rt.repository.get_findings(res.assessment.assessment_id)}
        self.assertTrue({"SEC-001", "B608-SQLI", "CVE-2020-14343"} <= rules)

    def test_clean_scan_is_not_blocked(self):
        res = self.rt.orchestrator.run_assessment(str(FIXTURES / "clean_project"))
        self.assertNotEqual(res.gate.status.value, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
