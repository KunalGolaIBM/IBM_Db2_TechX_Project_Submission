"""
ClaimGuard AI - LangGraph Multi-Agent Workflow Tests
Tests end-to-end orchestration, graph state propagation across all 5 nodes,
audit trail creation, and FastAPI verification endpoints.
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.agents.workflow import run_claim_verification, claimguard_orchestrator
from backend.database.repository import repository

client = TestClient(app)


def test_langgraph_orchestrator_compilation():
    """Verify LangGraph workflow compiles successfully with all required nodes."""
    assert claimguard_orchestrator is not None


def test_langgraph_full_claim_verification():
    """Verify end-to-end multi-agent execution on a seeded claim."""
    # Seed a test claim
    test_claim = {
        "CLAIM_ID": "CLM-LG-001",
        "POLICY_ID": "POL-1001",
        "CUSTOMER_ID": "CUST-001",
        "CLAIM_NUMBER": "CLM-LG-NUM-101",
        "INCIDENT_DATE": "2026-08-10",
        "ADMISSION_DATE": "2026-08-10",
        "DISCHARGE_DATE": "2026-08-14",
        "CLAIM_AMOUNT": 38000.0,
        "HOSPITAL_NAME": "Medanta The Medicity",
        "HOSPITAL_INVOICE_NUMBER": "INV-LG-8891",
        "DIAGNOSIS_CODE": "K29.0",
        "DIAGNOSIS_DESCRIPTION": "Acute gastritis"
    }
    repository.create_claim(test_claim)

    final_state = run_claim_verification("CLM-LG-001")
    assert final_state["completed"] is True
    assert final_state["current_step"] == "COMPLETED"
    assert "db_verification" in final_state
    assert final_state["db_verification"]["policy_exists"] is True
    assert "fraud_analysis" in final_state
    assert "decision_output" in final_state
    decision = final_state["decision_output"]
    assert "risk_score" in decision
    assert decision["recommendation"] in ("APPROVE", "INVESTIGATE", "REJECT")
    assert "human" in decision["disclaimer"].lower()


def test_api_verification_endpoint():
    """Verify POST /api/verification/{claim_id} triggers LangGraph workflow."""
    claim_id = "CLM-9001"
    response = client.post(f"/api/verification/{claim_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["claim_id"] == claim_id
    assert data["completed"] is True
    assert "decision_output" in data
    assert "db_verification" in data


def test_api_verification_status_get():
    """Verify GET /api/verification/{claim_id} returns verification history and logs."""
    claim_id = "CLM-9001"
    response = client.get(f"/api/verification/{claim_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == claim_id
    assert "risk_score" in data
    assert "audit_logs" in data
    assert isinstance(data["audit_logs"], list)


def test_api_verification_nonexistent_claim():
    """Verify 404 response on non-existent claim ID."""
    response = client.post("/api/verification/CLM-DOES-NOT-EXIST")
    assert response.status_code == 404
