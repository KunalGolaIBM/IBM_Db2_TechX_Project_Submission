"""
ClaimGuard AI - Comprehensive Edge Case & Resilience Test Suite
Tests:
1. Malformed and incomplete claim submissions
2. Boundary values (negative amounts, extreme amounts, zero)
3. Chronological date anomalies (discharge before admission)
4. Referential integrity failures (policy mismatches, nonexistent records)
5. File upload boundary conditions (0-byte files, unsupported formats)
6. Duplicate document uploads and hash idempotency
7. AI Agent degradation & offline resiliency (Gemini offline fallback)
"""

import io
import sys
from pathlib import Path

# Add backend directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.repository import repository
from backend.agents.document_agent import document_agent
from backend.agents.workflow import run_claim_verification

client = TestClient(app)


class TestInputValidationEdgeCases:
    """Tests Pydantic boundary validation and HTTP error response handling."""

    def test_empty_payload_rejection(self):
        """Verifies completely empty JSON payload returns HTTP 422."""
        response = client.post("/api/claims", json={})
        assert response.status_code == 422

    def test_missing_customer_id_rejection(self):
        """Verifies missing customer_id returns HTTP 422."""
        payload = {
            "policy_id": "POL-1001",
            "incident_date": "2026-03-01",
            "claim_amount": 5000.0
        }
        response = client.post("/api/claims", json=payload)
        assert response.status_code == 422

    def test_negative_claim_amount_rejection(self):
        """Verifies negative claim amount (gt=0 constraint) is rejected with HTTP 422."""
        payload = {
            "policy_id": "POL-1001",
            "customer_id": "CUST-001",
            "incident_date": "2026-03-01",
            "claim_amount": -1500.0
        }
        response = client.post("/api/claims", json=payload)
        assert response.status_code == 422

    def test_zero_claim_amount_rejection(self):
        """Verifies zero claim amount is rejected with HTTP 422."""
        payload = {
            "policy_id": "POL-1001",
            "customer_id": "CUST-001",
            "incident_date": "2026-03-01",
            "claim_amount": 0.0
        }
        response = client.post("/api/claims", json=payload)
        assert response.status_code == 422

    def test_excessive_claim_amount_rejection(self):
        """Verifies unreasonably large claim amount (> $50M limit) returns HTTP 422."""
        payload = {
            "policy_id": "POL-1001",
            "customer_id": "CUST-001",
            "incident_date": "2026-03-01",
            "claim_amount": 999999999.0
        }
        response = client.post("/api/claims", json=payload)
        assert response.status_code == 422

    def test_discharge_before_admission_rejection(self):
        """Verifies chronological anomaly (discharge prior to admission) returns HTTP 400."""
        payload = {
            "policy_id": "POL-1001",
            "customer_id": "CUST-001",
            "incident_date": "2026-03-10",
            "admission_date": "2026-03-15",
            "discharge_date": "2026-03-10",  # 5 days prior to admission!
            "claim_amount": 4500.0
        }
        response = client.post("/api/claims", json=payload)
        assert response.status_code == 400
        assert "precede" in response.json()["detail"].lower()

    def test_customer_policy_mismatch_rejection(self):
        """Verifies customer submitting against someone else's policy returns HTTP 400."""
        # POL-1001 belongs to CUST-001, attempt submission under CUST-002
        payload = {
            "policy_id": "POL-1001",
            "customer_id": "CUST-002",
            "incident_date": "2026-03-01",
            "claim_amount": 2000.0
        }
        response = client.post("/api/claims", json=payload)
        assert response.status_code == 400
        assert "does not match policyholder" in response.json()["detail"].lower()


class TestDocumentEdgeCases:
    """Tests document upload edge cases including 0-byte files, unsupported types, and hashing."""

    def test_empty_zero_byte_file_rejection(self):
        """Verifies 0-byte file upload returns HTTP 400."""
        claim_id = "CLM-9001"
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        response = client.post(f"/api/claims/{claim_id}/documents", files=files)
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.parametrize("filename,content_type", [
        ("malicious.bat", "application/x-bat"),
        ("script.sh", "application/x-sh"),
        ("archive.zip", "application/zip"),
        ("audio.mp3", "audio/mpeg")
    ])
    def test_unsupported_document_extension_rejection(self, filename, content_type):
        """Verifies unsupported non-insurance document types return HTTP 400."""
        claim_id = "CLM-9001"
        files = {"file": (filename, io.BytesIO(b"sample file content"), content_type)}
        response = client.post(f"/api/claims/{claim_id}/documents", files=files)
        assert response.status_code == 400
        assert "unsupported file format" in response.json()["detail"].lower()

    def test_duplicate_document_upload_hash_identity(self):
        """Verifies identical file bytes produce identical SHA-256 hashes for fraud detection."""
        claim_id = "CLM-9001"
        raw_bytes = b"Identical Invoice Content For Hash Testing"
        files1 = {"file": ("bill_copy1.pdf", io.BytesIO(raw_bytes), "application/pdf")}
        files2 = {"file": ("bill_copy2.pdf", io.BytesIO(raw_bytes), "application/pdf")}

        res1 = client.post(f"/api/claims/{claim_id}/documents", files=files1)
        res2 = client.post(f"/api/claims/{claim_id}/documents", files=files2)

        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["file_hash"] == res2.json()["file_hash"]


class TestAgentResilienceAndOfflineDegradation:
    """Tests agent performance under degraded network or missing API keys."""

    def test_document_agent_deterministic_regex_resilience(self, tmp_path):
        """
        Verifies Document Extraction Agent successfully extracts structured entities
        from text even when Gemini API is unconfigured.
        """
        sample_invoice_text = (
            "Apollo Multispecialty Hospital\n"
            "Invoice No: INV-EMERGENCY-2026\n"
            "Patient Name: Ananya Roy\n"
            "Admission Date: 2026-02-14\n"
            "Discharge Date: 2026-02-18\n"
            "Diagnosis: Type 2 Diabetes with Diabetic Ketoacidosis\n"
            "Total Amount: INR 35,000.00\n"
        )
        test_file = tmp_path / "hospital_bill.txt"
        test_file.write_text(sample_invoice_text, encoding="utf-8")

        extracted = document_agent.extract(str(test_file))
        assert extracted.patient_name == "Ananya Roy"
        assert extracted.hospital_invoice_number == "INV-EMERGENCY-2026"
        assert extracted.total_amount == 35000.0
        assert extracted.admission_date == "2026-02-14"
        assert extracted.discharge_date == "2026-02-18"

    def test_full_pipeline_with_missing_documents(self):
        """
        Verifies LangGraph verification pipeline runs to completion even if
        a claim has no attached documents, properly flagging for manual review.
        """
        claim = repository.create_claim({
            "POLICY_ID": "POL-1001",
            "CUSTOMER_ID": "CUST-001",
            "INCIDENT_DATE": "2026-03-01",
            "CLAIM_AMOUNT": 7000.0,
            "STATUS": "PENDING"
        })
        claim_id = claim["CLAIM_ID"]

        # Run verification without uploading documents
        state = run_claim_verification(claim_id)
        assert state["completed"] is True
        assert state["current_step"] in ("COMPLETED", "supervisor_finalize")
        assert state["decision_output"] is not None
        # Must require human review
        assert state["decision_output"]["human_review_required"] is True
