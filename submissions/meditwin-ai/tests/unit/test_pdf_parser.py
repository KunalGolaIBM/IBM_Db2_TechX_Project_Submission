"""
Unit Tests: Document Validation & PyMuPDF Parser
"""

from pathlib import Path
from ingestion.pdf_parser import validate_file, parse_pdf, parse_text_file, parse_document


def test_valid_pdf_file_validation():
    valid, err = validate_file("report.pdf", b"%PDF-1.4 sample content", max_size_mb=10)
    assert valid is True
    assert err is None


def test_valid_txt_file_validation():
    valid, err = validate_file("notes.txt", b"Clinical notes text", max_size_mb=10)
    assert valid is True
    assert err is None


def test_disallowed_extension_rejected():
    for ext in [".exe", ".docx", ".csv", ".jpg", ".bin"]:
        valid, err = validate_file(f"file{ext}", b"data", max_size_mb=10)
        assert valid is False
        assert "Unsupported file type" in err


def test_oversized_file_rejected():
    large_bytes = b"0" * (11 * 1024 * 1024)
    valid, err = validate_file("large.pdf", large_bytes, max_size_mb=10)
    assert valid is False
    assert "File too large" in err


def test_empty_file_rejected():
    valid, err = validate_file("empty.pdf", b"", max_size_mb=10)
    assert valid is False
    assert "File is empty" in err


def test_synthetic_pdf_parsing():
    pdf_path = Path("sample_data/synthetic_reports/SyntheticReport_A_Oct2026.pdf")
    assert pdf_path.exists()
    doc = parse_pdf(pdf_path.name, pdf_path.read_bytes())
    assert doc.parse_status == "PARSED"
    assert doc.total_pages == 1
    assert len(doc.source_hash) == 64
    assert "HbA1c" in doc.full_text


def test_synthetic_pdf_page_mapping():
    pdf_path = Path("sample_data/synthetic_reports/SyntheticReport_B_Nov2026.pdf")
    doc = parse_document(pdf_path.name, pdf_path.read_bytes())
    assert doc.parse_status == "PARSED"
    assert len(doc.pages) == 1
    assert doc.pages[0].page_number == 1
    assert doc.pages[0].char_count > 100

