"""
Tests for Evidence Ledger and Hallucination Rejection.
"""
import pytest
from backend.db.sample_catalog import get_sample_enterprise_metadata
from backend.services.evidence_service import EvidenceService
from backend.models.evidence import EvidenceClaim, EvidenceItem


def test_build_table_evidence_ledger():
    meta = get_sample_enterprise_metadata()
    svc = EvidenceService(meta)
    ledger = svc.build_table_evidence_ledger("CUSTOMER_MST")

    assert len(ledger) >= 2
    pk_claim = ledger[0]
    assert pk_claim.status == "verified_fact"
    assert pk_claim.confidence == 1.0
    assert "CUSTOMER_MST" in pk_claim.referenced_tables


def test_validate_valid_claim():
    meta = get_sample_enterprise_metadata()
    svc = EvidenceService(meta)

    claim = EvidenceClaim(
        claim="ORD_HDR contains customer reference",
        evidence=[EvidenceItem(source="SYSCAT.COLUMNS", observation="CUST_ID present", type="catalog_metadata")],
        confidence=0.90,
        status="ai_hypothesis",
        referenced_tables=["ORD_HDR"],
        referenced_columns=["ORD_HDR.CUST_ID"],
    )

    validated = svc.validate_claim(claim)
    assert validated.verified_by_engine is True
    assert len(validated.discrepancies) == 0
    assert validated.status == "metadata_supported"


def test_reject_hallucinated_table():
    meta = get_sample_enterprise_metadata()
    svc = EvidenceService(meta)

    # Claim referencing a non-existent table "NON_EXISTENT_AUDIT_LOG"
    claim = EvidenceClaim(
        claim="ORD_HDR logs to NON_EXISTENT_AUDIT_LOG",
        evidence=[],
        confidence=0.90,
        status="ai_hypothesis",
        referenced_tables=["ORD_HDR", "NON_EXISTENT_AUDIT_LOG"],
        referenced_columns=[],
    )

    validated = svc.validate_claim(claim)
    assert validated.verified_by_engine is False
    assert len(validated.discrepancies) > 0
    assert "NON_EXISTENT_AUDIT_LOG" in validated.discrepancies[0]
    assert validated.status == "unverified_assumption"
    assert validated.confidence < 0.50
