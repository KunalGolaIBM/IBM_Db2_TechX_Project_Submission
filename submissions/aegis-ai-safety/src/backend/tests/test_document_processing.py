"""Document validation, extraction, and chunking tests."""

from __future__ import annotations

import pytest

from app.core.errors import DocumentProcessingError, UploadValidationError
from app.services.document_processing import (
    chunk_text,
    chunk_text_with_offsets,
    process_text,
    process_upload,
    sanitize_filename,
)


def test_chunk_text_is_bounded_and_overlapping():
    text = " ".join(
        f"Sentence {index} reports a measured value of {index}% in the controlled trial."
        for index in range(120)
    )
    chunks = chunk_text(text, target_chars=400, overlap_chars=80)
    assert len(chunks) > 1
    assert all(len(chunk) <= 400 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_process_text_produces_stable_hash_and_pages():
    data = b"SolarCell-X achieved 92% efficiency. The trial was controlled."
    processed = process_text(data, title="Evidence")
    assert processed.title == "Evidence"
    assert processed.source_type == "text"
    assert len(processed.content_hash) == 64
    assert processed.passages[0][1] == 1
    assert "92%" in processed.passages[0][0]
    assert processed.passages[0][2] == 0
    assert processed.passages[0][3] is not None


def test_chunk_offsets_point_into_cleaned_text():
    text = "First sentence with 10% value. Second sentence with 20% value."
    chunks = chunk_text_with_offsets(text, target_chars=200)
    assert len(chunks) == 1
    chunk, start, end = chunks[0]
    assert start == 0
    assert end == len(chunk)
    assert text[start:end] == chunk


def test_process_upload_rejects_unknown_extensions():
    with pytest.raises(UploadValidationError):
        process_upload("payload.exe", "application/octet-stream", b"MZ")


def test_process_upload_rejects_fake_pdf_header():
    with pytest.raises(UploadValidationError):
        process_upload("paper.pdf", "application/pdf", b"not a pdf")


def test_process_upload_rejects_unreadable_pdf():
    with pytest.raises(DocumentProcessingError):
        process_upload("paper.pdf", "application/pdf", b"%PDF-1.4 truncated garbage")


def test_sanitize_filename_strips_paths_and_invalid_characters():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("weird<name>.txt") == "weird_name_.txt"
