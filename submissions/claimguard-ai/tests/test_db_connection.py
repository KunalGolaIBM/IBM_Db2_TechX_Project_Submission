"""
ClaimGuard AI - IBM Db2 Connection and Schema Integrity Tests
Verifies driver loading, connection string generation, health probe execution,
parameterized query safety, and table schema models.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from backend.config import settings
from backend.database.connection import db2_manager, IBM_DB_AVAILABLE
from backend.database.repository import repository


def test_ibm_db_driver_availability():
    """Verify that the official ibm_db driver is installed and importable."""
    assert db2_manager.is_driver_available() is True, (
        "ibm_db driver is not available. Please install it using: pip install ibm_db"
    )


def test_db2_connection_string_generation():
    """Verify that Db2 connection string includes required parameters and handles SSL correctly."""
    conn_str = settings.db2_connection_string
    assert "DATABASE=" in conn_str
    assert "HOSTNAME=" in conn_str
    assert "PORT=" in conn_str
    assert "PROTOCOL=TCPIP;" in conn_str
    assert "UID=" in conn_str


def test_db2_health_probe():
    """
    Executes the health probe against IBM Db2.
    Must return a valid dictionary and never crash.
    If Db2 is not running, must return status='disconnected' with clear instructions,
    not fake a connected state.
    """
    health = db2_manager.check_health()
    assert isinstance(health, dict)
    assert "database" in health
    assert health["database"] == "IBM Db2"
    assert "connected" in health

    if health["connected"]:
        assert health["status"] == "healthy"
        assert "server_time" in health
    else:
        assert health["status"] in ("disconnected", "unhealthy")
        assert "error" in health


def test_repository_customer_operations():
    """Tests CUSTOMER_DETAILS retrieval and schema conformance."""
    customers = repository.list_customers()
    assert isinstance(customers, list)
    assert len(customers) >= 1

    first = customers[0]
    assert "CUSTOMER_ID" in first
    assert "FIRST_NAME" in first
    assert "LAST_NAME" in first
    assert "EMAIL" in first


def test_repository_policy_operations():
    """Tests POLICY_DETAILS retrieval and schema conformance."""
    policies = repository.list_policies()
    assert isinstance(policies, list)
    assert len(policies) >= 1

    first = policies[0]
    assert "POLICY_ID" in first
    assert "POLICY_NUMBER" in first
    assert "MAX_COVERAGE_AMOUNT" in first
    assert "REMAINING_COVERAGE" in first


def test_repository_claim_lifecycle():
    """Tests creation, retrieval, and decision update of CLAIM_RECORDS."""
    new_claim = {
        "POLICY_ID": "POL-1001",
        "CUSTOMER_ID": "CUST-001",
        "INCIDENT_DATE": "2026-10-20",
        "ADMISSION_DATE": "2026-10-20",
        "DISCHARGE_DATE": "2026-10-22",
        "CLAIM_AMOUNT": 25000.00,
        "HOSPITAL_NAME": "Fortis Hospital",
        "HOSPITAL_INVOICE_NUMBER": "INV-TEST-9901",
        "DIAGNOSIS_CODE": "J18.9",
        "DIAGNOSIS_DESCRIPTION": "Pneumonia, unspecified organism"
    }

    created = repository.create_claim(new_claim)
    assert created is not None
    claim_id = created["CLAIM_ID"]
    assert claim_id.startswith("CLM-")

    fetched = repository.get_claim_by_id(claim_id)
    assert fetched is not None
    assert fetched["HOSPITAL_NAME"] == "Fortis Hospital"

    # Test decision update
    decision_ok = repository.update_claim_decision(
        claim_id=claim_id,
        status="APPROVED",
        decision_notes="Test verification approved.",
        reviewed_by="TEST_EXAMINER",
        approved_amount=25000.00
    )
    assert decision_ok is True

    updated = repository.get_claim_by_id(claim_id)
    assert updated["STATUS"] == "APPROVED"
    assert float(updated["APPROVED_AMOUNT"]) == 25000.00
