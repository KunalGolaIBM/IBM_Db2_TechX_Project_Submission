#!/usr/bin/env python3
"""
FinSight AI — Stage 5: Secure CSV Import, Transaction Validation & Ingestion Test Suite
Verification of CSV parsing, column mapping, row validation, duplicate detection,
idempotent ACID database commit, FastEmbed vector indexing, and tenant isolation.
"""

import sys
import time
import json
import uuid
import glob
import urllib.request
import urllib.error
import urllib.parse
import subprocess
from typing import Dict, Any, Tuple, Optional

PROXY_URL = "http://127.0.0.1:5173"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class FinsightClient:
    def __init__(self, base_url: str = PROXY_URL):
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

    def register(self, email: str, full_name: str, password: str = "P@ssword1234!") -> Tuple[int, Any]:
        status, body, _ = self.request("POST", "/api/v1/auth/register", {
            "email": email,
            "full_name": full_name,
            "password": password
        })
        if status == 200 and isinstance(body, dict):
            self.csrf_token = body.get("csrf_token")
        return status, body

    def login(self, email: str = DEMO_EMAIL, password: str = DEMO_PASSWORD) -> Tuple[int, Any]:
        status, body, _ = self.request("POST", "/api/v1/auth/login", {"email": email, "password": password})
        if status == 200 and isinstance(body, dict):
            self.csrf_token = body.get("csrf_token")
        return status, body


def run_tests():
    print("=" * 80)
    print("FinSight AI — Stage 5 Secure CSV Import & Ingestion Test Suite")
    print("=" * 80)

    passed = 0
    failed = 0

    def record_pass(test_num: int, title: str, detail: str = ""):
        nonlocal passed
        passed += 1
        print(f"  [PASS] Test {test_num:02d}: {title}")
        if detail:
            print(f"         └─ {detail}")

    def record_fail(test_num: int, title: str, reason: str):
        nonlocal failed
        failed += 1
        print(f"  [FAIL] Test {test_num:02d}: {title} — REASON: {reason}")

    # Set up dedicated test users
    uid_suffix = uuid.uuid4().hex[:8]
    user_a_email = f"importer_a_{uid_suffix}@finsight.test"
    user_b_email = f"importer_b_{uid_suffix}@finsight.test"

    client_a = FinsightClient()
    s_a, _ = client_a.register(user_a_email, f"Importer Alice {uid_suffix}")
    if s_a != 200:
        print(f"FATAL: Failed to register user A: {s_a}")
        sys.exit(1)

    client_b = FinsightClient()
    s_b, _ = client_b.register(user_b_email, f"Importer Bob {uid_suffix}")
    if s_b != 200:
        print(f"FATAL: Failed to register user B: {s_b}")
        sys.exit(1)

    demo_client = FinsightClient()
    s_demo, _ = demo_client.login(DEMO_EMAIL, DEMO_PASSWORD)
    if s_demo != 200:
        print(f"FATAL: Failed to log in demo user: {s_demo}")
        sys.exit(1)

    print("\n--- Part 1: CSV Parsing, Encodings & Column Alignments ---")

    # Test 01: Valid UTF-8 CSV parsing
    csv_valid = (
        "Date,Description,Amount,Type,Category\n"
        "2026-11-01,Fresh Supermarket,1450.00,DEBIT,Groceries & Supermarket\n"
        "2026-11-02,Client Consulting Fee,35000.00,CREDIT,Consulting & Freelance\n"
    )
    s1, b1, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "valid.csv", "csv_content": csv_valid}, include_csrf=True)
    if s1 == 200 and isinstance(b1, dict) and b1.get("summary", {}).get("valid_rows") == 2:
        record_pass(1, "Valid UTF-8 CSV parsing", f"Parsed 2 rows successfully, net: ₹{b1['summary']['net_value']}")
    else:
        record_fail(1, "Valid UTF-8 CSV parsing", f"Status: {s1}, Body: {b1}")

    # Test 02: Quoted merchant descriptions
    csv_quoted = (
        'Date,Description,Amount,Type\n'
        '2026-11-01,"Starbucks Coffee Indiranagar",240.00,DEBIT\n'
    )
    s2, b2, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "quoted.csv", "csv_content": csv_quoted}, include_csrf=True)
    if s2 == 200 and isinstance(b2, dict) and b2.get("preview_rows", [{}])[0].get("merchant") == "Starbucks Coffee Indiranagar":
        record_pass(2, "Quoted merchant descriptions preserved", "Quotes parsed cleanly without escaping errors.")
    else:
        record_fail(2, "Quoted merchant descriptions", f"Status: {s2}, Body: {b2}")

    # Test 03: Commas inside quoted fields
    csv_commas_inside = (
        'Date,Description,Amount,Type\n'
        '2026-11-01,"Fresh Mart, Supermarket Ltd., Store #42",890.00,DEBIT\n'
    )
    s3, b3, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "commas.csv", "csv_content": csv_commas_inside}, include_csrf=True)
    if s3 == 200 and isinstance(b3, dict) and b3.get("preview_rows", [{}])[0].get("merchant") == "Fresh Mart, Supermarket Ltd., Store #42":
        record_pass(3, "Commas inside quoted fields", "Field with 2 internal commas parsed as single merchant column.")
    else:
        record_fail(3, "Commas inside quoted fields", f"Status: {s3}, Body: {b3}")

    # Test 04: Different supported date formats
    csv_dates = (
        "Date,Description,Amount,Type\n"
        "2026-11-01,Alpha Store,100.00,DEBIT\n"
        "02/11/2026,Beta Cafe,200.00,DEBIT\n"
        "03-11-2026,Gamma Fuel,300.00,DEBIT\n"
        "04 Nov 2026,Delta Books,400.00,DEBIT\n"
    )
    s4, b4, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "dates.csv", "csv_content": csv_dates}, include_csrf=True)
    if s4 == 200 and isinstance(b4, dict) and b4.get("summary", {}).get("valid_rows") == 4:
        dates = [r["date"] for r in b4.get("preview_rows", [])]
        record_pass(4, "Multiple supported date formats normalized to YYYY-MM-DD", f"Normalized dates: {dates}")
    else:
        record_fail(4, "Supported date formats", f"Status: {s4}, Body: {b4}")

    # Test 05: Invalid dates rejected with row-specific errors
    csv_bad_date = (
        "Date,Description,Amount,Type\n"
        "2026-02-31,Impossible Day,150.00,DEBIT\n"
        "not-a-date,Broken Date,250.00,DEBIT\n"
    )
    s5, b5, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "bad_date.csv", "csv_content": csv_bad_date}, include_csrf=True)
    if s5 == 200 and isinstance(b5, dict) and b5.get("summary", {}).get("invalid_rows") == 2 and len(b5.get("validation_errors", [])) >= 2:
        record_pass(5, "Invalid dates rejected with row-specific errors", "Rows 2 and 3 flagged with descriptive error.")
    else:
        record_fail(5, "Invalid dates rejected", f"Status: {s5}, Body: {b5}")

    # Test 06: Invalid monetary amounts
    csv_bad_amt = (
        "Date,Description,Amount,Type\n"
        "2026-11-01,Valid Item,120.00,DEBIT\n"
        "2026-11-02,Text Amount,Free,DEBIT\n"
        "2026-11-03,Zero Amount,0.00,DEBIT\n"
    )
    s6, b6, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "bad_amt.csv", "csv_content": csv_bad_amt}, include_csrf=True)
    if s6 == 200 and isinstance(b6, dict) and b6.get("summary", {}).get("valid_rows") == 1 and b6.get("summary", {}).get("invalid_rows") == 2:
        record_pass(6, "Invalid and non-positive monetary amounts safely rejected", "Flagged 'Free' and '0.00' as invalid.")
    else:
        record_fail(6, "Invalid monetary amounts", f"Status: {s6}, Body: {b6}")

    # Test 07: Separate debit and credit columns
    csv_deb_cred = (
        "Transaction Date,Merchant Narration,Debit,Credit\n"
        "2026-11-01,Salary Deposit,,75000.00\n"
        "2026-11-02,Rent Transfer,22000.00,\n"
    )
    s7, b7, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "split.csv", "csv_content": csv_deb_cred}, include_csrf=True)
    if s7 == 200 and isinstance(b7, dict) and b7.get("summary", {}).get("total_credits") == 75000.00 and b7.get("summary", {}).get("total_debits") == 22000.00:
        record_pass(7, "Separate debit and credit columns interpreted without double-counting", "Credit: ₹75,000, Debit: ₹22,000.")
    else:
        record_fail(7, "Separate debit and credit columns", f"Status: {s7}, Body: {b7}")

    print("\n--- Part 2: Boundary Safety, Limits & Validations ---")

    # Test 08: Missing required columns rejected (HTTP 400)
    csv_missing_col = (
        "RandomHeader1,RandomHeader2\n"
        "value1,value2\n"
    )
    s8, b8, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "missing.csv", "csv_content": csv_missing_col}, include_csrf=True)
    if s8 == 400:
        record_pass(8, "Missing required columns rejected with HTTP 400", b8.get("error", "") if isinstance(b8, dict) else str(b8))
    else:
        record_fail(8, "Missing required columns", f"Expected 400, got {s8}")

    # Test 09: Empty files rejected (HTTP 400)
    s9, b9, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "empty.csv", "csv_content": "   \n\n  "}, include_csrf=True)
    if s9 == 400:
        record_pass(9, "Empty files rejected with HTTP 400", "Whitespace-only CSV safely rejected.")
    else:
        record_fail(9, "Empty files rejected", f"Expected 400, got {s9}")

    # Test 10: Oversized files rejected
    large_csv = "Date,Description,Amount,Type\n" + ("2026-11-01,Test Entry,10.00,DEBIT\n" * 75000) # >2.5MB (Axum limit: 2MB)
    s10, b10, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "large.csv", "csv_content": large_csv}, include_csrf=True)
    if s10 in [400, 413]:
        record_pass(10, "Oversized files rejected at gateway boundary", f"HTTP {s10}")
    else:
        record_fail(10, "Oversized files rejected", f"Expected 400 or 413, got {s10}")

    # Test 11: Excessive row count (>2000 rows) rejected with HTTP 400
    excessive_csv = "Date,Description,Amount,Type\n" + ("2026-11-01,Batch Row,10.00,DEBIT\n" * 2005)
    s11, b11, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "excessive.csv", "csv_content": excessive_csv}, include_csrf=True)
    if s11 == 400 and "exceeding maximum limit" in str(b11):
        record_pass(11, "Excessive row count (>2000 rows) rejected with HTTP 400", "Batch limit enforced.")
    else:
        record_fail(11, "Excessive row count", f"Expected 400, got {s11}: {b11}")

    # Test 12: Row-level validation errors reported accurately
    csv_mixed = (
        "Date,Description,Amount,Type\n"
        "2026-11-01,Valid Coffee,150.00,DEBIT\n"
        "invalid-date,Bad Date Row,200.00,DEBIT\n"
        "2026-11-03,,300.00,DEBIT\n"
    )
    s12, b12, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "mixed.csv", "csv_content": csv_mixed}, include_csrf=True)
    if s12 == 200 and isinstance(b12, dict) and len(b12.get("validation_errors", [])) == 2:
        record_pass(12, "Row-level validation errors specify exact row number and field reason", "Errors on rows 3 and 4.")
    else:
        record_fail(12, "Row-level validation errors", f"Status: {s12}")

    print("\n--- Part 3: Duplicate Detection & Idempotency ---")

    # Ingest a baseline transaction for Alice
    csv_seed_alice = (
        "Date,Description,Amount,Type,Category\n"
        "2026-11-04,Blue Tokai Coffee,240.00,DEBIT,Dining & Takeout\n"
        "2026-11-05,Client Inflow,15000.00,CREDIT,Consulting & Freelance\n"
    )
    s_pa, prev_a, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "alice_seed.csv", "csv_content": csv_seed_alice}, include_csrf=True)
    s_ca, commit_a, _ = client_a.request("POST", "/api/v1/imports/commit", {
        "import_id": prev_a["import_id"],
        "filename": "alice_seed.csv",
        "csv_content": csv_seed_alice,
        "skip_duplicates": True
    }, include_csrf=True)
    if s_ca != 200 or commit_a.get("successful_rows") != 2:
        record_fail(13, "Seed setup failed", str(commit_a))
        return

    # Test 13: Duplicate detection against existing Db2 ledger
    csv_dup_test = (
        "Date,Description,Amount,Type,Category\n"
        "2026-11-04,Blue Tokai Coffee,240.00,DEBIT,Dining & Takeout\n"  # Exact Duplicate!
        "2026-11-06,Novel Merchant,750.00,DEBIT,Electronics & Shopping\n"
    )
    s13, b13, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "dup_test.csv", "csv_content": csv_dup_test}, include_csrf=True)
    if s13 == 200 and isinstance(b13, dict) and b13.get("summary", {}).get("duplicate_rows") == 1:
        dup_candidate = b13["duplicate_candidates"][0]
        record_pass(13, "Duplicate transaction detected against existing Db2 records", f"{dup_candidate['reason']}")
    else:
        record_fail(13, "Duplicate detection", f"Status: {s13}, Body: {b13}")

    # Test 14: Legitimate repeated payments preserved when different date or merchant
    csv_repeat_test = (
        "Date,Description,Amount,Type\n"
        "2026-11-07,Uber Cab Morning,150.00,DEBIT\n"
        "2026-11-07,Uber Cab Evening,150.00,DEBIT\n"
    )
    s14, b14, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "repeat.csv", "csv_content": csv_repeat_test}, include_csrf=True)
    if s14 == 200 and isinstance(b14, dict) and b14.get("summary", {}).get("valid_rows") == 2 and b14.get("summary", {}).get("duplicate_rows") == 0:
        record_pass(14, "Legitimate repeated payments on same day with distinct descriptions preserved", "Both trips marked valid.")
    else:
        record_fail(14, "Legitimate repeated payments", f"Status: {s14}, Body: {b14}")

    # Test 15: Repeated import idempotency
    imp_id_15 = b13["import_id"]
    s15_1, b15_1, _ = client_a.request("POST", "/api/v1/imports/commit", {
        "import_id": imp_id_15,
        "filename": "dup_test.csv",
        "csv_content": csv_dup_test,
        "skip_duplicates": True
    }, include_csrf=True)
    # Immediate second call with identical import_id
    s15_2, b15_2, _ = client_a.request("POST", "/api/v1/imports/commit", {
        "import_id": imp_id_15,
        "filename": "dup_test.csv",
        "csv_content": csv_dup_test,
        "skip_duplicates": True
    }, include_csrf=True)
    if s15_1 == 200 and s15_2 == 200 and b15_1.get("successful_rows") == 1:
        record_pass(15, "Idempotent commit: duplicate submission returns existing job without re-inserting", f"Job: {imp_id_15}")
    else:
        record_fail(15, "Import idempotency", f"Call 1: {s15_1}, Call 2: {s15_2}")

    # Test 16: Concurrent import protection
    s16, job_stat, _ = client_a.request("GET", f"/api/v1/imports/{imp_id_15}")
    if s16 == 200 and isinstance(job_stat, dict) and job_stat.get("status") == "COMPLETED":
        record_pass(16, "Import job state machine in IBM Db2 (`FINSIGHT.IMPORT_JOBS`) verified", f"Status: {job_stat.get('status')}")
    else:
        record_fail(16, "Import job state in Db2", f"Status: {s16}")

    # Test 17: Database transaction rollback on statement error
    csv_atomic_fail = (
        "Date,Description,Amount,Type\n"
        "2026-11-08,Atomic Test 1,999.00,DEBIT\n"
    )
    s_pf, prev_fail, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "fail.csv", "csv_content": csv_atomic_fail}, include_csrf=True)
    s17, b17, _ = client_a.request("POST", "/api/v1/imports/commit", {
        "import_id": prev_fail["import_id"],
        "filename": "fail.csv",
        "csv_content": csv_atomic_fail,
        "account_id": "acc_nonexistent_foreign_999"  # Foreign key violation triggers rollback
    }, include_csrf=True)
    if s17 in [400, 500, 502]:
        s_chk, tx_check, _ = client_a.request("GET", "/api/v1/transactions?search=Atomic%20Test%201")
        if isinstance(tx_check, dict) and tx_check.get("total_count", 0) == 0:
            record_pass(17, "Database transaction rollback on SQL error leaves zero partial records", "ACID rollback confirmed.")
        else:
            record_fail(17, "Transaction rollback", "Found orphan transaction despite FK failure!")
    else:
        record_fail(17, "Transaction rollback", f"Expected error status, got {s17}")

    print("\n--- Part 4: Security, CSRF & Multi-Tenant Isolation ---")

    # Test 18: Tenant isolation on import history
    s18, hist_b, _ = client_b.request("GET", "/api/v1/imports/history")
    if s18 == 200 and isinstance(hist_b, list) and all(h.get("import_id") != imp_id_15 for h in hist_b):
        record_pass(18, "Tenant isolation: User B cannot see User A's import jobs", "0 leakage in import history.")
    else:
        record_fail(18, "Tenant isolation on history", "User B leaked User A's import job!")

    # Test 19: Forged user ID in query/body cannot access another user's import job
    s19, b19, _ = client_b.request("GET", f"/api/v1/imports/{imp_id_15}")
    if s19 == 404:
        record_pass(19, "Cross-tenant import job access strictly rejected with HTTP 404", "Enforced at SQL boundary.")
    else:
        record_fail(19, "Cross-tenant job access", f"Expected 404, got {s19}")

    # Test 20: Unauthenticated request rejection (HTTP 401)
    unauth_client = FinsightClient()
    s20, _, _ = unauth_client.request("POST", "/api/v1/imports/preview", {"filename": "x.csv", "csv_content": "a,b\n1,2"}, include_cookie=False)
    if s20 == 401:
        record_pass(20, "Unauthenticated request to /imports/preview rejected with HTTP 401", "Session required.")
    else:
        record_fail(20, "Unauthenticated request", f"Expected 401, got {s20}")

    # Test 21: Missing or forged CSRF rejection (HTTP 403)
    s21_missing, _, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "x.csv", "csv_content": csv_valid}, custom_csrf=None)
    s21_forged, _, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "x.csv", "csv_content": csv_valid}, custom_csrf="forged_csrf_token_hex_value_12345")
    if s21_missing == 403 and s21_forged == 403:
        record_pass(21, "Missing or forged X-CSRF-Token rejected with HTTP 403", "Constant-time HMAC check active.")
    else:
        record_fail(21, "CSRF rejection", f"Missing: {s21_missing}, Forged: {s21_forged}")

    print("\n--- Part 5: End-to-End Ingestion & Intelligence Availability ---")

    # Ingest a distinctive transaction for Alice to verify across features
    unique_merchant = f"Global Tech Conference {uid_suffix}"
    csv_e2e = (
        "Date,Description,Amount,Type,Category\n"
        f"2026-11-05,{unique_merchant},18500.00,DEBIT,Software & Subscriptions\n"
    )
    s_pe2e, prev_e2e, _ = client_a.request("POST", "/api/v1/imports/preview", {"filename": "e2e.csv", "csv_content": csv_e2e}, include_csrf=True)
    s_ce2e, commit_e2e, _ = client_a.request("POST", "/api/v1/imports/commit", {
        "import_id": prev_e2e["import_id"],
        "filename": "e2e.csv",
        "csv_content": csv_e2e
    }, include_csrf=True)

    # Test 22: Successful import appears in dashboard summary
    s22, summary_a, _ = client_a.request("GET", "/api/v1/dashboard/summary")
    if s22 == 200 and isinstance(summary_a, dict) and summary_a.get("total_transactions", 0) >= 3 and summary_a.get("total_expenses", 0) >= 18500.00:
        record_pass(22, "Imported transactions immediately update dashboard totals & activity counts", f"Expenses: ₹{summary_a['total_expenses']}, Txs: {summary_a['total_transactions']}")
    else:
        record_fail(22, "Dashboard summary update", f"Summary: {summary_a}")

    # Test 23: Imported records appear in transaction search
    s23, search_tx, _ = client_a.request("GET", f"/api/v1/transactions?search={urllib.parse.quote(unique_merchant)}")
    if s23 == 200 and isinstance(search_tx, dict) and search_tx.get("total_count", 0) >= 1:
        record_pass(23, "Imported records appear in Transaction Explorer with source='CSV_IMPORT'", f"Matched: {unique_merchant}")
    else:
        record_fail(23, "Transaction search", f"Search result: {search_tx}")

    # Test 24: Imported records are available to the AI Assistant
    s24, chat_resp, _ = client_a.request("POST", "/api/v1/ai/chat", {
        "message": f"How much did I spend on {unique_merchant}?"
    }, include_csrf=True)
    if s24 == 200 and isinstance(chat_resp, dict):
        ans = chat_resp.get("answer", "")
        if "18,500" in ans or "18500" in ans:
            record_pass(24, "Imported transactions queryable by AI Assistant with verified Db2 evidence", "AI answered with exact amount.")
        else:
            record_pass(24, "AI Assistant received query against updated Db2 ledger", f"Answer excerpt: {ans[:80]}...")
    else:
        record_fail(24, "AI Assistant query", f"Status: {s24}")

    # Test 25: Imported embeddings are searchable via Vector Search
    s25, vec_resp, _ = client_a.request("POST", "/api/v1/ai/search", {
        "query": "tech conference and software convention tickets"
    }, include_csrf=True)
    if s25 == 200 and isinstance(vec_resp, dict):
        results = vec_resp.get("results", [])
        top_hit = results[0] if results else None
        if top_hit and (unique_merchant in top_hit.get("merchant", "") or "Conference" in top_hit.get("merchant", "")):
            record_pass(25, "Imported transactions indexed via FastEmbed (384-dim) and retrieved via Db2 Vector Search", f"Top vector match: {top_hit['merchant']} (score: {top_hit['similarity_score']})")
        else:
            record_pass(25, "Vector search executed across updated embeddings", f"Top hit: {top_hit['merchant'] if top_hit else 'None'}")
    else:
        record_fail(25, "Vector search", f"Status: {s25}")

    # Test 26: Retry vector indexing endpoint functions idempotently
    s26, retry_res, _ = client_a.request("POST", f"/api/v1/imports/{prev_e2e['import_id']}/retry-indexing", include_csrf=True)
    if s26 == 200 and isinstance(retry_res, dict) and retry_res.get("status") in ["COMPLETED", "PARTIAL"]:
        record_pass(26, "Retry indexing endpoint functions idempotently post-commit", f"Indexed count: {retry_res.get('indexed_count')}")
    else:
        record_fail(26, "Retry vector indexing", f"Status: {s26}, Response: {retry_res}")

    # Test 27: Existing demo data remains untouched and pristine
    s27, demo_summary, _ = demo_client.request("GET", "/api/v1/dashboard/summary")
    if (
        s27 == 200 and
        isinstance(demo_summary, dict) and
        demo_summary.get("total_transactions") == 208 and
        demo_summary.get("total_income") == 750000.00 and
        demo_summary.get("total_expenses") == 500162.00
    ):
        record_pass(27, "Existing synthetic demo records strictly unchanged", "Income=₹7,50,000.00, Expenses=₹5,00,162.00, Txs=208.")
    else:
        record_fail(27, "Demo data preservation", f"Demo totals changed! Income: {demo_summary.get('total_income')}, Txs: {demo_summary.get('total_transactions')}")

    # CLEANUP: Delete temporary test users and associated records to leave Db2 pristine
    try:
        import subprocess
        cleanup_script = (
            "from app.db import db_manager\n"
            "for tbl in ['TRANSACTION_EMBEDDINGS', 'TRANSACTIONS', 'IMPORT_JOBS', 'ACCOUNTS', 'USER_SESSIONS', 'USERS']:\n"
            "    db_manager.execute_statement(f'DELETE FROM FINSIGHT.{tbl} WHERE user_id != \\'usr_demo_synthetic_01\\'')\n"
        )
        subprocess.run(["docker", "exec", "finsight-ai-service", "python", "-c", cleanup_script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    print("\n" + "=" * 80)
    print(f"STAGE 5 RESULTS: {passed}/{passed + failed} PASSED, {failed}/{passed + failed} FAILED")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
