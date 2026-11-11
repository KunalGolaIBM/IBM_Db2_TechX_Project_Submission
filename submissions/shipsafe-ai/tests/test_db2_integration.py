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


@unittest.skipUnless(os.getenv("SHIPSAFE_DB2_INTEGRATION") == "1", "set SHIPSAFE_DB2_INTEGRATION=1 to run against live Db2")
class TestLiveApi(unittest.TestCase):
    """The HTTP API end to end on IBM Db2: pool, auth, scan job, audit trail, vector search."""

    @classmethod
    def setUpClass(cls):
        import time as _time

        from fastapi.testclient import TestClient

        from shipsafe.api import create_app
        from shipsafe.config import ShipSafeConfig
        from shipsafe.db2.pool import ConnectionPool
        from shipsafe.security import issue_token

        cls.time = _time
        cfg = ShipSafeConfig.load()
        cfg.allowed_roots, cfg.pip_audit = [str(FIXTURES)], "off"
        cls.pool = ConnectionPool(cfg.db2, size=2)
        cls.tid, tok, digest = issue_token()
        with cls.pool.repository() as repo:
            repo.create_token(cls.tid, "integration-test", "admin", digest)
        cls.client = TestClient(create_app(cfg, cls.pool))
        cls.h = {"Authorization": f"Bearer {tok}"}

    @classmethod
    def tearDownClass(cls):
        with cls.pool.repository() as repo:
            repo.revoke_token(cls.tid)

    def test_ready_reports_db2_and_vectors(self):
        body = self.client.get("/api/ready").json()
        self.assertEqual(body["db2"]["engine"], "IBM Db2")
        self.assertGreater(body["db2"]["policy_chunks"], 0)

    def test_scan_persists_and_is_audited(self):
        job = self.client.post("/api/scans", json={"target": "vulnerable_project"}, headers=self.h).json()
        for _ in range(300):
            job = self.client.get(f"/api/scans/{job['job_id']}", headers=self.h).json()
            if job["status"] in ("done", "failed"):
                break
            self.time.sleep(0.1)
        self.assertEqual(job["status"], "done", job.get("error"))
        self.assertTrue(job["persisted"])
        detail = self.client.get(f"/api/assessments/{job['assessment_id']}", headers=self.h).json()
        cited = [f for f in detail["findings"] if (f["EVIDENCE"] or {}).get("policy")]
        self.assertEqual(len(cited), len(detail["findings"]))  # every finding carries a Db2-retrieved policy
        actions = {e["ACTION"] for e in self.client.get("/api/audit", headers=self.h).json()["items"]}
        self.assertTrue({"scan.requested", "scan.completed"} <= actions)

    def test_policy_search(self):
        r = self.client.post("/api/policies/search", json={"query": "where do I keep the Db2 password"}, headers=self.h)
        self.assertEqual(r.json()["results"][0]["doc_id"], "POL-SEC-002")


if __name__ == "__main__":
    unittest.main()
