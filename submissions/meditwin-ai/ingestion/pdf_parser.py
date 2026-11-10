"""
MediTwin AI — PDF Parser
Extracts text from PDF files page by page, preserving page numbers.
"""

import hashlib
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


@dataclass
class PageContent:
    """Content extracted from a single PDF page."""
    page_number: int
    text: str
    char_count: int


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    file_name: str
    total_pages: int
    pages: List[PageContent]
    full_text: str
    source_hash: str
    parse_status: str
    error_message: Optional[str] = None


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_file(file_name: str, file_bytes: bytes,
                  max_size_mb: int = 10) -> tuple:
    """
    Validate uploaded file.
    Returns (is_valid, error_message).
    """
    # Check file extension
    suffix = Path(file_name).suffix.lower()
    if suffix not in ('.pdf', '.txt'):
        return False, f"Unsupported file type: {suffix}. Only PDF and TXT files are accepted."

    # Check file size
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"File too large: {size_mb:.1f} MB. Maximum allowed: {max_size_mb} MB."

    # Check not empty
    if len(file_bytes) == 0:
        return False, "File is empty."

    return True, None


def parse_pdf(file_name: str, file_bytes: bytes) -> ParsedDocument:
    """
    Parse a PDF file and extract text page by page.
    Returns a ParsedDocument with page-level content.
    """
    source_hash = compute_file_hash(file_bytes)

    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        pages = []
        all_text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            text = text.strip()

            pages.append(PageContent(
                page_number=page_num + 1,  # 1-indexed
                text=text,
                char_count=len(text),
            ))
            all_text_parts.append(text)

        doc.close()
        full_text = "\n\n".join(all_text_parts)

        # Check if document has any readable content
        total_chars = sum(p.char_count for p in pages)
        if total_chars == 0:
            return ParsedDocument(
                file_name=file_name,
                total_pages=len(pages),
                pages=pages,
                full_text="",
                source_hash=source_hash,
                parse_status="FAILED",
                error_message="Document contains no readable text."
            )

        return ParsedDocument(
            file_name=file_name,
            total_pages=len(pages),
            pages=pages,
            full_text=full_text,
            source_hash=source_hash,
            parse_status="PARSED",
        )

    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        return ParsedDocument(
            file_name=file_name,
            total_pages=0,
            pages=[],
            full_text="",
            source_hash=source_hash,
            parse_status="FAILED",
            error_message=str(e),
        )


def parse_text_file(file_name: str, file_bytes: bytes) -> ParsedDocument:
    """Parse a plain text file as a single-page document."""
    source_hash = compute_file_hash(file_bytes)
    try:
        text = file_bytes.decode("utf-8").strip()
        if not text:
            return ParsedDocument(
                file_name=file_name,
                total_pages=0,
                pages=[],
                full_text="",
                source_hash=source_hash,
                parse_status="FAILED",
                error_message="Text file is empty.",
            )

        page = PageContent(page_number=1, text=text, char_count=len(text))
        return ParsedDocument(
            file_name=file_name,
            total_pages=1,
            pages=[page],
            full_text=text,
            source_hash=source_hash,
            parse_status="PARSED",
        )
    except UnicodeDecodeError:
        return ParsedDocument(
            file_name=file_name,
            total_pages=0,
            pages=[],
            full_text="",
            source_hash=source_hash,
            parse_status="FAILED",
            error_message="Could not decode text file (not valid UTF-8).",
        )


def parse_document(file_name: str, file_bytes: bytes) -> ParsedDocument:
    """
    Parse a document (PDF or TXT) and return structured content.
    """
    suffix = Path(file_name).suffix.lower()
    if suffix == '.pdf':
        return parse_pdf(file_name, file_bytes)
    elif suffix == '.txt':
        return parse_text_file(file_name, file_bytes)
    else:
        return ParsedDocument(
            file_name=file_name,
            total_pages=0,
            pages=[],
            full_text="",
            source_hash=compute_file_hash(file_bytes),
            parse_status="FAILED",
            error_message=f"Unsupported file type: {suffix}",
        )

