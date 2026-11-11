"""HTTP API tests: auth, roles, allowlisting, rate limiting, scan jobs, exports.

Runs on the offline SQLite backend so it needs no database; the same routes run
against IBM Db2 in test_db2_integration.py.
"""
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from shipsafe.api import create_app
from shipsafe.config import ShipSafeConfig
from shipsafe.db2.pool import ConnectionPool
from shipsafe.security import issue_token

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = ShipSafeConfig(backend="sqlite", allowed_roots=[str(FIXTURES)], scan_rate_per_minute=3,
                                    use_bandit=False, pip_audit="off")
        cls.pool = ConnectionPool(cls.config.db2, backend="sqlite")
        cls.tokens = {}
        with cls.pool.repository() as repo:
            for role in ("viewer", "operator", "admin"):
                tid, tok, digest = issue_token()
                repo.create_token(tid, f"test-{role}", role, digest)
                cls.tokens[role] = tok
        cls.client = TestClient(create_app(cls.config, cls.pool))

    def h(self, role):
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def wait_job(self, job_id, role="operator"):
        for _ in range(200):
            job = self.client.get(f"/api/scans/{job_id}", headers=self.h(role)).json()
            if job["status"] in ("done", "failed"):
                return job
            time.sleep(0.1)
        self.fail("scan job did not finish")

    def test_health_is_public_and_sets_security_headers(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_requires_token(self):
        self.assertEqual(self.client.get("/api/overview").status_code, 401)
        r = self.client.get("/api/overview", headers={"Authorization": "Bearer ss_wrong"})
        self.assertEqual(r.status_code, 401)

    def test_denied_request_is_audited(self):
        self.client.get("/api/me", headers={"Authorization": "Bearer ss_not_a_token"})
        audit = self.client.get("/api/audit", headers=self.h("admin")).json()["items"]
        self.assertTrue(any(e["ACTION"] == "auth.denied" for e in audit))

    def test_viewer_cannot_scan_or_manage_tokens(self):
        r = self.client.post("/api/scans", json={"target": "clean_project"}, headers=self.h("viewer"))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/tokens", headers=self.h("viewer")).status_code, 403)
        self.assertEqual(self.client.get("/api/tokens", headers=self.h("operator")).status_code, 403)

    def test_target_outside_allowed_roots_is_rejected(self):
        for target in ("../../..", "C:/Windows", "/etc", "clean_project/../../src"):
            r = self.client.post("/api/scans", json={"target": target}, headers=self.h("operator"))
            self.assertEqual(r.status_code, 400, target)

    def test_invalid_profile_rejected(self):
        r = self.client.post("/api/scans", json={"target": "clean_project", "profile": "everything"},
                             headers=self.h("operator"))
        self.assertEqual(r.status_code, 422)

    def test_scan_job_end_to_end_and_exports(self):
        r = self.client.post("/api/scans", json={"target": "vulnerable_project"}, headers=self.h("admin"))
        self.assertEqual(r.status_code, 202)
        job = self.wait_job(r.json()["job_id"], "admin")
        self.assertEqual(job["status"], "done", job.get("error"))
        self.assertEqual(job["gate"], "BLOCKED")
        self.assertTrue(job["persisted"])
        aid = job["assessment_id"]
        steps = [s["key"] for s in job["steps"]]
        self.assertEqual(steps[0], "discover")
        self.assertEqual(steps[-1], "done")

        detail = self.client.get(f"/api/assessments/{aid}", headers=self.h("viewer")).json()
        rules = {f["RULE_ID"] for f in detail["findings"]}
        self.assertTrue({"SEC-001", "B608-SQLI", "CVE-2020-14343"} <= rules)
        self.assertTrue(detail["dependencies"])

        sarif = self.client.get(f"/api/assessments/{aid}/report?format=sarif", headers=self.h("viewer")).json()
        self.assertEqual(sarif["version"], "2.1.0")
        self.assertEqual(len(sarif["runs"][0]["results"]), len(detail["findings"]))
        md = self.client.get(f"/api/assessments/{aid}/report?format=markdown", headers=self.h("viewer"))
        self.assertIn("Release gate", md.text)

        overview = self.client.get("/api/overview", headers=self.h("viewer")).json()
        self.assertGreaterEqual(overview["stats"]["assessments"], 1)

    def test_rate_limit(self):
        cfg = ShipSafeConfig(backend="sqlite", allowed_roots=[str(FIXTURES)], scan_rate_per_minute=1,
                             use_bandit=False, pip_audit="off")
        pool = ConnectionPool(cfg.db2, backend="sqlite")
        with pool.repository() as repo:
            tid, tok, digest = issue_token()
            repo.create_token(tid, "rl", "operator", digest)
        client = TestClient(create_app(cfg, pool))
        hdr = {"Authorization": f"Bearer {tok}"}
        self.assertEqual(client.post("/api/scans", json={"target": "clean_project", "profile": "quick"}, headers=hdr).status_code, 202)
        self.assertEqual(client.post("/api/scans", json={"target": "clean_project", "profile": "quick"}, headers=hdr).status_code, 429)

    def test_token_lifecycle(self):
        r = self.client.post("/api/tokens", json={"name": "ci bot", "role": "viewer"}, headers=self.h("admin"))
        self.assertEqual(r.status_code, 201)
        new = r.json()
        self.assertTrue(new["token"].startswith("ss_"))
        hdr = {"Authorization": f"Bearer {new['token']}"}
        self.assertEqual(self.client.get("/api/me", headers=hdr).json()["role"], "viewer")
        self.assertEqual(self.client.delete(f"/api/tokens/{new['token_id']}", headers=self.h("admin")).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=hdr).status_code, 401)
        listed = self.client.get("/api/tokens", headers=self.h("admin")).json()["items"]
        self.assertNotIn("TOKEN_HASH", listed[0])

    def test_token_name_validation(self):
        r = self.client.post("/api/tokens", json={"name": "<script>", "role": "admin"}, headers=self.h("admin"))
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
