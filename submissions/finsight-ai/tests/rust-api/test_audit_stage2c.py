#!/usr/bin/env python3
"""
FinSight AI — Stage 2C Comprehensive Security & Tenant Isolation Audit Suite
Validates:
  1. Authentication & Argon2id Password Storage (13 scenarios)
  2. Cookie Security Attributes & Session Lifecycle
  3. CSRF Validation on All Mutating Endpoints
  4. Cross-Tenant Isolation Attacks (Query, Body, Path, Headers)
  5. Python Internal Service Token & Network Boundary
  6. CORS Origin & Credential Enforcement
  7. In-Process Rate Limiting & Body Size Hardening
  8. Database Schema Integrity & Session Cascade
"""

import sys
import json
import time
import urllib.request
import urllib.error
import subprocess
from typing import Dict, Any, Tuple, Optional, List

import random

BASE_URL = "http://127.0.0.1:8080"
DEMO_EMAIL = "alex.chen.demo@finsight.internal"
DEMO_PASSWORD = "DemoPassword123!"

class AuditClient:
    def __init__(self, base_url: str = BASE_URL, client_ip: Optional[str] = None):
        self.base_url = base_url
        self.client_ip = client_ip or f"10.{random.randint(10,250)}.{random.randint(1,250)}.{random.randint(1,250)}"
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None

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
            elif isinstance(body, bytes):
                data = body
                if "Content-Type" not in req_headers:
                    req_headers["Content-Type"] = "application/octet-stream"
            elif isinstance(body, str):
                data = body.encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        resp_headers = {}
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
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
    cmd = ["docker", "exec", "-i", "finsight-db2", "su", "-", "db2inst1", "-c", f"db2 connect to FINDB > /dev/null && db2 -x \"{sql}\""]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout.strip()

def run_audit():
    print("=" * 80)
    print("      FinSight AI — Stage 2C Comprehensive Security Audit Suite")
    print("=" * 80)
    
    results: List[Dict[str, Any]] = []

    def record(area: str, test_name: str, passed: bool, evidence: str):
        status = "PASS" if passed else "FAIL"
        results.append({"area": area, "test": test_name, "status": status, "evidence": evidence})
        icon = "[PASS]" if passed else "[FAIL]"
        print(f" {icon} [{area}] {test_name}")
        print(f"        └─ {evidence}")

    # =========================================================================
    # AREA 1: CORS & SERVICE TOKEN BOUNDARIES
    # =========================================================================
    client = AuditClient()

    # Test 1.1: Allowed Origin Receives ACAO and ACAC headers
    status, _, headers = client.request(
        "OPTIONS",
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        },
        include_cookie=False
    )
    acao = headers.get("access-control-allow-origin", "")
    acac = headers.get("access-control-allow-credentials", "")
    acah = headers.get("access-control-allow-headers", "")
    record(
        "CORS",
        "Allowed Origin Configuration",
        acao == "http://localhost:5173" and acac == "true" and "x-service-token" not in acah.lower(),
        f"ACAO: '{acao}', ACAC: '{acac}', ACAH: '{acah}'"
    )

    # Test 1.2: Disallowed Origin is Rejected (No ACAO header)
    status, _, headers = client.request(
        "OPTIONS",
        "/api/v1/auth/me",
        headers={
            "Origin": "http://malicious-attacker.com",
            "Access-Control-Request-Method": "GET"
        },
        include_cookie=False
    )
    disallowed_acao = headers.get("access-control-allow-origin")
    record(
        "CORS",
        "Disallowed Origin Rejection",
        disallowed_acao is None,
        f"Disallowed Origin 'http://malicious-attacker.com' received ACAO: {disallowed_acao}"
    )

    # Test 1.3: Python Service Has No Published Host Port
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        py_host_accessible = True
    except Exception:
        py_host_accessible = False
    record(
        "Python service authentication",
        "Python Service Port Not Exposed to Host",
        not py_host_accessible,
        "Direct connection to http://127.0.0.1:8000 timed out / connection refused as expected"
    )

    # Test 1.4: Python Service Rejects Request with Missing/Invalid Service Token
    # We execute curl inside the rust container to test private python endpoint directly
    py_unauth_cmd = ["docker", "exec", "finsight-rust-api", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://ai-service:8000/api/internal/dashboard/summary?user_id=usr_demo_synthetic_01"]
    py_unauth_code = subprocess.run(py_unauth_cmd, capture_output=True, text=True).stdout.strip()

    py_badtoken_cmd = ["docker", "exec", "finsight-rust-api", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-H", "x-service-token: invalid_bogus_token", "http://ai-service:8000/api/internal/dashboard/summary?user_id=usr_demo_synthetic_01"]
    py_badtoken_code = subprocess.run(py_badtoken_cmd, capture_output=True, text=True).stdout.strip()

    record(
        "Python service authentication",
        "Python Rejects Missing / Invalid Service Token",
        py_unauth_code in ["401", "422"] and py_badtoken_code == "401",
        f"Missing token status: {py_unauth_code}, Invalid token status: {py_badtoken_code}"
    )

    # =========================================================================
    # AREA 2: AUTHENTICATION & PASSWORD STORAGE (13 SCENARIOS)
    # =========================================================================
    # 2.1 Register New User
    alice_client = AuditClient()
    alice_email = f"alice_audit_{int(time.time())}@finsight.internal"
    alice_password = "AliceSecurePassword2026!"
    status, body, _ = alice_client.request("POST", "/api/v1/auth/register", body={
        "email": alice_email,
        "password": alice_password,
        "full_name": "Alice Auditor"
    }, include_cookie=False)
    alice_user = body.get("user", {})
    record(
        "Registration/login",
        "1. Register New User",
        status == 200 and alice_user.get("email") == alice_email and "password" not in str(body),
        f"Registered user: {alice_user.get('user_id')} ({alice_user.get('email')})"
    )

    # 2.2 Register Same Email Again (Duplicate Rejection)
    status, body, _ = alice_client.request("POST", "/api/v1/auth/register", body={
        "email": alice_email,
        "password": "AnotherPassword123!",
        "full_name": "Alice Duplicate"
    }, include_cookie=False)
    record(
        "Registration/login",
        "2. Duplicate Email Registration Rejection",
        status == 409,
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # 2.3 Verify Password Storage (Argon2id Hash in Db2, No Plaintext)
    db2_hash = run_db2_sql(f"SELECT password_hash FROM FINSIGHT.USERS WHERE user_id = '{alice_user.get('user_id')}'")
    record(
        "Password storage",
        "Argon2id Hash Stored in Db2 (No Plaintext)",
        db2_hash.startswith("$argon2id$") and alice_password not in db2_hash,
        f"Db2 Hash: {db2_hash[:32]}... (Algorithm: Argon2id, Length: {len(db2_hash)})"
    )

    # 2.4 Login with Correct Credentials
    login_client = AuditClient()
    status, body, headers = login_client.request("POST", "/api/v1/auth/login", body={
        "email": alice_email,
        "password": alice_password
    }, include_cookie=False)
    set_cookie = headers.get("set-cookie", "")
    token_1 = login_client.cookies.get("finsight_session", "")
    csrf_1 = body.get("csrf_token", "")
    record(
        "Registration/login",
        "3. Login with Correct Credentials",
        status == 200 and "finsight_session" in login_client.cookies,
        f"Status: {status}, Session Token Length: {len(token_1)}, CSRF Token Length: {len(csrf_1)}"
    )

    # 2.5 Login with Incorrect Password
    status, body, _ = login_client.request("POST", "/api/v1/auth/login", body={
        "email": alice_email,
        "password": "WrongPassword999!"
    }, include_cookie=False)
    record(
        "Registration/login",
        "4. Login with Incorrect Password (Generic Error)",
        status == 401 and "invalid email or password" in body.get("error", "").lower(),
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # 2.6 Login with Nonexistent Email
    status, body, _ = login_client.request("POST", "/api/v1/auth/login", body={
        "email": "nonexistent_user_99999@finsight.internal",
        "password": "SomePassword123!"
    }, include_cookie=False)
    record(
        "Registration/login",
        "5. Login with Nonexistent Email (Generic Error, No Enumeration)",
        status == 401 and "invalid email or password" in body.get("error", "").lower(),
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # 2.7 Login with Inactive Account
    # Temporarily set is_active = 0 in Db2
    run_db2_sql(f"UPDATE FINSIGHT.USERS SET is_active = 0 WHERE user_id = '{alice_user.get('user_id')}'")
    status, body, _ = login_client.request("POST", "/api/v1/auth/login", body={
        "email": alice_email,
        "password": alice_password
    }, include_cookie=False)
    # Restore is_active = 1
    run_db2_sql(f"UPDATE FINSIGHT.USERS SET is_active = 1 WHERE user_id = '{alice_user.get('user_id')}'")
    record(
        "Registration/login",
        "6. Login with Inactive Account Returns Generic Error (No Status Enumeration)",
        status == 401 and "invalid email or password" in body.get("error", "").lower(),
        f"Status: {status}, Generic error: '{body.get('error')}'"
    )

    # 2.7b Login with Passwordless / Null-Password Account
    # Create isolated passwordless test account in Db2
    null_pw_uid = f"usr_null_pw_{int(time.time())}"
    null_pw_email = f"null_pw_{int(time.time())}@finsight.internal"
    run_db2_sql(f"INSERT INTO FINSIGHT.USERS (user_id, email, full_name, created_at, password_hash, is_active, updated_at) VALUES ('{null_pw_uid}', '{null_pw_email}', 'Null PW User', CURRENT TIMESTAMP, NULL, 1, CURRENT TIMESTAMP)")
    status, body, _ = client.request("POST", "/api/v1/auth/login", body={
        "email": null_pw_email,
        "password": "AnyPassword123!"
    }, include_cookie=False)
    run_db2_sql(f"DELETE FROM FINSIGHT.USERS WHERE user_id = '{null_pw_uid}'")
    record(
        "Registration/login",
        "6b. Passwordless / Null-Hash Account Cannot Log In With Password",
        status == 401 and "invalid email or password" in body.get("error", "").lower(),
        f"Status: {status}, Safe rejection: '{body.get('error')}'"
    )

    # 2.7c Login with Malformed Password Hash Fails Safely
    malformed_uid = f"usr_bad_hash_{int(time.time())}"
    malformed_email = f"bad_hash_{int(time.time())}@finsight.internal"
    run_db2_sql(f"INSERT INTO FINSIGHT.USERS (user_id, email, full_name, created_at, password_hash, is_active, updated_at) VALUES ('{malformed_uid}', '{malformed_email}', 'Bad Hash User', CURRENT TIMESTAMP, 'corrupted_non_argon2_hash_value', 1, CURRENT TIMESTAMP)")
    status, body, _ = client.request("POST", "/api/v1/auth/login", body={
        "email": malformed_email,
        "password": "AnyPassword123!"
    }, include_cookie=False)
    run_db2_sql(f"DELETE FROM FINSIGHT.USERS WHERE user_id = '{malformed_uid}'")
    record(
        "Registration/login",
        "6c. Malformed Password Hash Fails Safely Without Exception",
        status == 401 and "invalid email or password" in body.get("error", "").lower(),
        f"Status: {status}, Safe rejection: '{body.get('error')}'"
    )

    # 2.7d Password Hash Never Exposed in API Responses
    # Check registration response, login response, /me response
    user_keys_reg = list(alice_user.keys())
    status, body, _ = login_client.request("GET", "/api/v1/auth/me", include_cookie=True)
    user_keys_me = list(body.get("user", {}).keys())
    hash_exposed = any("hash" in k.lower() or "password" in k.lower() for k in user_keys_reg + user_keys_me)
    record(
        "Password storage",
        "Zero Password Hashes in API Responses",
        not hash_exposed,
        f"Keys returned in registration: {user_keys_reg}, in /me: {user_keys_me}"
    )

    # 2.8 Request /me without Session
    unauth_client = AuditClient()
    status, body, _ = unauth_client.request("GET", "/api/v1/auth/me", include_cookie=False)
    record(
        "Session lifecycle",
        "7. Request /me without Session Rejection",
        status == 401,
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # 2.9 Request /me with Valid Session
    status, body, _ = login_client.request("GET", "/api/v1/auth/me", include_cookie=True)
    record(
        "Session lifecycle",
        "8. Request /me with Valid Session",
        status == 200 and body.get("user", {}).get("email") == alice_email,
        f"Retrieved user profile: {body.get('user', {}).get('email')}"
    )

    # 2.10 Request /me with Malformed/Tampered Cookie
    tampered_client = AuditClient()
    tampered_client.cookies["finsight_session"] = "tampered_fake_session_token_00000000000000000000000000000000000"
    status, body, _ = tampered_client.request("GET", "/api/v1/auth/me", include_cookie=True)
    record(
        "Session lifecycle",
        "9. Request /me with Tampered Cookie Rejection",
        status == 401,
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # 2.11 Session Rotation on Second Login
    status, body, _ = login_client.request("POST", "/api/v1/auth/login", body={
        "email": alice_email,
        "password": alice_password
    }, include_cookie=False)
    token_2 = login_client.cookies.get("finsight_session", "")
    record(
        "Session lifecycle",
        "10. Session Rotation on Re-Authentication",
        status == 200 and token_1 != token_2 and len(token_2) == 64,
        f"New session token generated: {token_2[:16]}... != {token_1[:16]}..."
    )

    # 2.12 Logout (Clears Cookie and Revokes Session in Db2)
    login_client.csrf_token = body.get("csrf_token")
    status, body, headers = login_client.request("POST", "/api/v1/auth/logout", include_cookie=True, include_csrf=True)
    logout_cookie = headers.get("set-cookie", "")
    record(
        "Session lifecycle",
        "11. Logout Invalidation and Cookie Removal",
        status == 200 and ("max-age=0" in logout_cookie.lower() or "expires=" in logout_cookie.lower()),
        f"Status: {status}, Set-Cookie header: '{logout_cookie}'"
    )

    # 2.13 Attempt to Reuse Revoked Session
    status, body, _ = login_client.request("GET", "/api/v1/auth/me", headers={"Cookie": f"finsight_session={token_2}"}, include_cookie=False)
    record(
        "Session lifecycle",
        "12. Reuse of Revoked Session Immediately Rejected",
        status == 401,
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # 2.14 Server-side Expiry Rejection
    # Create a session with past expiry directly in Db2 to verify gateway rejects expired session
    import hashlib
    expired_raw = "expired_raw_token_test_1234567890abcdef1234567890abcdef1234567890"
    expired_hash = hashlib.sha256(expired_raw.encode()).hexdigest()
    csrf_hash = hashlib.sha256(b"dummy_csrf").hexdigest()
    insert_exp_sql = f"INSERT INTO FINSIGHT.USER_SESSIONS (session_token_hash, user_id, csrf_token_hash, created_at, expires_at, last_active_at) VALUES ('{expired_hash}', '{alice_user.get('user_id')}', '{csrf_hash}', CURRENT TIMESTAMP - 2 DAYS, CURRENT TIMESTAMP - 1 DAY, CURRENT TIMESTAMP - 2 DAYS)"
    run_db2_sql(insert_exp_sql)
    status, body, _ = client.request("GET", "/api/v1/auth/me", headers={"Cookie": f"finsight_session={expired_raw}"}, include_cookie=False)
    record(
        "Session lifecycle",
        "13. Expired Session Rejected Server-Side",
        status == 401,
        f"Status: {status}, Error: '{body.get('error')}'"
    )

    # =========================================================================
    # AREA 3: COOKIE & CSRF SECURITY
    # =========================================================================
    # Re-login Alice for Cookie & CSRF tests
    status, body, headers = alice_client.request("POST", "/api/v1/auth/login", body={
        "email": alice_email,
        "password": alice_password
    }, include_cookie=False)
    cookie_hdr = headers.get("set-cookie", "")
    alice_client.csrf_token = body.get("csrf_token")

    # 3.1 Local Development Cookie Attributes (HTTP)
    cookie_local_valid = (
        "httponly" in cookie_hdr.lower() and
        "samesite=lax" in cookie_hdr.lower() and
        "path=/" in cookie_hdr.lower() and
        "max-age=86400" in cookie_hdr.lower() and
        "secure" not in cookie_hdr.lower()
    )
    record(
        "Cookie security",
        "Local Development Cookie Attributes (HttpOnly, SameSite=Lax, Path=/, No Secure)",
        cookie_local_valid,
        f"Set-Cookie: '{cookie_hdr}'"
    )

    # 3.2 Production Rejection of Insecure Cookie Configuration
    prod_insecure_proc = subprocess.run(
        ["docker", "run", "--rm", "-e", "ENVIRONMENT=production", "-e", "COOKIE_SECURE=false", "finsight-ai-rust-api"],
        capture_output=True,
        text=True
    )
    rejection_observed = prod_insecure_proc.returncode != 0 and "COOKIE_SECURE must be set to 'true'" in (prod_insecure_proc.stderr + prod_insecure_proc.stdout)
    record(
        "Cookie security",
        "Server Rejects Insecure Production Configuration (ENVIRONMENT=production without COOKIE_SECURE)",
        rejection_observed,
        f"Exit Code: {prod_insecure_proc.returncode}, Error detected: Invariant enforced at gateway startup"
    )

    # 3.3 Production HTTPS Cookie Attributes (Secure, HttpOnly, SameSite=Lax, Path=/, Max-Age=86400)
    # Spin up isolated production test container on port 8089 to observe real HTTP response headers
    subprocess.run(["docker", "rm", "-f", "finsight-rust-api-prod-test"], capture_output=True)
    subprocess.run([
        "docker", "run", "-d", "--name", "finsight-rust-api-prod-test",
        "--network", "finsight-ai_default",
        "-e", "COOKIE_SECURE=true",
        "-e", "ENVIRONMENT=production",
        "-e", "CSRF_SECRET=finsight_prod_csrf_secret_32bytes_key_xyz123!",
        "-p", "8089:8080",
        "finsight-ai-rust-api"
    ], capture_output=True)
    time.sleep(2)
    prod_client = AuditClient(base_url="http://127.0.0.1:8089")
    st_prod, body_prod, hdrs_prod = prod_client.request("POST", "/api/v1/auth/login", body={
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD
    }, include_cookie=False)
    prod_set_cookie = hdrs_prod.get("set-cookie", "")
    prod_cookie_valid = (
        st_prod == 200 and
        "secure" in prod_set_cookie.lower() and
        "httponly" in prod_set_cookie.lower() and
        "samesite=lax" in prod_set_cookie.lower() and
        "path=/" in prod_set_cookie.lower() and
        "max-age=86400" in prod_set_cookie.lower()
    )
    subprocess.run(["docker", "rm", "-f", "finsight-rust-api-prod-test"], capture_output=True)
    record(
        "Cookie security",
        "Production HTTPS Cookie Security Attributes (Secure, HttpOnly, SameSite=Lax, Path=/)",
        prod_cookie_valid,
        f"Production Set-Cookie: '{prod_set_cookie}'"
    )

    # =========================================================================
    # AREA 3B: COMPLETE CSRF ROUTE COVERAGE
    # =========================================================================

    # Route 1: POST /api/v1/ai/chat (Authenticated Mutation)
    # 1a. Missing CSRF Token -> 403 Forbidden
    status, body, _ = alice_client.request("POST", "/api/v1/ai/chat", body={"message": "What is my balance?"}, include_cookie=True, include_csrf=False)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/ai/chat (Missing CSRF Header -> 403 Forbidden)",
        status == 403,
        f"Status: {status}, Error: '{body.get('error')}'"
    )
    # 1b. Forged CSRF Token -> 403 Forbidden
    status, body, _ = alice_client.request("POST", "/api/v1/ai/chat", body={"message": "What is my balance?"}, headers={"X-CSRF-Token": "forged_token_000000000000000000000000000000000000000000000000"}, include_cookie=True)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/ai/chat (Forged CSRF Header -> 403 Forbidden)",
        status == 403,
        f"Status: {status}, Error: '{body.get('error')}'"
    )
    # 1c. Valid CSRF Token -> 200 OK
    status, body, _ = alice_client.request("POST", "/api/v1/ai/chat", body={"message": "Summarize my account summary."}, include_cookie=True, include_csrf=True)
    ai_text = body.get("answer") or body.get("response", "")
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/ai/chat (Valid CSRF Header -> 200 OK)",
        status == 200 and bool(ai_text),
        f"Status: {status}, AI Response: {len(ai_text)} chars"
    )

    # Route 2: POST /api/v1/anomalies/:alert_id/explain (Authenticated Mutation)
    # 2a. Missing CSRF Token -> 403 Forbidden
    status, body, _ = alice_client.request("POST", "/api/v1/anomalies/dummy_alert_01/explain", include_cookie=True, include_csrf=False)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/anomalies/:id/explain (Missing CSRF Header -> 403 Forbidden)",
        status == 403,
        f"Status: {status}, Error: '{body.get('error')}'"
    )
    # 2b. Forged CSRF Token -> 403 Forbidden
    status, body, _ = alice_client.request("POST", "/api/v1/anomalies/dummy_alert_01/explain", headers={"X-CSRF-Token": "forged_csrf_000000000000000000000000000000000000000000000000"}, include_cookie=True)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/anomalies/:id/explain (Forged CSRF Header -> 403 Forbidden)",
        status == 403,
        f"Status: {status}, Error: '{body.get('error')}'"
    )
    # 2c. Valid CSRF Token -> Proceeds past CSRF check (Returns 404 alert not found, verifying CSRF passed first)
    status, body, _ = alice_client.request("POST", "/api/v1/anomalies/dummy_alert_01/explain", include_cookie=True, include_csrf=True)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/anomalies/:id/explain (Valid CSRF Header -> CSRF Check Passed)",
        status in (200, 404),
        f"Status: {status} (Expected 404 for nonexistent alert, confirming CSRF check passed before alert lookup)"
    )

    # Route 3: POST /api/v1/auth/logout (Authenticated Mutation)
    # 3a. Missing CSRF Token -> 403 Forbidden
    status, body, _ = alice_client.request("POST", "/api/v1/auth/logout", include_cookie=True, include_csrf=False)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/auth/logout (Missing CSRF Header -> 403 Forbidden)",
        status == 403,
        f"Status: {status}, Error: '{body.get('error')}'"
    )
    # 3b. Forged CSRF Token -> 403 Forbidden
    status, body, _ = alice_client.request("POST", "/api/v1/auth/logout", headers={"X-CSRF-Token": "forged_logout_token_000000000000000000000000000000000000000000000000"}, include_cookie=True)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/auth/logout (Forged CSRF Header -> 403 Forbidden)",
        status == 403,
        f"Status: {status}, Error: '{body.get('error')}'"
    )
    # 3c. Valid CSRF Token -> 200 OK (will be executed on fresh session)
    # Create a sub-session specifically to test logout success with valid CSRF
    logout_test_client = AuditClient()
    st_l, b_l, h_l = logout_test_client.request("POST", "/api/v1/auth/login", body={"email": alice_email, "password": alice_password}, include_cookie=False)
    logout_test_client.csrf_token = b_l.get("csrf_token")
    status, body, hdrs = logout_test_client.request("POST", "/api/v1/auth/logout", include_cookie=True, include_csrf=True)
    record(
        "CSRF",
        "CSRF Route Coverage: /api/v1/auth/logout (Valid CSRF Header -> 200 OK)",
        status == 200,
        f"Status: {status}, Message: '{body.get('message')}'"
    )

    # =========================================================================
    # AREA 4: TENANT ISOLATION ATTACK TESTS (USER A vs USER B)
    # =========================================================================
    # User A is Demo User (Alex Chen: 208 transactions, ₹750,000.00 income)
    demo_client = AuditClient()
    demo_client.request("POST", "/api/v1/auth/login", body={
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD
    }, include_cookie=False)

    # User B is Alice (Newly created, 0 transactions, ₹0.00 income)
    # Alice attempts cross-tenant manipulation across all endpoints:

    # 4.1 Dashboard Summary: Alice sends user_id=usr_demo_synthetic_01 in Query
    status, body, _ = alice_client.request(
        "GET",
        "/api/v1/dashboard/summary?user_id=usr_demo_synthetic_01",
        include_cookie=True,
        include_csrf=True
    )
    record(
        "Tenant isolation",
        "Dashboard Query Param Spoofing Prevented",
        status == 200 and body.get("total_transactions") == 0 and body.get("total_income") == 0.0,
        f"Alice's transactions: {body.get('total_transactions')} (Demo user has 208). Gateway enforced Alice's session ID."
    )

    # 4.2 Transactions List: Alice sends user_id=usr_demo_synthetic_01 in Query
    status, body, _ = alice_client.request(
        "GET",
        "/api/v1/transactions?user_id=usr_demo_synthetic_01&limit=50",
        include_cookie=True,
        include_csrf=True
    )
    record(
        "Tenant isolation",
        "Transactions Query Param Spoofing Prevented",
        status == 200 and body.get("count") == 0 and len(body.get("transactions", [])) == 0,
        f"Alice retrieved {body.get('count')} transactions (Demo ledger inaccessible)."
    )

    # 4.3 AI Chat: Alice sends user_id=usr_demo_synthetic_01 in JSON Body
    status, body, _ = alice_client.request(
        "POST",
        "/api/v1/ai/chat",
        body={
            "message": "List my salary transactions and monthly rent payments",
            "user_id": "usr_demo_synthetic_01" # Attempt to hijack Demo User ledger
        },
        include_cookie=True,
        include_csrf=True
    )
    # Since Alice has 0 transactions, the AI response will report no transactions found or 0 income, NOT Demo User's salary
    chat_resp = (body.get("answer") or body.get("response", "")).lower()
    alice_isolated = "125,000" not in chat_resp and "32,000" not in chat_resp
    record(
        "Tenant isolation",
        "AI Chat Body Spoofing Prevented",
        status == 200 and alice_isolated,
        f"Response correctly reflects Alice's empty ledger: '{(body.get('answer') or body.get('response', ''))[:90]}...'"
    )

    # 4.4 Semantic Search: Alice sends user_id=usr_demo_synthetic_01 in JSON Body
    status, body, _ = alice_client.request(
        "POST",
        "/api/v1/ai/search",
        body={
            "query": "salary payroll monthly transfer groceries",
            "user_id": "usr_demo_synthetic_01",
            "limit": 5
        },
        include_cookie=True,
        include_csrf=True
    )
    record(
        "Tenant isolation",
        "Semantic Search Body Spoofing Prevented",
        status == 200 and body.get("total_results") == 0,
        f"Alice vector results: {body.get('total_results')} (Demo user 208 embeddings not leaked)."
    )

    # 4.5 Anomalies & Insights Query Param Spoofing
    status_anom, body_anom, _ = alice_client.request("GET", "/api/v1/anomalies?user_id=usr_demo_synthetic_01", include_cookie=True)
    status_ins, body_ins, _ = alice_client.request("GET", "/api/v1/insights?user_id=usr_demo_synthetic_01", include_cookie=True)
    record(
        "Tenant isolation",
        "Anomalies & Insights Query Spoofing Prevented",
        status_anom == 200 and body_anom.get("total_anomalies") == 0 and status_ins == 200 and len(body_ins.get("insights", [])) == 0,
        f"Alice anomalies: {body_anom.get('total_anomalies')}, Alice insights: {len(body_ins.get('insights', []))}"
    )

    # =========================================================================
    # AREA 5: RATE LIMITING & REQUEST HARDENING
    # =========================================================================
    # 5.1 Request Body Size Limit (2 MB max configured via RequestBodyLimitLayer)
    # Send a payload > 2.5 MB to test 413 Payload Too Large
    oversized_payload = {"dummy": "A" * (2600000)}
    status, body, _ = client.request("POST", "/api/v1/auth/login", body=oversized_payload, include_cookie=False)
    record(
        "Request limits/timeouts",
        "Payload Body Size Limit Enforced (413 Payload Too Large)",
        status == 413,
        f"Status: {status} on 2.6 MB request payload"
    )

    # 5.2 Login Rate Limiting (10 requests per minute per IP)
    # Send 12 rapid requests from fixed IP to trigger 429
    rate_client = AuditClient(client_ip="198.51.100.42")
    rate_triggered = False
    rate_status = 200
    for i in range(15):
        st, b, _ = rate_client.request("POST", "/api/v1/auth/login", body={
            "email": "rate_test@finsight.internal",
            "password": "WrongPassword!"
        }, include_cookie=False)
        if st == 429:
            rate_triggered = True
            rate_status = st
            break
    record(
        "Rate limiting",
        "Login Brute Force Rate Limiting Enforced (429 Too Many Requests)",
        rate_triggered,
        f"Rapid login sequence returned HTTP {rate_status} (Too Many Requests)"
    )

    # =========================================================================
    # AREA 6: DATABASE INTEGRITY & CLEANUP
    # =========================================================================
    # Clean up test user Alice: deleting Alice must cascade-delete all her sessions
    sessions_before = run_db2_sql(f"SELECT count(*) FROM FINSIGHT.USER_SESSIONS WHERE user_id = '{alice_user.get('user_id')}'")
    run_db2_sql(f"DELETE FROM FINSIGHT.USERS WHERE user_id = '{alice_user.get('user_id')}'")
    sessions_after = run_db2_sql(f"SELECT count(*) FROM FINSIGHT.USER_SESSIONS WHERE user_id = '{alice_user.get('user_id')}'")

    record(
        "Db2 migration integrity",
        "User Deletion Cascades to Sessions (No Orphans)",
        sessions_after.strip() == "0",
        f"Sessions before deletion: {sessions_before.strip()}, Sessions after deletion: {sessions_after.strip()}"
    )

    print("\n" + "=" * 80)
    passed_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = len(results)
    print(f"       Security Audit Summary: {passed_count}/{total_count} Checks Passed")
    print("=" * 80)
    return results

if __name__ == "__main__":
    res = run_audit()
    all_ok = all(r["status"] == "PASS" for r in res)
    sys.exit(0 if all_ok else 1)
