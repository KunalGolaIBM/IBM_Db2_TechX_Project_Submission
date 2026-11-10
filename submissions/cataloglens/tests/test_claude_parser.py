"""
Tests for Claude Client and Deterministic Heuristic Engine Fallback.
"""
import pytest
from backend.db.sample_catalog import get_sample_enterprise_metadata
from backend.services.relationship_detector import RelationshipDetector
from backend.agents.claude_client import ClaudeClient
from backend.models.analysis import TableUnderstanding


def test_deterministic_fallback_table_understanding():
    meta = get_sample_enterprise_metadata()
    table = meta.get_object("CUSTOMER_MST")
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)

    client = ClaudeClient()
    # Force deterministic fallback
    understanding = client._deterministic_explain_table(table, rels, "ENTERPRISE")

    assert isinstance(understanding, TableUnderstanding)
    assert understanding.table_name == "CUSTOMER_MST"
    assert "Master" in understanding.likely_business_purpose or "registered" in understanding.likely_business_purpose.lower()
    assert len(understanding.important_columns) == len(table.columns)
    assert len(understanding.evidence) > 0
    assert len(understanding.verification_questions) > 0
    assert understanding.is_ai_generated is False


def test_ambiguous_return_table_understanding():
    meta = get_sample_enterprise_metadata()
    table = meta.get_object("RETURN_HDR")
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)

    client = ClaudeClient()
    understanding = client._deterministic_explain_table(table, rels, "ENTERPRISE")

    assert understanding.table_name == "RETURN_HDR"
    # Should identify inferred relationships or uncertainties
    assert len(understanding.uncertainties) > 0
