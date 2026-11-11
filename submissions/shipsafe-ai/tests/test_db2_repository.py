import unittest
import time
from shipsafe.models import Assessment, Finding
from shipsafe.db2 import Db2Repository


class TestDb2Repository(unittest.TestCase):
    def setUp(self):
        # Offline unit-test backend; see test_db2_integration.py for live IBM Db2
        self.repo = Db2Repository(backend="sqlite")

    def test_schema_and_connection(self):
        status = self.repo.check_connection()
        self.assertTrue(status["connected"])

    def test_save_and_retrieve_assessment(self):
        asm = Assessment(
            assessment_id="asm_test_01",
            project_id="prj_test",
            commit_sha="abcdef123456",
            base_sha=None,
            profile="pre-pr",
            status="BLOCKED",
            gate_reason="Blocked on critical secret",
            started_at=int(time.time() * 1000),
            finished_at=int(time.time() * 1000) + 500,
            findings_count=1,
            critical_count=1,
        )
        self.repo.save_project("prj_test", "hash123", "Test Project")
        self.repo.save_assessment(asm)

        retrieved = self.repo.get_assessment("asm_test_01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["ASSESSMENT_ID"], "asm_test_01")
        self.assertEqual(retrieved["STATUS"], "BLOCKED")

    def test_regression_comparison(self):
        self.repo.save_project("prj_test", "hash123", "Test Project")

        # Run 1: has Issue A and Issue B
        f_a = Finding.create("asm_1", "bandit", "B608", "security", "critical", "high", "Issue A", "desc")
        f_b = Finding.create("asm_1", "bandit", "B602", "security", "high", "high", "Issue B", "desc")
        self.repo.save_findings([f_a, f_b])

        # Run 2: Issue A resolved, Issue B remains, Issue C introduced
        f_b2 = Finding.create("asm_2", "bandit", "B602", "security", "high", "high", "Issue B", "desc")
        f_c = Finding.create("asm_2", "bandit", "B307", "security", "critical", "high", "Issue C", "desc")
        self.repo.save_findings([f_b2, f_c])

        diff = self.repo.compare_assessments("asm_1", "asm_2")
        self.assertEqual(diff["new_count"], 1)
        self.assertEqual(diff["resolved_count"], 1)
        self.assertEqual(diff["unchanged_count"], 1)

    def test_get_single_finding_roundtrip(self):
        f = Finding.create("asm_9", "shipsafe_secrets_scanner", "SEC-001", "secrets", "critical", "high",
                           "AWS Access Key ID Detected", "desc", file_path="src/api.py", line_start=7,
                           evidence={"snippet": "[REDACTED_AWS_KEY]"})
        self.repo.save_findings([f])
        got = self.repo.get_finding(f.finding_id)
        self.assertEqual(got["RULE_ID"], "SEC-001")
        self.assertEqual(got["EVIDENCE"]["snippet"], "[REDACTED_AWS_KEY]")


if __name__ == "__main__":
    unittest.main()
