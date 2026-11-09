"""
ClaimGuard AI - Basic API Test Suite
Tests FastAPI routing, health check endpoints, Pydantic validation, and claims endpoints.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root discovery endpoint returns project details."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "ClaimGuard AI"
    assert "Nitesh Barnwal" in data["author"]
    assert data["hackathon"] == "IBM Db2Hack 2026"


def test_health_endpoint():
    """Verify /api/health endpoint structure and database status reporting."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["app_name"] == "ClaimGuard AI"
    assert "database" in data
    assert data["database"]["database"] == "IBM Db2"


def test_db_health_endpoint():
    """Verify /api/db/health endpoint provides Db2 connection details."""
    response = client.get("/api/db/health")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert "database" in data


def test_list_customers():
    """Verify customer listing."""
    response = client.get("/api/customers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_policies():
    """Verify policy listing."""
    response = client.get("/api/policies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_claim_submission_and_retrieval():
    """Verify POST /api/claims and GET /api/claims/{claim_id}."""
    payload = {
        "policy_id": "POL-1001",
        "customer_id": "CUST-001",
        "incident_date": "2026-10-25",
        "admission_date": "2026-10-25",
        "discharge_date": "2026-10-28",
        "claim_amount": 45000.0,
        "hospital_name": "City Care Hospital",
        "hospital_invoice_number": "INV-API-TEST-101",
        "diagnosis_code": "K29.7",
        "diagnosis_description": "Gastritis, unspecified"
    }

    create_res = client.post("/api/claims", json=payload)
    assert create_res.status_code == 201
    claim = create_res.json()
    assert "claim_id" in claim
    claim_id = claim["claim_id"]

    # Retrieve details
    detail_res = client.get(f"/api/claims/{claim_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert "claim" in detail_data
    assert "policy" in detail_data
    assert detail_data["claim"]["hospital_name"] == "City Care Hospital"


def test_dashboard_stats():
    """Verify dashboard statistics aggregate calculations."""
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_claims" in data
    assert "total_claimed_amount" in data
    assert "db2_connected" in data
    assert data["total_claims"] >= 1


def test_auth_and_decision_flow():
    """Verify examiner authentication and claim decision adjudication."""
    login_res = client.post("/api/auth/login", json={"username": "examiner", "password": "examiner123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Verify /api/auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "examiner"

    # Submit decision on claim
    decision_payload = {
        "status": "APPROVED",
        "decision_notes": "Adjudication approved by examiner.",
        "approved_amount": 40000.0
    }
    dec_res = client.put(
        "/api/claims/CLM-9001/decision",
        json=decision_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "APPROVED"

    # Verify report endpoint
    rep_res = client.get("/api/reports/CLM-9001")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert "risk_assessment" in rep_data

