"""
ClaimGuard AI - Decision Support Agent Tests
Tests transparent risk scoring (0-100), explainable rationale, recommendation mapping,
and human-in-the-loop disclaimers.
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from backend.agents.decision_agent import decision_agent
from backend.agents.state import (
    DbVerificationResult,
    DecisionResult,
    FraudAnalysisResult,
    FraudIndicator,
)


def test_decision_agent_clean_approval():
    """Verify clean claim receives low risk score and APPROVE recommendation."""
    claim_data = {"CLAIM_ID": "CLM-APP-001", "CLAIM_AMOUNT": 30000.0}
    db_res = DbVerificationResult(
        customer_exists=True,
        policy_exists=True,
        policy_active=True,
        policy_details={"DEDUCTIBLE": 5000.0},
        has_sufficient_coverage=True,
        max_coverage=500000.0,
        remaining_coverage=450000.0
    )
    fraud_res = FraudAnalysisResult(is_suspicious=False, indicators=[])

    res = decision_agent.evaluate(claim_data, db_res, fraud_res)
    assert isinstance(res, DecisionResult)
    assert res.risk_score <= 25.0
    assert res.risk_level == "LOW"
    assert res.recommendation == "APPROVE"
    assert res.recommended_approved_amount == 25000.0  # 30k minus 5k deductible
    assert res.human_review_required is True
    assert "human" in res.disclaimer.lower()


def test_decision_agent_critical_fraud_rejection():
    """Verify critical duplicate alerts cause score spike and REJECT recommendation."""
    claim_data = {"CLAIM_ID": "CLM-REJ-001", "CLAIM_AMOUNT": 85000.0}
    db_res = DbVerificationResult(
        customer_exists=True,
        policy_exists=True,
        policy_active=True,
        has_sufficient_coverage=True,
        max_coverage=500000.0,
        remaining_coverage=450000.0
    )
    fraud_res = FraudAnalysisResult(
        is_suspicious=True,
        duplicate_hash_found=True,
        indicators=[
            FraudIndicator(
                alert_type="DUPLICATE_DOCUMENT_HASH",
                severity="CRITICAL",
                description="Hash collision on existing claim.",
                risk_weight=45
            ),
            FraudIndicator(
                alert_type="DUPLICATE_INVOICE",
                severity="CRITICAL",
                description="Invoice number collision.",
                risk_weight=40
            )
        ]
    )

    res = decision_agent.evaluate(claim_data, db_res, fraud_res)
    assert res.risk_score >= 80.0
    assert res.risk_level == "CRITICAL"
    assert res.recommendation == "REJECT"
    assert res.recommended_approved_amount == 0.0
    assert len(res.key_factors) >= 2


def test_decision_agent_investigate_routing():
    """Verify moderate risk leads to INVESTIGATE recommendation with examiner escalation."""
    claim_data = {"CLAIM_ID": "CLM-INV-001", "CLAIM_AMOUNT": 120000.0}
    db_res = DbVerificationResult(
        customer_exists=True,
        policy_exists=True,
        policy_active=True,
        has_sufficient_coverage=False,  # Exceeded coverage!
        remaining_coverage=80000.0
    )
    fraud_res = FraudAnalysisResult(
        is_suspicious=True,
        indicators=[
            FraudIndicator(
                alert_type="UNUSUAL_AMOUNT",
                severity="MEDIUM",
                description="High billing for minor symptom.",
                risk_weight=20
            )
        ]
    )

    res = decision_agent.evaluate(claim_data, db_res, fraud_res)
    assert 25.0 < res.risk_score < 75.0
    assert res.recommendation == "INVESTIGATE"
    assert "manual review" in res.executive_summary.lower() or "examiner" in res.executive_summary.lower()
