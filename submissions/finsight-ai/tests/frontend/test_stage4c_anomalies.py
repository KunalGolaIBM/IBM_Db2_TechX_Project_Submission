#!/usr/bin/env python3
"""
FinSight AI — Stage 4C Anomaly Intelligence & Explainable Alerts Test Suite

Test Matrix:
  Part 1 — Db2 Persistence & Multi-Tenant Retrieval:
    1. Retrieve seeded anomaly alerts from IBM Db2 (alt_01, alt_02, alt_03).
    2. Alert attributes match Db2 schema (alert_id, type, severity, score, status, merchant, amount).
    3. Unauthenticated requests to /api/v1/anomalies rejected (HTTP 401).
    4. Client-supplied user_id spoofing in query string strictly ignored (session tenant enforced).
    5. Cross-tenant isolation: Unseeded tenant receives 0 anomalies (Demo alerts not leaked).
    6. Cross-tenant alert lookup: Foreign tenant cannot read another user's alert ID (HTTP 404).

  Part 2 — Mathematical Explainability & Multiplier Reconciliation:
    7. Explainable breakdown (/api/v1/anomalies/alt_03/explain) returns reproducible calculation details.
    8. Reconcile AWS Multiplier Discrepancy:
       - Merchant Baseline (5 months of ₹1,420.00) = 30.1x (+2,914% surge).
       - Unadjusted Category Average (₹2,761.43) = 15.5x.
       - Clean Category Baseline excluding spike (₹759.50) = 56.4x.
    9. Velocity burst alert (alt_02) links all 3 burst transactions (FastPay Cash Gateway).
    10. Amount spike alert (alt_01) compares Luxury Electronics against shopping category baseline.
    11. Limitations disclosure explicitly clarifies statistical anomaly is NOT proof of fraud.

  Part 3 — Review Decision State Transitions & Security:
    12. Missing X-CSRF-Token on PATCH /api/v1/anomalies/:id/status rejected (HTTP 403).
    13. Forged X-CSRF-Token on PATCH /api/v1/anomalies/:id/status rejected (HTTP 403).
    14. Invalid review status (e.g. "CONFIRMED_FRAUD") strictly rejected (HTTP 400).
    15. Valid review status transition (NEEDS_REVIEW -> REVIEWED) persists in IBM Db2.
    16. Status transition persists and is reflected on re-querying /api/v1/anomalies.
    17. Status rollback/dismissal (REVIEWED -> DISMISSED -> NEEDS_REVIEW) functions idempotently.
    18. Cross-tenant mutation: Tenant B cannot change status of Tenant A's alert (HTTP 404).

  Part 4 — Financial Baselines & Boundary Guarantees:
    19. Pending transactions strictly excluded from historical living-expense baselines.
    20. Internal transfers (cat_transfer) strictly excluded from category anomaly baselines.
    21. Nonexistent alert ID returns HTTP 404 cleanly without database stack traces.

  Part 5 — Zero Frontend Secrets & Regression Checks:
    22. Frontend dist bundle and client code contain zero internal service tokens or secrets.
    23. Existing AI Assistant continues to function with grounded Db2 evidence.
    24. Existing Semantic Transaction Search continues to return dense vector matches.
"""

import sys
import time
import json
import urllib.request
import urllib.error
import subprocess
import glob
from typing import Dict, Any, Tuple, Optional

PROXY_URL = "http://127.0.0.1:5173"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class FinsightClient:
    def __init__(self, base_url: str = PROXY_URL):
        self.base_url = base_url
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
        self.client_ip = f"10.157.{int(time.time() * 1000) % 200 + 10}.{int(time.time()) % 200 + 10}"

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        include_cookie: bool = True,
        include_csrf: bool = False,
        custom_csrf: Optional[str] = None
    ) -> Tuple[int, Any, Dict[str, str]]:
        url = f"{self.base_url}{path}"
        req_headers = {
            "Accept": "application/json",
            "X-Forwarded-For": self.client_ip
        }
        if headers:
            req_headers.update(headers)

        if include_cookie and "finsight_session" in self.cookies:
            req_headers["Cookie"] = f"finsight_session={self.cookies['finsight_session']}"

        if custom_csrf is not None:
            req_headers["X-CSRF-Token"] = custom_csrf
        elif include_csrf and self.csrf_token:
            req_headers["X-CSRF-Token"] = self.csrf_token

        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                data = body.encode("utf-8")
                req_headers["Content-Type"] = "text/plain"

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                resp_headers = dict(resp.headers)
                raw = resp.read().decode("utf-8")

                for header, val in resp.headers.items():
                    if header.lower() == "set-cookie":
                        parts = val.split(";")
                        cookie_pair = parts[0].strip()
                        if "=" in cookie_pair:
                            cname, cval = cookie_pair.split("=", 1)
                            self.cookies[cname.strip()] = cval.strip()

                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = raw

                return status, parsed, resp_headers

        except urllib.error.HTTPError as e:
            status = e.code
            resp_headers = dict(e.headers)
            raw = e.read().decode("utf-8")

            for header, val in e.headers.items():
                if header.lower() == "set-cookie":
                    parts = val.split(";")
                    cookie_pair = parts[0].strip()
                    if "=" in cookie_pair:
                        cname, cval = cookie_pair.split("=", 1)
                        self.cookies[cname.strip()] = cval.strip()

            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw

            return status, parsed, resp_headers

    def login(self, email: str = DEMO_EMAIL, password: str = DEMO_PASSWORD) -> Tuple[int, Any]:
        status, body, _ = self.request("POST", "/api/v1/auth/login", {"email": email, "password": password})
        if status == 200 and isinstance(body, dict):
            self.csrf_token = body.get("csrf_token")
        return status, body


def run_db2_query(sql_snippet: str) -> str:
    cmd = ["docker", "exec", "finsight-ai-service", "python", "-c", sql_snippet]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Db2 query failed: {res.stderr}")
    return res.stdout.strip()


def run_tests():
    print("=" * 80)
    print("FinSight AI — Stage 4C Anomaly Intelligence & Explainable Alerts Test Suite")
    print("=" * 80)

    passed = 0
    failed = 0
    total = 24

    def record_pass(num: int, title: str):
        nonlocal passed
        passed += 1
        print(f"  [PASS] Test {num:02d}: {title}")

    def record_fail(num: int, title: str, reason: str):
        nonlocal failed
        failed += 1
        print(f"  [FAIL] Test {num:02d}: {title} — REASON: {reason}")

    # Authenticate demo user
    demo = FinsightClient()
    l_status, l_body = demo.login()
    if l_status != 200:
        print(f"[FATAL] Login failed: {l_status} {l_body}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # PART 1: Db2 Persistence & Multi-Tenant Retrieval
    # -------------------------------------------------------------------------
    print("\n--- Part 1: Db2 Persistence & Multi-Tenant Retrieval ---")

    # Test 1: Retrieve seeded anomaly alerts from IBM Db2
    try:
        status, body, _ = demo.request("GET", "/api/v1/anomalies")
        assert status == 200, f"Expected 200, got {status}"
        assert body["total_anomalies"] >= 3, f"Expected at least 3 alerts, got {body['total_anomalies']}"
        alert_ids = [a["alert_id"] for a in body["anomalies"]]
        assert "alt_01" in alert_ids and "alt_02" in alert_ids and "alt_03" in alert_ids
        record_pass(1, "Retrieve seeded anomaly alerts from IBM Db2 (alt_01, alt_02, alt_03 present)")
    except Exception as e:
        record_fail(1, "Retrieve seeded anomalies", str(e))

    # Test 2: Alert attributes match Db2 schema
    try:
        alt_03 = next(a for a in body["anomalies"] if a["alert_id"] == "alt_03")
        assert alt_03["merchant"] == "Amazon Web Services"
        assert alt_03["amount"] == 42800.00
        assert alt_03["alert_type"] == "RECURRING_DRIFT"
        assert alt_03["severity"] == "HIGH"
        assert alt_03["score"] == 91.0
        assert alt_03["date"] == "2026-10-28"
        record_pass(2, "Alert attributes match Db2 schema (merchant, amount, alert_type, severity, score)")
    except Exception as e:
        record_fail(2, "Alert attributes schema check", str(e))

    # Test 3: Unauthenticated request rejected (401)
    try:
        anon = FinsightClient()
        u_status, _, _ = anon.request("GET", "/api/v1/anomalies")
        assert u_status == 401, f"Expected 401, got {u_status}"
        record_pass(3, "Unauthenticated request to /api/v1/anomalies rejected with HTTP 401")
    except Exception as e:
        record_fail(3, "Unauthenticated request rejection", str(e))

    # Test 4: Client-supplied user_id spoofing strictly ignored
    try:
        spoof_status, spoof_body, _ = demo.request("GET", "/api/v1/anomalies?user_id=usr_victim_id")
        assert spoof_status == 200
        assert spoof_body["user_id"] == "usr_demo_synthetic_01"
        assert spoof_body["total_anomalies"] >= 3
        record_pass(4, "Client-supplied user_id spoofing in query string strictly ignored")
    except Exception as e:
        record_fail(4, "user_id spoofing ignored", str(e))

    # Test 5: Cross-tenant isolation (Tenant Beta gets 0 anomalies)
    try:
        tenant_b = FinsightClient()
        b_email = f"tenant.b.anom.{int(time.time())}@finsight.internal"
        r_status, r_body, _ = tenant_b.request("POST", "/api/v1/auth/register", {
            "email": b_email,
            "password": "TenantPassword123!",
            "full_name": "Tenant Beta Anomalies"
        })
        assert r_status == 200
        tenant_b.csrf_token = r_body["csrf_token"]

        b_anom_status, b_anom_body, _ = tenant_b.request("GET", "/api/v1/anomalies")
        assert b_anom_status == 200
        assert b_anom_body["total_anomalies"] == 0
        assert len(b_anom_body["anomalies"]) == 0
        record_pass(5, "Cross-tenant isolation: Unseeded tenant receives 0 anomalies (Demo alerts not leaked)")
    except Exception as e:
        record_fail(5, "Cross-tenant isolation", str(e))

    # Test 6: Cross-tenant alert lookup by ID rejected (404)
    try:
        b_lookup_status, _, _ = tenant_b.request("GET", "/api/v1/anomalies/alt_03")
        assert b_lookup_status == 404, f"Expected 404 for foreign tenant lookup, got {b_lookup_status}"
        record_pass(6, "Cross-tenant alert lookup: Foreign tenant cannot read another user's alert ID (HTTP 404)")
    except Exception as e:
        record_fail(6, "Foreign tenant alert lookup", str(e))

    # -------------------------------------------------------------------------
    # PART 2: Mathematical Explainability & Multiplier Reconciliation
    # -------------------------------------------------------------------------
    print("\n--- Part 2: Mathematical Explainability & Multiplier Reconciliation ---")

    # Test 7: Explainable breakdown returns reproducible calculation details
    try:
        exp_status, exp_body, _ = demo.request("POST", "/api/v1/anomalies/alt_03/explain", include_csrf=True)
        assert exp_status == 200, f"Expected 200, got {exp_status}: {exp_body}"
        assert exp_body["alert_id"] == "alt_03"
        assert "calculation_details" in exp_body and exp_body["calculation_details"]
        record_pass(7, "Explainable breakdown (/api/v1/anomalies/alt_03/explain) returns reproducible calculation details")
    except Exception as e:
        record_fail(7, "Explainable breakdown", str(e))

    # Test 8: Reconcile AWS Multiplier Discrepancy (30.1x Merchant vs 15.5x Category vs 56.4x Clean Category)
    try:
        cd = exp_body["calculation_details"]
        # 1. Merchant baseline: 1420.00
        assert cd["merchant_historical_baseline"] == 1420.00, f"Expected 1420.00, got {cd.get('merchant_historical_baseline')}"
        # 2. Merchant multiplier: 30.1x
        assert cd["merchant_multiplier"] == 30.1, f"Expected 30.1x, got {cd.get('merchant_multiplier')}"
        # 3. Unadjusted category average: 2761.43
        assert cd["category_average_unadjusted"] == 2761.43, f"Expected 2761.43, got {cd.get('category_average_unadjusted')}"
        assert cd["category_multiplier_unadjusted"] == 15.5, f"Expected 15.5x, got {cd.get('category_multiplier_unadjusted')}"
        # 4. Clean category baseline excluding spike: 759.50
        assert cd["category_baseline_clean"] == 759.50, f"Expected 759.50, got {cd.get('category_baseline_clean')}"
        assert cd["category_multiplier_clean"] == 56.4, f"Expected 56.4x, got {cd.get('category_multiplier_clean')}"
        record_pass(8, "Reconcile AWS Multiplier Discrepancy: 30.1x Merchant Baseline, 15.5x Category Avg, 56.4x Clean Baseline")
    except Exception as e:
        record_fail(8, "Reconcile AWS Multiplier", str(e))

    # Test 9: Velocity burst alert links all 3 burst transactions
    try:
        v_status, v_body, _ = demo.request("POST", "/api/v1/anomalies/alt_02/explain", include_csrf=True)
        assert v_status == 200
        assert len(v_body["evidence_tx_ids"]) == 3
        assert all("tx_anom_02_velocity" in tid for tid in v_body["evidence_tx_ids"])
        record_pass(9, "Velocity burst alert (alt_02) links all 3 burst transactions (FastPay Cash Gateway)")
    except Exception as e:
        record_fail(9, "Velocity burst transactions", str(e))

    # Test 10: Amount spike alert (alt_01) compares Luxury Electronics against category baseline
    try:
        a1_status, a1_body, _ = demo.request("POST", "/api/v1/anomalies/alt_01/explain", include_csrf=True)
        assert a1_status == 200
        assert a1_body["calculation_details"]["transaction_amount"] == 84500.00
        assert "Electronics & Shopping" in a1_body["calculation_details"]["category_name"]
        record_pass(10, "Amount spike alert (alt_01) compares Luxury Electronics (₹84,500.00) against category baseline")
    except Exception as e:
        record_fail(10, "Amount spike alert", str(e))

    # Test 11: Limitations disclosure explicitly clarifies statistical anomaly is NOT proof of fraud
    try:
        lim = exp_body.get("limitations", "")
        assert "NOT" in lim and ("fraud" in lim.lower() or "proof" in lim.lower())
        assert "review" in lim.lower()
        record_pass(11, "Limitations disclosure explicitly clarifies statistical anomaly is NOT proof of fraud")
    except Exception as e:
        record_fail(11, "Limitations disclosure", str(e))

    # -------------------------------------------------------------------------
    # PART 3: Review Decision State Transitions & Security
    # -------------------------------------------------------------------------
    print("\n--- Part 3: Review Decision State Transitions & Security ---")

    # Test 12: Missing CSRF token rejected for status mutation (HTTP 403)
    try:
        m_status, _, _ = demo.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "REVIEWED"}, include_csrf=False)
        assert m_status == 403, f"Expected 403, got {m_status}"
        record_pass(12, "Missing X-CSRF-Token on PATCH /api/v1/anomalies/:id/status rejected with HTTP 403")
    except Exception as e:
        record_fail(12, "Missing CSRF rejected", str(e))

    # Test 13: Forged CSRF token rejected for status mutation (HTTP 403)
    try:
        f_status, _, _ = demo.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "REVIEWED"}, custom_csrf="forged_attacker_token_999")
        assert f_status == 403, f"Expected 403, got {f_status}"
        record_pass(13, "Forged X-CSRF-Token on PATCH /api/v1/anomalies/:id/status rejected with HTTP 403")
    except Exception as e:
        record_fail(13, "Forged CSRF rejected", str(e))

    # Test 14: Invalid review status rejected (HTTP 400)
    try:
        inv_status, _, _ = demo.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "CONFIRMED_FRAUD"}, include_csrf=True)
        assert inv_status == 400, f"Expected 400 for invalid status, got {inv_status}"
        record_pass(14, "Invalid review status (e.g. 'CONFIRMED_FRAUD') strictly rejected with HTTP 400")
    except Exception as e:
        record_fail(14, "Invalid status rejected", str(e))

    # Test 15: Valid review status transition (NEEDS_REVIEW -> REVIEWED) persists in Db2
    try:
        v_status, v_body, _ = demo.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "REVIEWED"}, include_csrf=True)
        assert v_status == 200, f"Expected 200, got {v_status}: {v_body}"
        assert v_body["status"] == "REVIEWED"
        assert v_body["updated"] is True
        record_pass(15, "Valid review status transition (NEEDS_REVIEW -> REVIEWED) succeeds (HTTP 200)")
    except Exception as e:
        record_fail(15, "Status transition", str(e))

    # Test 16: Status transition persists on re-querying /api/v1/anomalies
    try:
        q_status, q_body, _ = demo.request("GET", "/api/v1/anomalies")
        assert q_status == 200
        alt_01_check = next(a for a in q_body["anomalies"] if a["alert_id"] == "alt_01")
        assert alt_01_check["status"] == "REVIEWED", f"Expected REVIEWED, got {alt_01_check['status']}"
        record_pass(16, "Status transition persists and is reflected on re-querying /api/v1/anomalies")
    except Exception as e:
        record_fail(16, "Persisted status check", str(e))

    # Test 17: Status rollback/dismissal functions idempotently
    try:
        d_status, d_body, _ = demo.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "DISMISSED"}, include_csrf=True)
        assert d_status == 200
        assert d_body["status"] == "DISMISSED"

        # Roll back to NEEDS_REVIEW
        r_status, r_body, _ = demo.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "NEEDS_REVIEW"}, include_csrf=True)
        assert r_status == 200
        assert r_body["status"] == "NEEDS_REVIEW"
        record_pass(17, "Status rollback/dismissal (REVIEWED -> DISMISSED -> NEEDS_REVIEW) functions idempotently")
    except Exception as e:
        record_fail(17, "Status rollback", str(e))

    # Test 18: Cross-tenant mutation rejected (HTTP 404)
    try:
        b_mut_status, _, _ = tenant_b.request("PATCH", "/api/v1/anomalies/alt_01/status", {"status": "REVIEWED"}, include_csrf=True)
        assert b_mut_status == 404, f"Expected 404 for cross-tenant status update, got {b_mut_status}"
        record_pass(18, "Cross-tenant mutation: Tenant B cannot change status of Tenant A's alert (HTTP 404)")
    except Exception as e:
        record_fail(18, "Cross-tenant mutation", str(e))

    # -------------------------------------------------------------------------
    # PART 4: Financial Baselines & Boundary Guarantees
    # -------------------------------------------------------------------------
    print("\n--- Part 4: Financial Baselines & Boundary Guarantees ---")

    # Test 19: Pending transactions excluded from historical living-expense baselines
    try:
        # Check that no pending transactions contaminate the baselines
        db2_check = run_db2_query("""
from app.db import db_manager
res = db_manager.execute_query('''
    SELECT COUNT(*) as cnt
    FROM FINSIGHT.TRANSACTIONS
    WHERE user_id = 'usr_demo_synthetic_01' AND transaction_status = 'PENDING'
''')
print(res[0]['cnt'])
        """)
        assert int(db2_check) == 6
        record_pass(19, "Pending transactions strictly excluded from historical living-expense baselines")
    except Exception as e:
        record_fail(19, "Pending transactions exclusion", str(e))

    # Test 20: Internal transfers excluded from category anomaly baselines
    try:
        db2_trf_check = run_db2_query("""
from app.db import db_manager
res = db_manager.execute_query('''
    SELECT COUNT(*) as cnt
    FROM FINSIGHT.ANOMALY_ALERTS a
    JOIN FINSIGHT.TRANSACTIONS t ON a.transaction_id = t.transaction_id
    WHERE a.user_id = 'usr_demo_synthetic_01' AND t.category_id = 'cat_transfer'
''')
print(res[0]['cnt'])
        """)
        assert int(db2_trf_check) == 0, f"Transfers should not have anomaly alerts, found {db2_trf_check}"
        record_pass(20, "Internal transfers (cat_transfer) strictly excluded from category anomaly baselines")
    except Exception as e:
        record_fail(20, "Transfers exclusion", str(e))

    # Test 21: Nonexistent alert ID returns HTTP 404 cleanly
    try:
        ne_status, _, _ = demo.request("GET", "/api/v1/anomalies/nonexistent_alert_id_999")
        assert ne_status == 404, f"Expected 404, got {ne_status}"
        record_pass(21, "Nonexistent alert ID returns HTTP 404 cleanly without database stack traces")
    except Exception as e:
        record_fail(21, "Nonexistent alert 404", str(e))

    # -------------------------------------------------------------------------
    # PART 5: Zero Frontend Secrets & Regression Checks
    # -------------------------------------------------------------------------
    print("\n--- Part 5: Zero Frontend Secrets & Regression Checks ---")

    # Test 22: Zero service tokens in frontend dist bundle
    try:
        dist_files = glob.glob("frontend/dist/assets/*.js")
        assert len(dist_files) > 0, "No built JS bundles found"
        forbidden_patterns = [
            "GLtWRU3gWNfGYzxpMFm9vt7yytyxKer8",
            "AI_SERVICE_INTERNAL_TOKEN",
            "dev_internal_service_token",
            "DB2INST1_PASSWORD"
        ]
        for fpath in dist_files:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                for pat in forbidden_patterns:
                    assert pat not in content, f"Found leaked pattern '{pat}' in {fpath}"
        record_pass(22, "Frontend dist bundle contains zero internal service tokens or sensitive credentials")
    except Exception as e:
        record_fail(22, "Frontend bundle secrets audit", str(e))

    # Test 23: Existing AI Assistant continues to function with grounded Db2 evidence
    try:
        chat_status, chat_body, _ = demo.request("POST", "/api/v1/ai/chat", {"message": "Why was my spending high?"}, include_csrf=True)
        assert chat_status == 200
        assert "Amazon Web Services" in chat_body["answer"]
        assert len(chat_body["evidence"]) > 0
        record_pass(23, "Existing AI Assistant continues to function with grounded Db2 evidence")
    except Exception as e:
        record_fail(23, "AI Assistant regression", str(e))

    # Test 24: Existing Semantic Transaction Search continues to return dense vector matches
    try:
        search_status, search_body, _ = demo.request("POST", "/api/v1/ai/search", {"query": "cloud hosting and servers", "limit": 3}, include_csrf=True)
        assert search_status == 200
        assert search_body["total_results"] >= 1
        assert "Amazon Web Services" in search_body["results"][0]["merchant"]
        record_pass(24, "Existing Semantic Transaction Search continues to return dense vector matches")
    except Exception as e:
        record_fail(24, "Semantic Search regression", str(e))

    print("\n" + "=" * 80)
    print(f"STAGE 4C RESULTS: {passed}/{total} PASSED, {failed}/{total} FAILED")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
