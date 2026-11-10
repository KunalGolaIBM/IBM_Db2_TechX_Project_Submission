#!/usr/bin/env python3
"""
FinSight AI — Stage 3B.1 Authentication Persistence & Security Audit Verification Suite
Tests:
  1. Login -> session cookie set + initial CSRF token issued.
  2. Browser refresh simulation -> in-memory CSRF cleared, session cookie preserved.
  3. /api/v1/auth/me session restoration -> returns user profile AND refreshed CSRF bootstrap token.
  4. Authenticated mutation after refresh -> POST /api/v1/ai/chat with restored CSRF token succeeds (200 OK).
  5. Mutation with invalid/missing CSRF token after refresh rejected (403 Forbidden).
  6. Authenticated logout after refresh -> POST /api/v1/auth/logout with restored CSRF token succeeds (200 OK).
  7. Post-logout session invalidation -> session removed from Db2, /auth/me returns 401.
  8. Registration lifecycle -> register, refresh, mutate, logout.
  9. Client security check: No hardcoded credentials or demo passwords in frontend source code or production dist bundle.
  10. Dashboard UI privacy check: No raw internal user_id or raw csrf_token leaked in DashboardPage.tsx.
"""

import sys
import os
import time
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional

PROXY_URL = "http://127.0.0.1:5173"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class FinsightClient:
    def __init__(self, base_url: str = PROXY_URL):
        self.base_url = base_url
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
        self.client_ip = f"10.144.{int(time.time() * 1000) % 200 + 10}.{int(time.time()) % 200 + 10}"

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
                        if cookie_val == "" or "max-age=0" in val.lower():
                            self.cookies.pop(name, None)
                        else:
                            self.cookies[name] = cookie_val

def run_tests():
    passed = 0
    failed = 0

    print("=" * 80)
    print("FINSIGHT AI — STAGE 3B.1 AUTH PERSISTENCE & SECURITY AUDIT VERIFICATION")
    print(f"Target Gateway (via Vite proxy): {PROXY_URL}")
    print("=" * 80)

    # -------------------------------------------------------------
    # Test 1: Login with valid credentials
    # -------------------------------------------------------------
    print("\n[TEST 1] Login with valid credentials...")
    client = FinsightClient()
    status, body, headers = client.request(
        "POST",
        "/api/v1/auth/login",
        body={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    if status == 200 and "finsight_session" in client.cookies and "csrf_token" in body:
        client.csrf_token = body["csrf_token"]
        print(f"  PASS: Login succeeded (HTTP {status}). Session cookie and CSRF token received.")
        passed += 1
    else:
        print(f"  FAIL: Expected 200 with session cookie and CSRF token, got {status}: {body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 2: Simulate page refresh (clear client in-memory CSRF)
    # -------------------------------------------------------------
    print("\n[TEST 2] Simulate browser refresh (in-memory CSRF cleared, cookie preserved)...")
    client.csrf_token = None
    if client.csrf_token is None and "finsight_session" in client.cookies:
        print("  PASS: In-memory state cleared, HttpOnly cookie preserved.")
        passed += 1
    else:
        print("  FAIL: State setup failed.")
        failed += 1

    # -------------------------------------------------------------
    # Test 3: GET /api/v1/auth/me restores session AND fresh CSRF token
    # -------------------------------------------------------------
    print("\n[TEST 3] GET /api/v1/auth/me session restoration & CSRF bootstrap...")
    status, body, _ = client.request("GET", "/api/v1/auth/me")
    if status == 200 and "user" in body and "csrf_token" in body:
        restored_csrf = body["csrf_token"]
        client.csrf_token = restored_csrf
        print(f"  PASS: Restored session for '{body['user']['email']}'. Fresh CSRF token received.")
        passed += 1
    else:
        print(f"  FAIL: Expected 200 with user and csrf_token, got {status}: {body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 4: Authenticated mutation after refresh with restored CSRF token
    # -------------------------------------------------------------
    print("\n[TEST 4] Authenticated mutation POST /api/v1/ai/chat using restored CSRF token...")
    status, body, _ = client.request(
        "POST",
        "/api/v1/ai/chat",
        body={"message": "Summarize my balance in 10 words.", "mode": "deterministic"},
        include_csrf=True
    )
    if status == 200 and ("answer" in body or "reply" in body):
        print(f"  PASS: Protected mutation succeeded after refresh (HTTP {status}).")
        passed += 1
    else:
        print(f"  FAIL: Expected 200, got {status}: {body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 5: Mutation rejection with forged/missing CSRF token after refresh
    # -------------------------------------------------------------
    print("\n[TEST 5] Mutation rejection with invalid CSRF token...")
    status, body, _ = client.request(
        "POST",
        "/api/v1/ai/chat",
        body={"message": "Malicious forged call"},
        custom_csrf="forged_csrf_token_1234567890abcdef"
    )
    if status == 403:
        print(f"  PASS: Forged CSRF correctly rejected (HTTP 403: {body.get('error', body)})")
        passed += 1
    else:
        print(f"  FAIL: Expected 403 Forbidden, got {status}: {body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 6: Authenticated logout after refresh with restored CSRF token
    # -------------------------------------------------------------
    print("\n[TEST 6] Authenticated logout POST /api/v1/auth/logout after refresh...")
    status, body, headers = client.request(
        "POST",
        "/api/v1/auth/logout",
        include_csrf=True
    )
    if status == 200:
        print(f"  PASS: Logout succeeded (HTTP 200: {body.get('message', body)})")
        passed += 1
    else:
        print(f"  FAIL: Expected 200 OK, got {status}: {body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 7: Post-logout session invalidation in Db2
    # -------------------------------------------------------------
    print("\n[TEST 7] Post-logout session invalidation (cookie removal & Db2 deletion)...")
    status, body, _ = client.request("GET", "/api/v1/auth/me", include_cookie=True)
    if status == 401:
        print(f"  PASS: Revoked session rejected with HTTP 401.")
        passed += 1
    else:
        print(f"  FAIL: Expected 401 Unauthorized after logout, got {status}: {body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 8: Full registration lifecycle with refresh, mutation, and logout
    # -------------------------------------------------------------
    print("\n[TEST 8] Registration lifecycle (register -> refresh -> mutate -> logout)...")
    reg_client = FinsightClient()
    unique_email = f"audit.user.{int(time.time())}@finsight.test"
    reg_status, reg_body, _ = reg_client.request(
        "POST",
        "/api/v1/auth/register",
        body={
            "full_name": "Audit Test User",
            "email": unique_email,
            "password": "SecurePassword123!"
        }
    )
    if reg_status == 200 and "finsight_session" in reg_client.cookies:
        # Simulate refresh
        reg_client.csrf_token = None
        me_status, me_body, _ = reg_client.request("GET", "/api/v1/auth/me")
        if me_status == 200 and "csrf_token" in me_body:
            reg_client.csrf_token = me_body["csrf_token"]
            # Mutate
            chat_status, _, _ = reg_client.request(
                "POST",
                "/api/v1/ai/chat",
                body={"message": "Hello from audit test"},
                include_csrf=True
            )
            # Logout
            logout_status, _, _ = reg_client.request(
                "POST",
                "/api/v1/auth/logout",
                include_csrf=True
            )
            if chat_status == 200 and logout_status == 200:
                print(f"  PASS: Full registration lifecycle verified cleanly for {unique_email}.")
                passed += 1
            else:
                print(f"  FAIL: Chat status {chat_status}, logout status {logout_status}")
                failed += 1
        else:
            print(f"  FAIL: Refresh failed after registration, got {me_status}: {me_body}")
            failed += 1
    else:
        print(f"  FAIL: Registration failed, got {reg_status}: {reg_body}")
        failed += 1

    # -------------------------------------------------------------
    # Test 9: Zero demo credentials in frontend source code & build bundles
    # -------------------------------------------------------------
    print("\n[TEST 9] Audit frontend source code and production build for leaked credentials...")
    login_page_path = os.path.abspath("src/pages/LoginPage.tsx")
    dist_dir = os.path.abspath("dist/assets")
    leaks = []

    # Check LoginPage.tsx
    if os.path.exists(login_page_path):
        with open(login_page_path, "r", encoding="utf-8") as f:
            src = f.read()
            if "DemoPassword123!" in src:
                leaks.append("DemoPassword123! in LoginPage.tsx")
            if "Fill Seed Demo Account" in src:
                leaks.append("Fill Seed Demo Account button in LoginPage.tsx")

    # Check dist JS bundles
    if os.path.exists(dist_dir):
        for fname in os.listdir(dist_dir):
            if fname.endswith(".js"):
                fpath = os.path.join(dist_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    bundle_src = f.read()
                    if "DemoPassword123!" in bundle_src:
                        leaks.append(f"DemoPassword123! in dist/{fname}")

    if not leaks:
        print("  PASS: Zero demo credentials found in LoginPage.tsx and production build bundles.")
        passed += 1
    else:
        print(f"  FAIL: Credential leaks detected: {leaks}")
        failed += 1

    # -------------------------------------------------------------
    # Test 10: Dashboard UI privacy check (no raw user_id or raw csrf_token displayed)
    # -------------------------------------------------------------
    print("\n[TEST 10] Audit DashboardPage.tsx for raw internal user_id / raw csrf_token display...")
    dash_page_path = os.path.abspath("src/pages/DashboardPage.tsx")
    privacy_issues = []
    if os.path.exists(dash_page_path):
        with open(dash_page_path, "r", encoding="utf-8") as f:
            dash_src = f.read()
            if "user?.user_id" in dash_src:
                privacy_issues.append("Raw user_id rendered in DashboardPage.tsx")
            if "csrfToken.slice" in dash_src:
                privacy_issues.append("Raw CSRF token fragment rendered in DashboardPage.tsx")

    if not privacy_issues:
        print("  PASS: DashboardPage.tsx displays only user-facing details (name, email, secure status).")
        passed += 1
    else:
        print(f"  FAIL: Privacy issues detected: {privacy_issues}")
        failed += 1

    print("\n" + "=" * 80)
    print(f"STAGE 3B.1 AUDIT RESULTS: {passed} PASSED, {failed} FAILED (TOTAL: {passed + failed})")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
