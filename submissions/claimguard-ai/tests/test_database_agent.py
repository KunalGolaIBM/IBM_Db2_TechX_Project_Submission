"""
ClaimGuard AI - Database Verification Agent Tests
Tests policy verification, remaining coverage checking, date validation, and Db2 queries.
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from backend.agents.database_agent import database_agent
from backend.agents.state import DbVerificationResult


def test_database_agent_valid_claim():
    """Verify standard valid policy coverage and date checks pass."""
    claim_data = {
        "CLAIM_ID": "CLM-TEST-001",
        "CUSTOMER_ID": "CUST-001",
        "POLICY_ID": "POL-1001",
        "CLAIM_AMOUNT": 50000.0,
        "INCIDENT_DATE": "2026-06-15"
    }
    res = database_agent.verify(claim_data)
    assert isinstance(res, DbVerificationResult)
    assert res.customer_exists is True
    assert res.policy_exists is True
    assert res.policy_active is True
    assert res.has_sufficient_coverage is True
    assert res.start_date_valid is True
    assert res.end_date_valid is True
    assert len(res.discrepancies) == 0


def test_database_agent_exceeded_coverage():
    """Verify when claim exceeds remaining coverage, discrepancy is flagged."""
    claim_data = {
        "CLAIM_ID": "CLM-TEST-002",
        "CUSTOMER_ID": "CUST-001",
        "POLICY_ID": "POL-1001",
        "CLAIM_AMOUNT": 9999999.0,  # Far exceeds 420,000 remaining limit
        "INCIDENT_DATE": "2026-06-15"
    }
    res = database_agent.verify(claim_data)
    assert res.has_sufficient_coverage is False
    assert any("exceeds policy remaining coverage" in d for d in res.discrepancies)


def test_database_agent_expired_or_invalid_dates():
    """Verify date outside policy coverage window is flagged."""
    claim_data = {
        "CLAIM_ID": "CLM-TEST-003",
        "CUSTOMER_ID": "CUST-001",
        "POLICY_ID": "POL-1001",
        "CLAIM_AMOUNT": 20000.0,
        "INCIDENT_DATE": "2028-12-31"  # Policy ends in 2026
    }
    res = database_agent.verify(claim_data)
    assert res.end_date_valid is False
    assert any("occurred after policy expiry" in d for d in res.discrepancies)
