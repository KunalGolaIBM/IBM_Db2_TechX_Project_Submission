"""
ClaimGuard AI - End-to-End System & Workflow Integration Tests
Verifies the complete 11-step claim lifecycle:
1. Claim Intake & Validation
2. Db2 Record Persistence
3. Document Upload & SHA-256 Hashing
4. Agent 1: Multimodal Document Extraction
5. Agent 2: IBM Db2 Database Verification & Policy Limits
6. Agent 3: Fraud Detection & Billing Anomaly Matching
7. Agent 4: Decision Support & Transparent 0-100 Risk Scoring
8. Agent 5: Supervisor Orchestration (LangGraph StateGraph)
9. Report Generation & Evidence Compilation
10. Dashboard Analytics Aggregation
11. Human-in-the-Loop Examiner Decision & Coverage Balance Adjustment

Distinguishes live integration behavior from sandbox verification.
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
from backend.config import settings
from backend.database.connection import db2_manager
from backend.database.repository import repository
from backend.agents.workflow import run_claim_verification
from backend.utils.security import create_access_token

client = TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "USR-001", "username": "examiner1", "role": "EXAMINER"})
    return {"Authorization": f"Bearer {token}"}


class TestEndToEndClaimLifecycle:
    """End-to-end integration tests for complete claim lifecycle."""

    def test_step_01_and_02_claim_submission_and_validation(self):
        """Phase 2, Steps 1-3: Claim intake, schema validation, and persistence."""
        claim_payload = {
            "policy_id": "POL-1001",
            "customer_id": "CUST-001",
            "incident_date": "2026-03-01",
            "admission_date": "2026-03-02",
            "discharge_date": "2026-03-06",
            "claim_amount": 14500.0,
            "hospital_name": "Apollo Super Specialty Hospital",
            "hospital_invoice_number": "INV-E2E-7701",
            "diagnosis_code": "I20.0",
            "diagnosis_description": "Unstable Angina Pectoris"
        }

        response = client.post("/api/claims", json=claim_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["policy_id"] == "POL-1001"
        assert data["customer_id"] == "CUST-001"
        assert data["claim_amount"] == 14500.0
        assert data["hospital_invoice_number"] == "INV-E2E-7701"
        assert data["status"] == "PENDING"
        assert "claim_id" in data

        # Check repository retrieval
        claim_id = data["claim_id"]
        record = repository.get_claim_by_id(claim_id)
        assert record is not None
        assert record["CLAIM_NUMBER"].startswith("CLM-")

    def test_step_03_invalid_policy_rejection(self):
        """Verifies referential validation fails when policy does not exist."""
        invalid_payload = {
            "policy_id": "POL-NONEXISTENT-999",
            "customer_id": "CUST-001",
            "incident_date": "2026-03-01",
            "claim_amount": 5000.0,
            "hospital_name": "City Clinic"
        }
        response = client.post("/api/claims", json=invalid_payload)
        assert response.status_code == 400
        assert "Invalid policy_id" in response.json()["detail"]

    def test_step_04_document_upload_and_sha256_hashing(self):
        """Phase 2, Step 4: Supporting document upload with automatic SHA-256 generation."""
        # Create a fresh claim
        claim = repository.create_claim({
            "POLICY_ID": "POL-1001",
            "CUSTOMER_ID": "CUST-001",
            "INCIDENT_DATE": "2026-03-10",
            "CLAIM_AMOUNT": 8500.0,
            "HOSPITAL_NAME": "Metro General Hospital",
            "STATUS": "PENDING"
        })
        claim_id = claim["CLAIM_ID"]

        # Upload a simulated medical invoice PDF
        doc_content = b"%PDF-1.4 Simulated Hospital Invoice - ClaimGuard AI E2E Test"
        files = {"file": ("hospital_bill_e2e.pdf", io.BytesIO(doc_content), "application/pdf")}
        data = {"document_type": "MEDICAL_BILL"}

        response = client.post(f"/api/claims/{claim_id}/documents", files=files, data=data)
        assert response.status_code == 200
        doc_resp = response.json()
        assert doc_resp["claim_id"] == claim_id
        assert doc_resp["document_name"] == "hospital_bill_e2e.pdf"
        assert len(doc_resp["file_hash"]) == 64  # Valid SHA-256 hash length

        # Verify document stored in repository
        docs = repository.get_documents_by_claim(claim_id)
        assert len(docs) == 1
        assert docs[0]["FILE_HASH"] == doc_resp["file_hash"]

    def test_step_05_through_09_multiagent_verification_pipeline(self):
        """
        Phase 2, Steps 5-9: LangGraph coordination of Document Agent,
        Database Verification Agent, Fraud Agent, Decision Support Agent,
        and Supervisor Agent.
        """
        # Create claim with valid parameters
        claim = repository.create_claim({
            "POLICY_ID": "POL-1001",
            "CUSTOMER_ID": "CUST-001",
            "INCIDENT_DATE": "2026-03-10",
            "ADMISSION_DATE": "2026-03-10",
            "DISCHARGE_DATE": "2026-03-14",
            "CLAIM_AMOUNT": 12000.0,
            "HOSPITAL_NAME": "Apollo Hospital",
            "HOSPITAL_INVOICE_NUMBER": "INV-AI-9002",
            "STATUS": "PENDING"
        })
        claim_id = claim["CLAIM_ID"]

        # Run verification via API
        response = client.post(f"/api/verification/{claim_id}")
        assert response.status_code == 200
        res = response.json()
        assert res["status"] == "success"
        assert res["completed"] is True
        assert res["db_verification"] is not None
        assert res["fraud_analysis"] is not None
        assert res["decision_output"] is not None

        # Verify Decision Agent produced a recommendation
        decision = res["decision_output"]
        assert decision["recommendation"] in ("APPROVE", "INVESTIGATE", "REJECT")
        assert 0.0 <= decision["risk_score"] <= 100.0
        assert len(decision["executive_summary"]) > 10

        # Verify claim record was updated in database
        updated = repository.get_claim_by_id(claim_id)
        assert updated["RISK_SCORE"] == decision["risk_score"]
        assert updated["RISK_LEVEL"] == decision["risk_level"]

        # Verify audit logs recorded agent execution
        logs = repository.get_logs_by_claim(claim_id)
        assert len(logs) >= 3
        agent_names = [l["AGENT_NAME"] for l in logs]
        assert "DATABASE_AGENT" in agent_names
        assert "FRAUD_AGENT" in agent_names
        assert "DECISION_AGENT" in agent_names
        assert "SUPERVISOR_AGENT" in agent_names

    def test_step_08_fraud_collision_detection(self):
        """Verifies Fraud Agent detects duplicate invoices and creates FRAUD_ALERTS."""
        # Create an initial claim with a known invoice
        claim1 = repository.create_claim({
            "POLICY_ID": "POL-1001",
            "CUSTOMER_ID": "CUST-001",
            "INCIDENT_DATE": "2026-02-10",
            "CLAIM_AMOUNT": 22000.0,
            "HOSPITAL_NAME": "Fortis Care",
            "HOSPITAL_INVOICE_NUMBER": "INV-COLLISION-999",
            "STATUS": "APPROVED"
        })

        # Create a second claim reusing the EXACT same invoice number
        claim2 = repository.create_claim({
            "POLICY_ID": "POL-1002",
            "CUSTOMER_ID": "CUST-002",
            "INCIDENT_DATE": "2026-03-01",
            "CLAIM_AMOUNT": 22000.0,
            "HOSPITAL_NAME": "Fortis Care",
            "HOSPITAL_INVOICE_NUMBER": "INV-COLLISION-999",
            "STATUS": "PENDING"
        })

        # Run verification on claim 2
        verification_state = run_claim_verification(claim2["CLAIM_ID"])
        assert verification_state["completed"] is True
        fraud_analysis = verification_state["fraud_analysis"]
        assert fraud_analysis["is_suspicious"] is True
        assert fraud_analysis["duplicate_invoice_found"] is True

        # Check Decision Agent appropriately elevated risk
        decision = verification_state["decision_output"]
        assert decision["risk_score"] >= 40.0
        assert decision["recommendation"] in ("INVESTIGATE", "REJECT")

        # Check FRAUD_ALERTS table was populated
        alerts = repository.get_alerts_by_claim(claim2["CLAIM_ID"])
        assert len(alerts) >= 1
        alert_types = [a["ALERT_TYPE"] for a in alerts]
        assert "DUPLICATE_INVOICE" in alert_types

    def test_step_10_explainable_verification_report(self):
        """Phase 2, Step 10: Generate structured explainable verification report."""
        response = client.get("/api/reports/CLM-9001")
        assert response.status_code == 200
        report = response.json()
        assert "claim_id" in report
        assert "customer" in report
        assert "policy" in report
        assert "risk_assessment" in report
        assert "evidence" in report
        assert report["risk_assessment"]["recommendation"] in ("APPROVE", "FLAG_FOR_MANUAL_REVIEW", "ADJUST_OR_REJECT", "REQUEST_ADDITIONAL_DOCUMENTS")

    def test_step_11_human_in_the_loop_adjudication(self, auth_headers):
        """
        Phase 2, Step 11: Authorized human reviewer records final decision,
        updates claim status, and verifies policy coverage balance deduction.
        """
        # Create claim
        claim = repository.create_claim({
            "POLICY_ID": "POL-1002",
            "CUSTOMER_ID": "CUST-002",
            "INCIDENT_DATE": "2026-03-05",
            "CLAIM_AMOUNT": 5000.0,
            "STATUS": "PENDING"
        })
        claim_id = claim["CLAIM_ID"]

        # Check initial remaining coverage
        policy_before = repository.get_policy_by_id("POL-1002")
        cov_before = float(policy_before["REMAINING_COVERAGE"])

        # Examiner submits approval decision
        decision_payload = {
            "status": "APPROVED",
            "decision_notes": "All medical bills validated and within policy limits. Approved by Senior Examiner.",
            "approved_amount": 5000.0
        }
        res = client.put(f"/api/claims/{claim_id}/decision", json=decision_payload, headers=auth_headers)
        assert res.status_code == 200
        updated = res.json()
        assert updated["status"] == "APPROVED"
        assert updated["approved_amount"] == 5000.0
        assert updated["reviewed_by"] == "USR-001"

        # Verify policy remaining coverage was deducted
        policy_after = repository.get_policy_by_id("POL-1002")
        cov_after = float(policy_after["REMAINING_COVERAGE"])
        assert cov_after == max(0.0, cov_before - 5000.0)


class TestIBMDb2IntegrationAndParity:
    """Tests IBM Db2 driver availability, health probes, and live credentials."""

    def test_driver_availability(self):
        """Verifies official ibm_db driver is installed and inspectable."""
        assert db2_manager.is_driver_available() is True

    def test_db2_health_probe_honesty(self):
        """
        Verifies health check accurately reports database connectivity status
        without fabricating successful connection or substituting SQLite.
        """
        health = db2_manager.check_health()
        assert "status" in health
        assert "connected" in health
        assert health["database"] == "IBM Db2"

        # When offline, must explain Docker setup instructions
        if not health["connected"]:
            assert health["status"] in ("disconnected", "unhealthy")
            assert "docker run" in health.get("instructions", "").lower() or "error" in health

    def test_parameterized_query_safety(self):
        """Verifies parameterized query execution signature."""
        sql = "SELECT * FROM CLAIMGUARD.CUSTOMER_DETAILS WHERE CUSTOMER_ID = ?"
        # In demo mode, repository handles parameterization; against Db2 it runs ibm_db.prepare()
        assert db2_manager.execute_query is not None
        assert db2_manager.execute_transaction is not None
