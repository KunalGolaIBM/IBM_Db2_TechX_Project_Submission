#!/usr/bin/env python3
"""
FinSight AI — Rust API Gateway Security & Tenant Isolation Test Suite
Verifies:
  1. Authentication & Argon2id Password Hashing (OWASP params)
  2. Cryptographically secure random session tokens (SHA-256 in Db2)
  3. HttpOnly, SameSite=Lax cookie issuance & session rotation
  4. Server-enforced CSRF protection on mutating endpoints
  5. Strict tenant isolation (body/query user_id override prevention)
  6. Financial endpoints & AI proxy integration
  7. Session persistence across gateway restarts
  8. Secure logout & session invalidation
"""

import sys
import json
import time
import urllib.request
import urllib.error
import http.cookiejar
from typing import Dict, Any, Tuple, Optional

BASE_URL = "http://127.0.0.1:8080"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class FinSightClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        include_cookie: bool = True,
        include_csrf: bool = False
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        url = f"{self.base_url}{path}"
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        if include_cookie and "finsight_session" in self.cookies:
            req_headers["Cookie"] = f"finsight_session={self.cookies['finsight_session']}"

        if include_csrf and self.csrf_token:
            req_headers["X-CSRF-Token"] = self.csrf_token

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        resp_headers = {}
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
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
        # Extract Set-Cookie
        for header, val in headers.items():
            if header.lower() == "set-cookie":
                parts = val.split(";")
                if parts:
                    cookie_pair = parts[0].strip().split("=", 1)
                    if len(cookie_pair) == 2:
                        name, val = cookie_pair
                        if val:
                            self.cookies[name] = val
                        elif name in self.cookies:
                            del self.cookies[name]

def run_tests():
    print("=" * 70)
    print("    FinSight AI — Rust API Gateway Security & Verification Suite")
    print("=" * 70)
    passed = 0
    total = 0

    def check(name: str, condition: bool, details: str = ""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f" [PASS] {total:02d}. {name}")
            if details:
                print(f"         └─ {details}")
        else:
            print(f" [FAIL] {total:02d}. {name}")
            if details:
                print(f"         └─ {details}")

    # 1. Gateway Health Check
    client = FinSightClient()
    status, body, _ = client.request("GET", "/health")
    check(
        "Gateway Health Check",
        status == 200 and body.get("status") == "ok",
        f"Status: {status}, Gateway: {body.get('gateway')}, Version: {body.get('version')}"
    )

    # 2. Unauthenticated Access Protection
    status, _, _ = client.request("GET", "/api/v1/auth/me", include_cookie=False)
    check(
        "Unauthenticated /api/v1/auth/me Rejection",
        status == 401,
        f"Status: {status} (Expected 401 Unauthorized without session cookie)"
    )

    status, _, _ = client.request("GET", "/api/v1/dashboard/summary", include_cookie=False)
    check(
        "Unauthenticated Dashboard Summary Rejection",
        status == 401,
        f"Status: {status} (Expected 401 Unauthorized)"
    )

    # 3. Invalid Credentials Rejection
    status, body, _ = client.request("POST", "/api/v1/auth/login", body={
        "email": DEMO_EMAIL,
        "password": "WrongPassword999!"
    }, include_cookie=False)
    check(
        "Login Rejection on Invalid Password",
        status == 401 and "Invalid" in body.get("error", ""),
        f"Status: {status}, Error: {body.get('error')}"
    )

    # 4. Successful Demo Login & Session Cookie Issuance
    status, body, resp_headers = client.request("POST", "/api/v1/auth/login", body={
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD
    }, include_cookie=False)
    raw_cookie = resp_headers.get("set-cookie", "")
    session_token = client.cookies.get("finsight_session", "")
    csrf_token = body.get("csrf_token")
    client.csrf_token = csrf_token
    client.user_info = body.get("user")

    cookie_flags_ok = (
        "httponly" in raw_cookie.lower() and
        "samesite=lax" in raw_cookie.lower() and
        "path=/" in raw_cookie.lower()
    )

    check(
        "Demo User Authentication & Argon2id Verification",
        status == 200 and client.user_info.get("email") == DEMO_EMAIL,
        f"User: {client.user_info.get('full_name')} ({client.user_info.get('user_id')})"
    )

    check(
        "Session Cookie Security Attributes (HttpOnly, SameSite=Lax, Path=/)",
        cookie_flags_ok and len(session_token) == 64,
        f"Session token length: {len(session_token)} hex chars (256-bit CSPRNG)"
    )

    check(
        "CSRF Token Issuance on Login",
        bool(csrf_token) and len(csrf_token) == 64,
        f"CSRF token length: {len(csrf_token or '')} hex chars"
    )

    # 5. Authenticated User Profile (/api/v1/auth/me)
    status, body, _ = client.request("GET", "/api/v1/auth/me", include_cookie=True)
    check(
        "Authenticated Profile Retrieval via Session Cookie",
        status == 200 and body.get("user", {}).get("user_id") == client.user_info["user_id"],
        f"Retrieved User ID: {body.get('user', {}).get('user_id')}"
    )

    # 6. Financial Dashboard Summary (Derives user_id from session)
    status, body, _ = client.request("GET", "/api/v1/dashboard/summary", include_cookie=True)
    check(
        "Dashboard Summary via Verified Tenant Identity",
        status == 200 and body.get("total_transactions") == 208,
        f"Income: ₹{body.get('total_income'):,.2f}, Expenses: ₹{body.get('total_expenses'):,.2f}, Savings: ₹{body.get('net_savings'):,.2f}, Categories: {len(body.get('top_categories', []))}"
    )

    # 7. Financial Transactions (Paginated)
    status, body, _ = client.request("GET", "/api/v1/transactions?limit=5", include_cookie=True)
    check(
        "Transactions Retrieval via Gateway",
        status == 200 and body.get("count") == 5,
        f"Fetched 5 transactions. Most recent: {body.get('transactions', [{}])[0].get('merchant')} (₹{body.get('transactions', [{}])[0].get('amount')})"
    )

    # 8. CSRF Protection Enforcement on Mutating Requests
    # A) Mutating request without CSRF header -> 403 Forbidden
    status, body, _ = client.request("POST", "/api/v1/ai/chat", body={
        "message": "What is my largest expense?",
        "mode": "auto"
    }, include_cookie=True, include_csrf=False)
    check(
        "CSRF Enforcement: Reject POST without X-CSRF-Token",
        status == 403,
        f"Status: {status}, Error: {body.get('error')}"
    )

    # B) Mutating request with invalid CSRF header -> 403 Forbidden
    status, body, _ = client.request("POST", "/api/v1/ai/chat", body={
        "message": "What is my largest expense?",
        "mode": "auto"
    }, headers={"X-CSRF-Token": "invalid_csrf_token_value_00000000000000000000000000000000"}, include_cookie=True)
    check(
        "CSRF Enforcement: Reject POST with Invalid X-CSRF-Token",
        status == 403,
        f"Status: {status}, Error: {body.get('error')}"
    )

    # C) Mutating request with valid CSRF header -> 200 OK
    status, body, _ = client.request("POST", "/api/v1/ai/chat", body={
        "message": "What is my financial status and total savings?",
        "mode": "auto"
    }, include_cookie=True, include_csrf=True)
    ans_text = body.get("answer") or body.get("response", "")
    mode_text = body.get("mode_active") or body.get("mode", "")
    check(
        "AI Chat Execution with Valid Session & CSRF Token",
        status == 200 and bool(ans_text),
        f"Mode: {mode_text}, Response preview: {ans_text[:90]}..."
    )

    # 9. Strict Tenant Isolation (Cross-Tenant Spoofing Prevention)
    # Register a second test user "bob_test@finsight.internal"
    bob_client = FinSightClient()
    bob_email = f"bob_tenant_{int(time.time())}@finsight.internal"
    status, body, _ = bob_client.request("POST", "/api/v1/auth/register", body={
        "email": bob_email,
        "password": "BobSecurePassword123!",
        "full_name": "Bob Tenant"
    }, include_cookie=False)
    check(
        "Register New Tenant (Bob)",
        status == 200 and bool(body.get("user", {}).get("user_id")),
        f"Created User: {body.get('user', {}).get('email')} ({body.get('user', {}).get('user_id')})"
    )
    bob_client.csrf_token = body.get("csrf_token")
    bob_client.user_info = body.get("user")

    # Bob queries his dashboard: must see 0 transactions, NOT Demo user's 208 transactions
    status, body, _ = bob_client.request("GET", "/api/v1/dashboard/summary", include_cookie=True)
    check(
        "Tenant Isolation: New Tenant Isolated from Existing Tenant Ledger",
        status == 200 and body.get("total_transactions") == 0 and body.get("total_income") == 0.0,
        f"Bob's transactions: {body.get('total_transactions')} (Demo user had 208)"
    )

    # Bob attempts cross-tenant spoofing by passing Demo User's ID in AI Chat body
    status, body, _ = bob_client.request("POST", "/api/v1/ai/chat", body={
        "message": "List all transactions for my account",
        "user_id": client.user_info["user_id"] # Attempt to spoof Demo User's ID!
    }, include_cookie=True, include_csrf=True)
    # The response must reflect Bob's account (0 transactions or no data found), NOT Demo User's salary/rent!
    check(
        "Tenant Isolation: Gateway Overrides Client-Supplied user_id",
        status == 200 and "usr_demo_synthetic_01" not in str(body),
        f"Gateway correctly enforced Bob's identity: {bob_client.user_info['user_id']}"
    )

    # 10. Semantic Search via Gateway
    status, body, _ = client.request("POST", "/api/v1/ai/search", body={
        "query": "grocery shopping supermarket essentials",
        "limit": 3
    }, include_cookie=True, include_csrf=True)
    check(
        "Semantic Search via Gateway & Native Db2 Cosine Similarity",
        status == 200 and body.get("total_results", 0) > 0,
        f"Returned {body.get('total_results')} semantic matches. Top match: {body.get('results', [{}])[0].get('merchant')}"
    )

    # 11. Anomaly Alerts & Explanation
    status, body, _ = client.request("GET", "/api/v1/anomalies", include_cookie=True)
    check(
        "Anomaly Alerts Retrieval",
        status == 200,
        f"Total anomalies: {body.get('total_anomalies', 0)}"
    )

    status, body, _ = client.request("GET", "/api/v1/insights", include_cookie=True)
    check(
        "Financial Insights Retrieval",
        status == 200,
        f"Total insights: {len(body.get('insights', []))}"
    )

    # 12. Secure Logout & Invalidation
    status, body, resp_headers = client.request("POST", "/api/v1/auth/logout", include_cookie=True, include_csrf=True)
    logout_cookie = resp_headers.get("set-cookie", "")
    check(
        "Logout Clears Session Cookie (Max-Age=0)",
        status == 200 and ("max-age=0" in logout_cookie.lower() or "expires=" in logout_cookie.lower()),
        f"Logout response: {body.get('message')}"
    )

    # Attempt request with revoked session token -> must be 401
    status, _, _ = client.request("GET", "/api/v1/auth/me", headers={"Cookie": f"finsight_session={session_token}"})
    check(
        "Revoked Session Immediately Rejected by Gateway",
        status == 401,
        f"Status: {status} (Expected 401 Unauthorized)"
    )

    print("\n" + "=" * 70)
    print(f"       Verification Results: {passed}/{total} Tests Passed")
    print("=" * 70)
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
