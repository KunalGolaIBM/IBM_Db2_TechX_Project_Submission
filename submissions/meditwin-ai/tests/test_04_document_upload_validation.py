"""
Test Category 4: Document Upload Validation Test
Validates file extension, size limits, and non-empty checks.
"""

from ingestion.pdf_parser import validate_file


def test_valid_pdf_file():
    """Valid PDF content passes validation."""
    valid, err = validate_file("report.pdf", b"%PDF-1.4 sample content", max_size_mb=10)
    assert valid is True
    assert err is None


def test_valid_txt_file():
    """Valid TXT content passes validation."""
    valid, err = validate_file("notes.txt", b"Clinical notes text", max_size_mb=10)
    assert valid is True
    assert err is None


def test_invalid_file_extension():
    """Disallowed file extensions are rejected."""
    for ext in [".exe", ".docx", ".csv", ".jpg", ".bin"]:
        valid, err = validate_file(f"file{ext}", b"data", max_size_mb=10)
        assert valid is False
        assert "Unsupported file type" in err


def test_file_size_exceeded():
    """Files exceeding maximum size are rejected."""
    large_bytes = b"0" * (11 * 1024 * 1024)  # 11 MB
    valid, err = validate_file("report.pdf", large_bytes, max_size_mb=10)
    assert valid is False
    assert "File too large" in err


def test_empty_file_rejected():
    """Empty files are rejected."""
    valid, err = validate_file("empty.pdf", b"", max_size_mb=10)
    assert valid is False
    assert "File is empty" in err

