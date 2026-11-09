#!/usr/bin/env python3
"""
FinSight AI — Stage 3B Frontend Authentication & Rust Gateway Integration Test Suite
Executes all 12 required test cases through the Vite proxy (http://127.0.0.1:5173/api):
  1. Registration with valid details.
  2. Registration with invalid details.
  3. Duplicate email handling.
  4. Login with valid credentials.
  5. Login with incorrect credentials.
  6. /auth/me with and without a session.
  7. Protected-route redirection / unauthenticated access check.
  8. Logout (with CSRF header).
  9. Access after logout (cookie removal & revoked session rejection).
  10. Session persistence across requests (simulating browser refresh).
  11. CSRF behavior for protected mutations (missing, forged, valid).
  12. Network / malformed input failure handling.
"""

import sys
import time
import json
import urllib.request
import urllib.error
import subprocess
from typing import Dict, Any, Tuple, Optional

PROXY_URL = "http://127.0.0.1:5173"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class ProxyClient:
    def __init__(self, base_url: str = PROXY_URL):
        self.base_url = base_url
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
        self.client_ip = f"10.133.{int(time.time()) % 200 + 10}.{int(time.time()) % 200 + 10}"

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        include_cookie: bool = True,
        include_csrf: bool = False
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

        if include_csrf and self.csrf_token:
            req_headers["X-CSRF-Token"] = self.csrf_token

        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                data = body.encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        resp_headers = {}

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                for k, v in resp.headers.items():
                    resp_headers[k.lower()] = v
                parsed = json.loads(raw) if raw else {}
                self._extract_cookies(resp.headers)
                return status, parsed, resp_headers
        except urllib.error.HTTPError as e:
            status = e.code
            raw = e.read().decode("utf-8")
            for k, v in e.headers.items():
                resp_headers[k.lower()] = v
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw}
            self._extract_cookies(e.headers)
            return status, parsed, resp_headers

    def _extract_cookies(self, headers):
        for header, val in headers.items():
            if header.lower() == "set-cookie":
                parts = val.split(";")
                if parts:
                    cookie_pair = parts[0].strip().split("=", 1)
                    if len(cookie_pair) == 2:
                        name, cookie_val = cookie_pair
                        if cookie_val:
                            self.cookies[name] = cookie_val
                        elif name in self.cookies:
                            del self.cookies[name]

def run_db2_sql(sql: str) -> str:
    cmd = ["docker", "exec", "-i", "finsight-db2", "bash", "-c", f"su - db2inst1 -c \"db2 connect to FINDB > /dev/null && db2 -x \\\"{sql}\\\"\""]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()

def run_suite():
    results = []

    def record(num: int, name: str, passed: bool, details: str = ""):
        st = "PASS" if passed else "FAIL"
        results.append({"num": num, "name": name, "status": st, "details": details})
        print(f" [{st}] Test {num:02d}: {name}")
        if details:
            print(f"        └─ {details}")

    print("=" * 80)
    print("      FinSight AI — Stage 3B Frontend & Rust Gateway Integration Test Suite")
    print("=" * 80)

    # Test Account Setup
    ts = int(time.time())
    test_email = f"test_stage3b_{ts}@finsight.internal"
    test_password = "SecurePassword123!"
    test_name = "Stage 3B Test User"
    test_user_id = None

    client = ProxyClient()

    # 1. Registration with valid details
    status, body, hdrs = client.request("POST", "/api/v1/auth/register", body={
        "email": test_email,
        "password": test_password,
        "full_name": test_name
    }, include_cookie=False)
    reg_ok = status == 200 and "user" in body and "finsight_session" in client.cookies and "csrf_token" in body
    test_user_id = body.get("user", {}).get("user_id")
    client.csrf_token = body.get("csrf_token")
    record(1, "Registration with Valid Details via Vite Proxy", reg_ok,
           f"Status: {status}, User ID: {test_user_id}, Session Cookie Set: {'finsight_session' in client.cookies}")

    # 2. Registration with invalid details
    # 2a. Short password (<8 chars)
    c2 = ProxyClient()
    st_p, b_p, _ = c2.request("POST", "/api/v1/auth/register", body={"email": f"bad_{ts}@test.com", "password": "short", "full_name": "Test User"}, include_cookie=False)
    # 2b. Bad email
    st_e, b_e, _ = c2.request("POST", "/api/v1/auth/register", body={"email": "not-an-email", "password": "ValidPassword123!", "full_name": "Test User"}, include_cookie=False)
    # 2c. Short name (<2 chars)
    st_n, b_n, _ = c2.request("POST", "/api/v1/auth/register", body={"email": f"valid_{ts}@test.com", "password": "ValidPassword123!", "full_name": "A"}, include_cookie=False)
    invalid_reg_ok = st_p == 400 and st_e == 400 and st_n == 400
    record(2, "Registration with Invalid Details Rejected (Status 400)", invalid_reg_ok,
           f"Short PW status: {st_p}, Invalid Email status: {st_e}, Short Name status: {st_n}")

    # 3. Duplicate email handling
    st_dup, b_dup, _ = c2.request("POST", "/api/v1/auth/register", body={
        "email": test_email,
        "password": test_password,
        "full_name": "Another User"
    }, include_cookie=False)
    dup_ok = st_dup == 409 and "already exists" in b_dup.get("error", "").lower()
    record(3, "Duplicate Email Registration Rejection (Status 409)", dup_ok,
           f"Status: {st_dup}, Error message: '{b_dup.get('error')}'")

    # 4. Login with valid credentials
    login_client = ProxyClient()
    st_log, b_log, _ = login_client.request("POST", "/api/v1/auth/login", body={
        "email": test_email,
        "password": test_password
    }, include_cookie=False)
    login_client.csrf_token = b_log.get("csrf_token")
    log_ok = st_log == 200 and "finsight_session" in login_client.cookies and len(b_log.get("csrf_token", "")) == 64
    record(4, "Login with Valid Credentials (Status 200 + Session Cookie)", log_ok,
           f"Status: {st_log}, Session Cookie Length: {len(login_client.cookies.get('finsight_session', ''))}, CSRF Token Length: {len(b_log.get('csrf_token', ''))}")

    # 5. Login with incorrect credentials
    c_bad = ProxyClient()
    st_bad, b_bad, _ = c_bad.request("POST", "/api/v1/auth/login", body={
        "email": test_email,
        "password": "WrongPassword999!"
    }, include_cookie=False)
    bad_log_ok = st_bad == 401 and "invalid email or password" in b_bad.get("error", "").lower()
    record(5, "Login with Incorrect Password (Generic 401 Unauthorized)", bad_log_ok,
           f"Status: {st_bad}, Generic error message: '{b_bad.get('error')}'")

    # 6. /auth/me with and without a session
    # 6a. without session
    c_unauth = ProxyClient()
    st_me_unauth, b_me_unauth, _ = c_unauth.request("GET", "/api/v1/auth/me", include_cookie=False)
    # 6b. with session
    st_me_auth, b_me_auth, _ = login_client.request("GET", "/api/v1/auth/me", include_cookie=True)
    if "csrf_token" in b_me_auth:
        login_client.csrf_token = b_me_auth["csrf_token"]
    me_ok = st_me_unauth == 401 and st_me_auth == 200 and b_me_auth.get("user", {}).get("email") == test_email
    record(6, "/auth/me Session Validation (401 without cookie, 200 with cookie)", me_ok,
           f"Unauthenticated status: {st_me_unauth}, Authenticated status: {st_me_auth}, Resolved user: {b_me_auth.get('user', {}).get('email')}")

    # 7. Protected-route redirection / unauthenticated access check
    # Direct check: unauthenticated client calling /api/v1/dashboard/summary is rejected
    st_dash, b_dash, _ = c_unauth.request("GET", "/api/v1/dashboard/summary", include_cookie=False)
    prot_ok = st_dash == 401 and "authentication required" in b_dash.get("error", "").lower()
    record(7, "Protected Route Access without Session Rejected (Status 401)", prot_ok,
           f"Status: {st_dash}, Error: '{b_dash.get('error')}'")

    # 8. Logout with CSRF header
    prev_session_token = login_client.cookies.get("finsight_session")
    st_out, b_out, hdrs_out = login_client.request("POST", "/api/v1/auth/logout", include_cookie=True, include_csrf=True)
    set_cookie_logout = hdrs_out.get("set-cookie", "").lower()
    logout_ok = st_out == 200 and ("max-age=0" in set_cookie_logout or "expires=" in set_cookie_logout)
    record(8, "Logout Execution with X-CSRF-Token Header (Status 200 + Cookie Removal)", logout_ok,
           f"Status: {st_out}, Removal header: '{hdrs_out.get('set-cookie', '')}'")

    # 9. Access after logout
    # Check with previous session token header
    st_rev, b_rev, _ = c_unauth.request("GET", "/api/v1/auth/me", headers={"Cookie": f"finsight_session={prev_session_token}"}, include_cookie=False)
    post_logout_ok = st_rev == 401
    record(9, "Revoked Session Rejection Immediately After Logout (Status 401)", post_logout_ok,
           f"Status: {st_rev}, Error: '{b_rev.get('error')}'")

    # 10. Session persistence across requests (simulating browser refresh)
    # Re-login test user
    st_rel, b_rel, _ = login_client.request("POST", "/api/v1/auth/login", body={
        "email": test_email,
        "password": test_password
    }, include_cookie=False)
    login_client.csrf_token = b_rel.get("csrf_token")
    # Simulate multiple browser refresh requests to /auth/me
    st_ref1, b_ref1, _ = login_client.request("GET", "/api/v1/auth/me", include_cookie=True)
    st_ref2, b_ref2, _ = login_client.request("GET", "/api/v1/auth/me", include_cookie=True)
    if "csrf_token" in b_ref2:
        login_client.csrf_token = b_ref2["csrf_token"]
    persist_ok = st_ref1 == 200 and st_ref2 == 200 and b_ref1.get("user", {}).get("user_id") == test_user_id
    record(10, "Session Persistence Across Multiple Requests (Browser Refresh)", persist_ok,
           f"Request 1 status: {st_ref1}, Request 2 status: {st_ref2}, Identity: {b_ref1.get('user', {}).get('email')}")

    # 11. CSRF behavior for protected mutations
    # 11a. Missing CSRF Token -> 403 Forbidden
    st_csrf_miss, b_csrf_miss, _ = login_client.request("POST", "/api/v1/ai/chat", body={"message": "balance"}, include_cookie=True, include_csrf=False)
    # 11b. Forged CSRF Token -> 403 Forbidden
    st_csrf_bad, b_csrf_bad, _ = login_client.request("POST", "/api/v1/ai/chat", body={"message": "balance"}, headers={"X-CSRF-Token": "0000000000000000000000000000000000000000000000000000000000000000"}, include_cookie=True)
    # 11c. Valid CSRF Token -> 200 OK
    st_csrf_ok, b_csrf_ok, _ = login_client.request("POST", "/api/v1/ai/chat", body={"message": "balance", "mode": "deterministic"}, include_cookie=True, include_csrf=True)
    csrf_ok = st_csrf_miss == 403 and st_csrf_bad == 403 and st_csrf_ok == 200
    record(11, "CSRF Mutation Protection (Missing: 403, Forged: 403, Valid: 200)", csrf_ok,
           f"Missing status: {st_csrf_miss}, Forged status: {st_csrf_bad}, Valid status: {st_csrf_ok}")

    # 12. Network / malformed input failure handling
    st_malf, b_malf, _ = client.request("POST", "/api/v1/auth/login", body="not_valid_json_payload", headers={"Content-Type": "application/json"}, include_cookie=False)
    malf_ok = st_malf in (400, 422)
    record(12, "Malformed Input Handling via Gateway (Status 400/422)", malf_ok,
           f"Malformed body status: {st_malf}")

    # CLEANUP: Delete temporary test user and associated sessions
    if test_user_id:
        run_db2_sql(f"DELETE FROM FINSIGHT.USERS WHERE user_id = '{test_user_id}'")
        remaining = run_db2_sql(f"SELECT COUNT(*) FROM FINSIGHT.USER_SESSIONS WHERE user_id = '{test_user_id}'")
        print(f"\n[CLEANUP] Deleted test user {test_user_id}. Remaining orphan sessions in Db2: {remaining}")

    print("\n" + "=" * 80)
    passed_cnt = sum(1 for r in results if r["status"] == "PASS")
    total_cnt = len(results)
    print(f"       Stage 3B Integration Suite: {passed_cnt}/{total_cnt} Tests Passed")
    print("=" * 80)

    return results

if __name__ == "__main__":
    res = run_suite()
    all_passed = all(r["status"] == "PASS" for r in res)
    sys.exit(0 if all_passed else 1)
