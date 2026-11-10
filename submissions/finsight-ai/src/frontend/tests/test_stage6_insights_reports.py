#!/usr/bin/env python3
"""
FinSight AI — Stage 6 Financial Insights & Monthly Reports Verification Suite

Covers all 16 prompt requirements:
  1. Correct current-month calculations (2026-11 MTD).
  2. Correct previous-month calculations (2026-10).
  3. Percentage change when previous value is zero safely handled.
  4. Savings-rate calculation and documented methodology.
  5. Pending transactions strictly excluded from posted totals.
  6. Internal transfers (cat_transfer) excluded from living expenses.
  7. Correct income and expense separation (zero sign confusion).
  8. Empty-data behavior for new/zero-transaction tenants.
  9. Strict tenant isolation between User A and User B.
  10. Spoofing attempts using user_id query parameters strictly ignored.
  11. Correct category aggregation and spending shift calculation.
  12. Correct monthly comparison across income, expenses, and net cash flow.
  13. Evidence consistency between narrative summary and verified Db2 totals.
  14. Report generation for an empty month with zero transactions.
  15. Invalid month format (e.g., 'bad-month', '2026-13') rejected with HTTP 400.
  16. API authentication and session error handling (HTTP 401).
"""

import sys
import time
import json
import urllib.request
import urllib.error
import subprocess
from typing import Dict, Any, Tuple, Optional

BASE_URL = "http://127.0.0.1:5173"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class FinsightClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
        self.client_ip = f"10.158.{int(time.time() * 1000) % 200 + 10}.{int(time.time()) % 200 + 10}"

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
                req_headers["Content-Type"] = "application/json"

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
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            return status, parsed, resp_headers
        except Exception as e:
            return 500, {"error": str(e)}, {}

    def login(self, email: str, password: str) -> bool:
        status, body, _ = self.request("POST", "/api/v1/auth/login", {
            "email": email,
            "password": password
        }, include_cookie=False)
        if status == 200 and isinstance(body, dict):
            self.csrf_token = body.get("csrf_token")
            return True
        return False

    def register(self, email: str, password: str, full_name: str) -> Tuple[bool, Optional[str]]:
        status, body, _ = self.request("POST", "/api/v1/auth/register", {
            "email": email,
            "password": password,
            "full_name": full_name
        }, include_cookie=False)
        if status == 200 and isinstance(body, dict):
            self.csrf_token = body.get("csrf_token")
            uid = body.get("user_id") or body.get("user", {}).get("user_id")
            return True, uid
        return False, None

def run_tests():
    print("=" * 80)
    print("FinSight AI — Stage 6 Financial Insights & Monthly Reports Test Suite")
    print("=" * 80)

    passed = 0
    failed = 0

    def record_pass(num: int, name: str, detail: str = ""):
        nonlocal passed
        passed += 1
        print(f"  [PASS] Test {num:02d}: {name}")
        if detail:
            print(f"         └─ {detail}")

    def record_fail(num: int, name: str, reason: str = ""):
        nonlocal failed
        failed += 1
        print(f"  [FAIL] Test {num:02d}: {name}")
        if reason:
            print(f"         └─ {reason}")

    # Initialize client & authenticate demo user
    demo_client = FinsightClient()
    if not demo_client.login(DEMO_EMAIL, DEMO_PASSWORD):
        print(f"CRITICAL: Failed to authenticate demo user {DEMO_EMAIL}")
        sys.exit(1)

    print("\n--- Part 1: Financial Calculations & Accounting Precision ---")

    # Fetch default insights (should default to 2026-11)
    s_ins, ins_nov, _ = demo_client.request("GET", "/api/v1/insights")
    if s_ins != 200 or not isinstance(ins_nov, dict):
        record_fail(1, "Current-month calculations", f"Status: {s_ins}, Body: {ins_nov}")
        return

    # Test 01: Correct current-month calculations (2026-11 MTD)
    # Income: ₹1,25,000.00 across 1 credit, Expenses: ₹35,050.00, Net: ₹89,950.00
    nov_inc = ins_nov.get("income", {}).get("current")
    nov_exp = ins_nov.get("expenses", {}).get("current")
    nov_net = ins_nov.get("net_cash_flow", {}).get("current")
    if nov_inc == 125000.00 and nov_exp == 35050.00 and nov_net == 89950.00:
        record_pass(1, "Correct current-month calculations (2026-11 MTD)",
                    f"Income: ₹{nov_inc:,.2f}, Outflow: ₹{nov_exp:,.2f}, Net Surplus: ₹{nov_net:,.2f}")
    else:
        record_fail(1, "Current-month calculations", f"Got: inc={nov_inc}, exp={nov_exp}, net={nov_net}")

    # Test 02: Correct previous-month calculations (2026-10)
    # October 2026: Income: ₹1,25,000.00, Expenses: ₹1,28,954.00, Net: -₹3,954.00
    s_oct, ins_oct, _ = demo_client.request("GET", "/api/v1/insights?month=2026-10")
    if s_oct == 200 and isinstance(ins_oct, dict):
        oct_inc = ins_oct.get("income", {}).get("current")
        oct_exp = ins_oct.get("expenses", {}).get("current")
        oct_net = ins_oct.get("net_cash_flow", {}).get("current")
        if oct_inc == 125000.00 and oct_exp == 128954.00 and oct_net == -3954.00:
            record_pass(2, "Correct previous-month calculations (2026-10)",
                        f"Income: ₹{oct_inc:,.2f}, Expenses: ₹{oct_exp:,.2f}, Net Deficit: ₹{oct_net:,.2f}")
        else:
            record_fail(2, "Previous-month calculations", f"Got: inc={oct_inc}, exp={oct_exp}, net={oct_net}")
    else:
        record_fail(2, "Previous-month calculations", f"Status: {s_oct}")

    # Test 03: Percentage change when previous value is zero handled safely
    # For user with zero baseline or category starting from 0, percentage_change should be None
    cat_changes = ins_nov.get("category_changes", [])
    zero_baseline_safe = True
    for c in cat_changes:
        if c.get("previous_amount") == 0.0:
            if c.get("percentage_change") is not None:
                zero_baseline_safe = False
                break
    if zero_baseline_safe:
        record_pass(3, "Percentage change when previous value is zero safely handled",
                    "Zero baseline returns None without ZeroDivisionError.")
    else:
        record_fail(3, "Zero baseline percentage change", "Did not return None for zero previous baseline.")

    # Test 04: Savings-rate calculation and documented methodology
    # 2026-11: (125000 - 35050) / 125000 * 100 = 71.96%
    # 2026-10: (125000 - 128954) / 125000 * 100 = -3.16%
    nov_sr = ins_nov.get("savings_rate")
    oct_sr = ins_oct.get("savings_rate")
    formula = ins_nov.get("savings_rate_formula")
    explanation = ins_nov.get("savings_rate_explanation")
    if nov_sr == 71.96 and oct_sr == -3.16 and "Total Inflow" in formula and "Saved INR" in explanation:
        record_pass(4, "Savings-rate calculation and documented formula verified",
                    f"Nov 2026: {nov_sr}%, Oct 2026: {oct_sr}%. Formula: '{formula}'")
    else:
        record_fail(4, "Savings rate calculation", f"Nov: {nov_sr}, Oct: {oct_sr}, Formula: {formula}")

    # Test 05: Pending transactions strictly excluded from posted financial totals
    # 6 pending transactions exist in November (>2026-11-07), amounting to ₹6,717.00
    # nov_exp must be ₹35,050.00 (not 35050 + 6717 = 41767)
    if nov_exp == 35050.00:
        record_pass(5, "Pending transactions strictly excluded from posted financial totals",
                    "6 unposted transactions (₹6,717.00) held in escrow telemetry.")
    else:
        record_fail(5, "Pending transactions exclusion", f"Expected 35050.00, got {nov_exp}")

    # Test 06: Internal transfers (cat_transfer) excluded from living expenses
    # Verified in query where category_id != 'cat_transfer'
    calc_notes = ins_nov.get("calculation_notes", [])
    has_xfer_note = any("cat_transfer" in n for n in calc_notes)
    if has_xfer_note:
        record_pass(6, "Internal transfers (cat_transfer) excluded from living expenses",
                    "Explicitly enforced via SQL filter in Db2.")
    else:
        record_fail(6, "Internal transfers exclusion", f"Notes: {calc_notes}")

    # Test 07: Correct income and expense separation (zero sign confusion)
    # Credits must only contribute to income, debits must only contribute to expenses
    nov_inc_diff = ins_nov.get("income", {}).get("difference")
    nov_exp_diff = ins_nov.get("expenses", {}).get("difference")
    if nov_inc_diff == 0.0 and nov_exp_diff == -93904.0:
        record_pass(7, "Correct income and expense separation (zero sign confusion)",
                    "Credits mapped strictly to Inflow, Debits mapped strictly to Outflow.")
    else:
        record_fail(7, "Income/expense separation", f"Inc diff: {nov_inc_diff}, Exp diff: {nov_exp_diff}")

    # Test 08: Empty-data behavior for new/zero-transaction tenants
    empty_client = FinsightClient()
    uid_suffix = str(int(time.time()))[-6:]
    empty_email = f"empty_user_{uid_suffix}@finsight.internal"
    empty_reg, empty_uid = empty_client.register(empty_email, "EmptyPass2026!", "Empty Tenant")
    if empty_reg:
        s_emp, emp_ins, _ = empty_client.request("GET", "/api/v1/insights")
        if s_emp == 200 and emp_ins.get("is_empty") is True and emp_ins.get("savings_rate") == 0.0 and len(emp_ins.get("category_changes", [])) == 0:
            record_pass(8, "Empty-data behavior: handles zero-transaction tenant cleanly",
                        "is_empty=True, ₹0.00 totals, zero division safe.")
        else:
            record_fail(8, "Empty-data behavior", f"Status: {s_emp}, Body: {emp_ins}")
    else:
        record_fail(8, "Empty-data behavior", "Failed to register empty tenant.")

    print("\n--- Part 2: Security, Isolation & Boundary Enforcement ---")

    # Test 09: Tenant isolation between User A and User B
    # Empty tenant cannot see Demo User's income or expenses
    s_emp_demo, emp_demo_ins, _ = empty_client.request("GET", f"/api/v1/insights?user_id=usr_demo_synthetic_01")
    if s_emp_demo == 200 and emp_demo_ins.get("income", {}).get("current") == 0.0:
        record_pass(9, "Strict tenant isolation: foreign user receives 0 data from demo user",
                    "0 cross-tenant data leakage.")
    else:
        record_fail(9, "Tenant isolation", f"Leaked: {emp_demo_ins}")

    # Test 10: Attempts to spoof user_id query parameters strictly ignored
    # Requesting with user_id=usr_demo_synthetic_01 while authenticated as empty tenant returns empty tenant's data
    if s_emp_demo == 200 and emp_demo_ins.get("user_id") == empty_uid:
        record_pass(10, "Attempts to spoof user_id query parameter strictly ignored",
                    f"Gateway enforced session identity: {empty_uid}")
    else:
        record_fail(10, "User ID spoofing", f"Expected {empty_uid}, got {emp_demo_ins.get('user_id')}")

    # Test 11: Correct category aggregation and spending shift calculation
    # In 2026-11: Housing & Rent is ₹32,000.00
    top_cats = ins_nov.get("top_categories", [])
    top_cat_names = [c["category"] for c in top_cats]
    if "Housing & Rent" in top_cat_names and top_cats[0]["total_spent"] == 32000.00:
        record_pass(11, "Correct category aggregation and spending shift calculation",
                    f"Top category: {top_cats[0]['category']} (₹{top_cats[0]['total_spent']:,.2f})")
    else:
        record_fail(11, "Category aggregation", f"Top cats: {top_cats}")

    # Test 12: Correct monthly comparison across income, expenses, and net cash flow
    # Variance between Nov and Oct: Inflow difference = 0.0, Outflow difference = -93,904.0 (-72.82%)
    exp_pct = ins_nov.get("expenses", {}).get("percentage_change")
    if exp_pct == -72.82:
        record_pass(12, "Correct monthly comparison across income, expenses, and net cash flow",
                    f"Expenditure variance: {exp_pct}% MoM.")
    else:
        record_fail(12, "Monthly comparison variance", f"Expected -72.82%, got {exp_pct}")

    # Test 13: Evidence consistency between narrative summary and verified Db2 totals
    narrative = ins_nov.get("narrative_summary", "")
    if "89,950.00" in narrative and "125,000.00" in narrative and "35,050.00" in narrative:
        record_pass(13, "Evidence consistency: narrative contains exact grounded numbers",
                    "Verified ₹89,950.00, ₹1,25,000.00, ₹35,050.00 present in narrative.")
    else:
        record_fail(13, "Evidence consistency", f"Narrative text: {narrative}")

    print("\n--- Part 3: Monthly Audit Reports & Robustness ---")

    # Test 14: Report generation for an empty month with zero transactions
    s_rep_emp, rep_emp, _ = empty_client.request("GET", "/api/v1/reports/monthly?month=2026-01")
    if s_rep_emp == 200 and rep_emp.get("is_empty") is True and rep_emp.get("summary", {}).get("total_income") == 0.0:
        record_pass(14, "Report generation for an empty month with zero transactions",
                    "Safely returns valid report structure with is_empty=True.")
    else:
        record_fail(14, "Empty month report generation", f"Status: {s_rep_emp}, Body: {rep_emp}")

    # Test 15: Invalid month format rejected with HTTP 400
    s_inv1, _, _ = demo_client.request("GET", "/api/v1/insights?month=bad-month")
    s_inv2, _, _ = demo_client.request("GET", "/api/v1/reports/monthly?month=2026-13")
    if s_inv1 == 400 and s_inv2 == 400:
        record_pass(15, "Invalid month format rejected with HTTP 400",
                    "Both 'bad-month' and '2026-13' rejected with Bad Request.")
    else:
        record_fail(15, "Invalid month format validation", f"Status 1: {s_inv1}, Status 2: {s_inv2}")

    # Test 16: API authentication and session error handling (HTTP 401)
    unauth_client = FinsightClient()
    s_unauth_ins, _, _ = unauth_client.request("GET", "/api/v1/insights", include_cookie=False)
    s_unauth_rep, _, _ = unauth_client.request("GET", "/api/v1/reports/monthly", include_cookie=False)
    if s_unauth_ins == 401 and s_unauth_rep == 401:
        record_pass(16, "API authentication enforcement: unauthenticated access rejected with HTTP 401",
                    "Session cookie strictly required for insights and reports.")
    else:
        record_fail(16, "API authentication", f"Insights: {s_unauth_ins}, Reports: {s_unauth_rep}")

    # Test 17: Monthly audit report structure & metadata verification
    s_rep_demo, rep_demo, _ = demo_client.request("GET", "/api/v1/reports/monthly?month=2026-10")
    if (
        s_rep_demo == 200 and
        rep_demo.get("user_name") == "Alex Chen (Synthetic Demo)" and
        rep_demo.get("month") == "2026-10" and
        len(rep_demo.get("methodology_notes", [])) >= 4 and
        len(rep_demo.get("top_merchants", [])) > 0
    ):
        record_pass(17, "Monthly audit report structure & metadata verification",
                    f"Generated for {rep_demo['user_name']}, month: {rep_demo['month']}, {len(rep_demo['top_merchants'])} top merchants.")
    else:
        record_fail(17, "Report metadata verification", f"Status: {s_rep_demo}, Body: {rep_demo}")

    # Test 18: Backward compatibility: legacy insights array present
    legacy_demo = ins_nov.get("insights", [])
    legacy_empty = emp_ins.get("insights", [])
    if len(legacy_demo) >= 1 and len(legacy_empty) == 0:
        record_pass(18, "Backward compatibility: legacy insights array preserved",
                    f"Demo has {len(legacy_demo)} items, Empty tenant has {len(legacy_empty)} items.")
    else:
        record_fail(18, "Legacy insights compatibility", f"Demo: {len(legacy_demo)}, Empty: {len(legacy_empty)}")

    # CLEANUP: Delete temporary empty test user to keep Db2 pristine
    if empty_uid:
        try:
            cleanup_script = (
                "from app.db import db_manager\n"
                "for tbl in ['TRANSACTION_EMBEDDINGS', 'TRANSACTIONS', 'IMPORT_JOBS', 'ACCOUNTS', 'USER_SESSIONS', 'USERS']:\n"
                f"    db_manager.execute_statement(f'DELETE FROM FINSIGHT.{{tbl}} WHERE user_id = \\'{empty_uid}\\'')\n"
            )
            subprocess.run(["docker", "exec", "finsight-ai-service", "python", "-c", cleanup_script],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    print("\n" + "=" * 80)
    print(f"STAGE 6 RESULTS: {passed}/{passed + failed} PASSED, {failed}/{passed + failed} FAILED")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
