"""
ClaimGuard AI - Fraud Detection Agent Tests
Tests duplicate hash matching, invoice collision detection, date anomalies, and alert creation.
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from backend.agents.fraud_agent import fraud_agent
from backend.agents.state import FraudAnalysisResult
from backend.database.repository import repository


def test_fraud_agent_clean_claim():
    """Verify clean claim produces zero high or critical fraud alerts."""
    claim_data = {
        "CLAIM_ID": "CLM-CLEAN-001",
        "HOSPITAL_INVOICE_NUMBER": "INV-UNIQUE-8877",
        "CLAIM_AMOUNT": 30000.0,
        "ADMISSION_DATE": "2026-10-01",
        "DISCHARGE_DATE": "2026-10-04",
        "INCIDENT_DATE": "2026-10-01",
        "DIAGNOSIS_CODE": "J18.9"
    }
    docs = [{"DOCUMENT_NAME": "bill.pdf", "FILE_HASH": "unique_hash_9876543210"}]
    res = fraud_agent.analyze(claim_data, docs)
    assert isinstance(res, FraudAnalysisResult)
    assert res.is_suspicious is False
    assert len(res.indicators) == 0


def test_fraud_agent_duplicate_invoice_collision():
    """Verify duplicate invoice number used on a different claim is flagged as CRITICAL."""
    # Pre-seed a claim with invoice INV-COLLIDE-99
    existing_claim = {
        "CLAIM_ID": "CLM-SEED-INV",
        "POLICY_ID": "POL-1001",
        "CUSTOMER_ID": "CUST-001",
        "CLAIM_NUMBER": "CLM-SEED-01",
        "HOSPITAL_INVOICE_NUMBER": "INV-COLLIDE-99",
        "CLAIM_AMOUNT": 40000.0,
        "INCIDENT_DATE": "2026-09-01"
    }
    repository.create_claim(existing_claim)

    new_claim = {
        "CLAIM_ID": "CLM-NEW-002",
        "HOSPITAL_INVOICE_NUMBER": "INV-COLLIDE-99",  # Collision!
        "CLAIM_AMOUNT": 40000.0,
        "ADMISSION_DATE": "2026-10-01",
        "DISCHARGE_DATE": "2026-10-04",
        "INCIDENT_DATE": "2026-10-01"
    }
    res = fraud_agent.analyze(new_claim, [])
    assert res.is_suspicious is True
    assert res.duplicate_invoice_found is True
    assert any(i.alert_type == "DUPLICATE_INVOICE" and i.severity == "CRITICAL" for i in res.indicators)


def test_fraud_agent_date_anomaly():
    """Verify discharge before admission date is flagged as HIGH severity anomaly."""
    anomalous_claim = {
        "CLAIM_ID": "CLM-DATE-ANOMALY",
        "HOSPITAL_INVOICE_NUMBER": "INV-UNIQUE-3321",
        "CLAIM_AMOUNT": 25000.0,
        "ADMISSION_DATE": "2026-10-15",
        "DISCHARGE_DATE": "2026-10-10",  # Discharged 5 days before admission!
        "INCIDENT_DATE": "2026-10-10"
    }
    res = fraud_agent.analyze(anomalous_claim, [])
    assert res.is_suspicious is True
    assert res.date_anomaly_found is True
    assert any(i.alert_type == "DATE_ANOMALY" and i.severity == "HIGH" for i in res.indicators)


def test_fraud_agent_duplicate_document_hash():
    """Verify cryptographic SHA-256 hash collision triggers DUPLICATE_DOCUMENT_HASH alert."""
    test_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    # Ensure parent claim exists to satisfy IBM Db2 FK constraint FK_DOC_CLAIM
    repository.create_claim({
        "CLAIM_ID": "CLM-DOC-FIRST",
        "POLICY_ID": "POL-1001",
        "CUSTOMER_ID": "CUST-001",
        "CLAIM_NUMBER": "CLM-DOC-01",
        "INCIDENT_DATE": "2026-09-01",
        "CLAIM_AMOUNT": 20000.0,
        "STATUS": "PENDING"
    })
    doc1 = {
        "CLAIM_ID": "CLM-DOC-FIRST",
        "DOCUMENT_NAME": "original_receipt.pdf",
        "DOCUMENT_TYPE": "MEDICAL_BILL",
        "FILE_PATH": "/tmp/orig.pdf",
        "FILE_HASH": test_hash,
        "FILE_SIZE_BYTES": 1024,
        "MIME_TYPE": "application/pdf"
    }
    repository.create_document(doc1)

    claim_data = {"CLAIM_ID": "CLM-DOC-SECOND", "CLAIM_AMOUNT": 20000.0}
    docs = [{"DOCUMENT_NAME": "copied_receipt.pdf", "FILE_HASH": test_hash}]

    res = fraud_agent.analyze(claim_data, docs)
    assert res.is_suspicious is True
    assert res.duplicate_hash_found is True
    assert any(i.alert_type == "DUPLICATE_DOCUMENT_HASH" for i in res.indicators)
