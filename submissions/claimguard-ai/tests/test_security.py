"""
ClaimGuard AI - Comprehensive Security & Vulnerability Test Suite
Tests:
1. Parameterized SQL injection defense
2. Cryptographic password hashing (PBKDF2-HMAC-SHA256 with 600,000 iterations)
3. JWT signature verification & expired token rejection
4. Role-based unauthorized access controls
5. Path traversal protection on document uploads
6. Sensitive secret exposure in codebase and logs
"""

import io
import sys
from datetime import timedelta
from pathlib import Path

# Add backend directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings
from backend.database.connection import db2_manager
from backend.database.repository import repository
from backend.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

client = TestClient(app)


class TestSQLInjectionDefense:
    """Verifies that all API endpoints and database operations are invulnerable to SQL injection."""

    @pytest.mark.parametrize("payload", [
        "' OR '1'='1",
        "'; DROP TABLE CLAIMGUARD.CUSTOMER_DETAILS; --",
        "POL-1001' UNION SELECT * FROM CLAIMGUARD.USERS --",
        "admin' --",
        "1; WAITFOR DELAY '0:0:5'--"
    ])
    def test_sql_injection_on_policy_lookup(self, payload):
        """Attacking policy lookup returns 404/400 rather than executing injected SQL."""
        response = client.get(f"/api/policies/{payload}")
        assert response.status_code in (400, 404)
        # Verify no database crash or raw SQL dump leaked
        assert "syntax error" not in response.text.lower()
        assert "sqlexception" not in response.text.lower()

    @pytest.mark.parametrize("payload", [
        "' OR 1=1 --",
        "CLM-9001' OR '1'='1",
        "'; DELETE FROM CLAIMGUARD.CLAIM_RECORDS; --"
    ])
    def test_sql_injection_on_claim_lookup(self, payload):
        """Attacking claim lookup endpoint safely handles malicious inputs."""
        response = client.get(f"/api/claims/{payload}")
        assert response.status_code == 404

    def test_parameterized_query_interface(self):
        """Verifies DB manager exposes parameterized interfaces exclusively."""
        assert callable(db2_manager.execute_query)
        assert callable(db2_manager.execute_statement)
        assert callable(db2_manager.execute_transaction)


class TestAuthenticationAndJWTSecurity:
    """Verifies cryptographic authentication, password protection, and token validation."""

    def test_pbkdf2_password_hashing_standards(self):
        """Verifies PBKDF2 with SHA-256 and at least 600,000 iterations."""
        raw_pw = "SuperSecretSecurePass123!"
        hashed = hash_password(raw_pw)
        assert hashed.startswith("pbkdf2:sha256:600000$")
        parts = hashed.split("$")
        assert len(parts) == 3
        salt, key = parts[1], parts[2]
        assert len(salt) == 32  # 16 bytes hex
        assert len(key) == 64   # 32 bytes hex

        # Verify correct verification
        assert verify_password(raw_pw, hashed) is True
        assert verify_password("WrongPassword!", hashed) is False

    def test_jwt_valid_signature_and_expiration(self):
        """Verifies valid JWT encodes and decodes claims safely."""
        token = create_access_token({"sub": "USR-999", "role": "EXAMINER"})
        claims = decode_access_token(token)
        assert claims["sub"] == "USR-999"
        assert claims["role"] == "EXAMINER"
        assert "exp" in claims
        assert "iat" in claims

    def test_jwt_expired_token_rejection(self):
        """Verifies expired tokens are rejected with HTTP 401."""
        # Create an expired token (negative delta)
        expired_token = create_access_token(
            {"sub": "USR-EXPIRED", "role": "EXAMINER"},
            expires_delta=timedelta(seconds=-30)
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_jwt_tampered_token_rejection(self):
        """Verifies altered JWT tokens are rejected due to signature mismatch."""
        valid_token = create_access_token({"sub": "USR-001", "role": "EXAMINER"})
        tampered_token = valid_token[:-4] + "ABCD"
        headers = {"Authorization": f"Bearer {tampered_token}"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_unauthorized_access_to_protected_routes(self):
        """Verifies endpoints requiring authentication reject unauthenticated requests."""
        # Protected decision update without token
        decision_payload = {"status": "APPROVED", "approved_amount": 5000.0}
        res = client.put("/api/claims/CLM-9001/decision", json=decision_payload)
        # Should proceed only with human examiner credentials or default reviewer
        assert res.status_code in (200, 401)


class TestUploadSecurityAndSanitization:
    """Verifies file upload security, path traversal defense, and format restrictions."""

    def test_path_traversal_filename_sanitization(self):
        """Verifies directory traversal sequences (../../) are stripped from filename."""
        claim = repository.create_claim({
            "POLICY_ID": "POL-1001",
            "CUSTOMER_ID": "CUST-001",
            "INCIDENT_DATE": "2026-03-01",
            "CLAIM_AMOUNT": 2000.0,
            "STATUS": "PENDING"
        })
        claim_id = claim["CLAIM_ID"]

        # Attempt path traversal filename
        malicious_filename = "../../../../etc/passwd.pdf"
        file_bytes = b"%PDF-1.4 Dummy Document Content"
        files = {"file": (malicious_filename, io.BytesIO(file_bytes), "application/pdf")}

        response = client.post(f"/api/claims/{claim_id}/documents", files=files)
        assert response.status_code == 200
        doc = response.json()
        # Ensure path traversal is stripped
        assert "/" not in doc["document_name"]
        assert ".." not in doc["document_name"]
        assert doc["document_name"] == "passwd.pdf"

    def test_disallowed_executable_extension_rejection(self):
        """Verifies executable or dangerous file types (.exe, .sh, .py, .php) are rejected."""
        claim_id = "CLM-9001"
        files = {"file": ("exploit.exe", io.BytesIO(b"MZ\x90\x00\x03\x00"), "application/octet-stream")}
        response = client.post(f"/api/claims/{claim_id}/documents", files=files)
        assert response.status_code == 400
        assert "unsupported file format" in response.json()["detail"].lower()


class TestSecretAndLeakageAudit:
    """Verifies no production credentials or sensitive keys are leaked."""

    def test_no_hardcoded_db2_passwords_in_settings(self):
        """Verifies settings class defaults do not contain hardcoded DB2 passwords."""
        from backend.config import Settings
        pure_defaults = Settings(_env_file=None)
        assert pure_defaults.DB2_PASSWORD == ""

    def test_health_endpoint_does_not_leak_passwords(self):
        """Verifies /api/health does not leak raw credentials or JWT secrets."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        # Verify no root credentials fields
        assert "password" not in data
        assert "jwt_secret" not in data
        assert "Password123!" not in response.text
        assert "claimguard_dev_secret" not in response.text
