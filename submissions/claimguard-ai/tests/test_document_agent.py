"""
ClaimGuard AI - Document Extraction Agent Tests
Tests document text extraction, LangChain Gemini invocation, and Pydantic validation.
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

import pytest
from backend.agents.document_agent import document_agent
from backend.agents.state import ExtractedDocumentData


def test_document_agent_initialization():
    """Verify document agent initializes with LangChain model configuration."""
    assert document_agent.model_name is not None
    assert isinstance(document_agent.model_name, str)


def test_document_agent_deterministic_fallback():
    """Verify regex-based fallback extraction extracts structured fields and validates with Pydantic."""
    sample_text = """
    APOLLO HOSPITALS LUCKNOW
    INVOICE NUMBER: INV-MED-9941
    Date of Admission: 2026-10-10
    Date of Discharge: 2026-10-14
    Patient: Rajesh Kumar
    Diagnosis: Acute Gastroenteritis (ICD-10: A09)
    Total Amount: INR 48,500.00
    """
    res = document_agent._rule_based_fallback_extract(sample_text, "apollo_bill.pdf")
    assert isinstance(res, ExtractedDocumentData)
    assert res.total_amount == 48500.0
    assert res.hospital_invoice_number == "INV-MED-9941"
    assert res.admission_date == "2026-10-10"
    assert res.discharge_date == "2026-10-14"
    assert res.currency == "INR"


def test_document_agent_empty_file_handling(tmp_path):
    """Verify graceful handling when an empty file is passed."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    res = document_agent.extract(str(empty_file))
    assert isinstance(res, ExtractedDocumentData)
    assert res.hospital_invoice_number is not None
