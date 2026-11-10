"""
Test Category 5: PDF Extraction Test
Validates PyMuPDF extraction, page count preservation, and text extraction.
"""

from pathlib import Path
from ingestion.pdf_parser import parse_pdf, parse_text_file, parse_document


def test_parse_synthetic_pdf():
    """Verify text is extracted page by page from sample report."""
    pdf_path = Path("sample_data/synthetic_reports/SyntheticReport_A_Oct2026.pdf")
    assert pdf_path.exists(), "Sample PDF must exist"

    file_bytes = pdf_path.read_bytes()
    doc = parse_pdf(pdf_path.name, file_bytes)

    assert doc.parse_status == "PARSED"
    assert doc.total_pages >= 1
    assert len(doc.pages) == doc.total_pages
    assert doc.pages[0].page_number == 1
    assert "HbA1c" in doc.full_text or "Hemoglobin" in doc.full_text
    assert len(doc.source_hash) == 64  # SHA-256


def test_parse_text_document():
    """Verify plain text document parsing."""
    text_bytes = b"Patient: Demo Alpha\nReport Date: 2026-10-12\nHbA1c: 6.4%"
    doc = parse_text_file("notes.txt", text_bytes)

    assert doc.parse_status == "PARSED"
    assert doc.total_pages == 1
    assert "HbA1c" in doc.full_text


def test_unified_parse_document_dispatcher():
    """Verify parse_document correctly dispatches based on extension."""
    pdf_path = Path("sample_data/synthetic_reports/SyntheticReport_B_Nov2026.pdf")
    doc = parse_document(pdf_path.name, pdf_path.read_bytes())
    assert doc.parse_status == "PARSED"

