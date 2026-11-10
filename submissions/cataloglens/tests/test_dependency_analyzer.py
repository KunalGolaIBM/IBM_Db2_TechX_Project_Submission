"""
Tests for Dependency Investigation and Impact Severity.
"""
import pytest
from backend.db.sample_catalog import get_sample_enterprise_metadata
from backend.services.relationship_detector import RelationshipDetector
from backend.services.dependency_analyzer import DependencyAnalyzer


def test_investigate_central_table_dependency():
    meta = get_sample_enterprise_metadata()
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)
    analyzer = DependencyAnalyzer(meta, rels)

    # Investigating ORD_HDR (central table with many downstream dependents)
    inv = analyzer.investigate("ORD_HDR")
    assert inv.target_object == "ORD_HDR"
    assert inv.object_type == "TABLE"
    assert inv.impact_severity in ("HIGH", "CRITICAL")
    assert len(inv.direct_dependencies) > 0
    # ORD_LINE, PAYMENT_TXN, SHIPMENT_HDR should depend on ORD_HDR
    dependent_entities = [d.entity for d in inv.direct_dependencies]
    assert "ORD_LINE" in dependent_entities or "PAYMENT_TXN" in dependent_entities


def test_investigate_column_dependency():
    meta = get_sample_enterprise_metadata()
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)
    analyzer = DependencyAnalyzer(meta, rels)

    inv = analyzer.investigate("CUSTOMER_MST.CUST_ID")
    assert inv.target_object == "CUSTOMER_MST.CUST_ID"
    assert inv.object_type == "COLUMN"
    assert inv.impact_severity in ("HIGH", "CRITICAL")
    assert len(inv.recommended_manual_checks) > 0


def test_investigate_nonexistent_table():
    meta = get_sample_enterprise_metadata()
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)
    analyzer = DependencyAnalyzer(meta, rels)

    inv = analyzer.investigate("GHOST_TABLE")
    assert inv.impact_severity == "LOW"
    assert len(inv.direct_dependencies) == 0
