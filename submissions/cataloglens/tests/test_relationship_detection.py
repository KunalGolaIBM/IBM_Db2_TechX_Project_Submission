"""
Tests for Declared and Inferred Relationship Discovery.
"""
import pytest
from backend.db.sample_catalog import get_sample_enterprise_metadata
from backend.services.relationship_detector import RelationshipDetector
from backend.models.relationship import RelationshipType, VerificationStatus


def test_discover_declared_relationships():
    meta = get_sample_enterprise_metadata()
    detector = RelationshipDetector()
    edges = detector.discover_relationships(meta)

    declared = [e for e in edges if e.relationship_type == RelationshipType.DECLARED]
    assert len(declared) >= 10

    # Verify ORD_HDR -> CUSTOMER_MST
    ord_to_cust = next((e for e in declared if e.source_table == "ORD_HDR" and e.target_table == "CUSTOMER_MST"), None)
    assert ord_to_cust is not None
    assert ord_to_cust.source_column == "CUST_ID"
    assert ord_to_cust.target_column == "CUST_ID"
    assert ord_to_cust.confidence == 1.0
    assert ord_to_cust.verification_status == VerificationStatus.VERIFIED_FACT


def test_discover_inferred_relationships():
    meta = get_sample_enterprise_metadata()
    detector = RelationshipDetector()
    edges = detector.discover_relationships(meta)

    inferred = [e for e in edges if e.relationship_type == RelationshipType.INFERRED]
    assert len(inferred) >= 1

    # Verify RETURN_HDR -> ORD_HDR inference on ORDER_ID
    ret_to_ord = next((e for e in inferred if e.source_table == "RETURN_HDR" and e.target_table == "ORD_HDR"), None)
    assert ret_to_ord is not None
    assert ret_to_ord.source_column == "ORDER_ID"
    assert ret_to_ord.target_column == "ORDER_ID"
    assert ret_to_ord.confidence >= 0.90
    assert ret_to_ord.verification_status in (VerificationStatus.METADATA_SUPPORTED, VerificationStatus.HYPOTHESIS_UNVERIFIED)


def test_type_compatibility_check():
    detector = RelationshipDetector()
    assert detector.are_types_compatible("BIGINT", "BIGINT") is True
    assert detector.are_types_compatible("BIGINT", "INTEGER") is True
    assert detector.are_types_compatible("VARCHAR", "CHAR") is True
    assert detector.are_types_compatible("VARCHAR", "BIGINT") is False
