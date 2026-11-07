"""Document processing: validated uploads, PDF text extraction, passage splitting."""

from __future__ import annotations

import hashlib
import io
import logging
import re
from dataclasses import dataclass
from pathlib import PurePath

from app.core.errors import DocumentProcessingError, UploadValidationError
from app.config_helpers import truncate_bytes

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "text",
    "text/markdown": "text",
}
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"[ \t]+")


@dataclass(slots=True)
class ProcessedDocument:
    title: str
    filename: str
    content_hash: str
    source_type: str
    # (text, page_number, char_start, char_end); offsets are within the page
    # text for PDFs and within the full text for plain text.
    passages: list[tuple[str, int | None, int | None, int | None]]


def sanitize_filename(filename: str) -> str:
    name = PurePath(filename or "document").name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name[:255] or "document"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean(text: str) -> str:
    lines = [line.strip() for line in text.replace("\x00", " ").splitlines()]
    return "\n".join(line for line in lines if line)


def _chunk_cleaned(cleaned: str, target_chars: int, overlap_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(paragraph) if s.strip()]
        if not sentences:
            continue
        for sentence in sentences:
            while len(sentence) > target_chars:
                head, sentence = sentence[:target_chars], sentence[target_chars:]
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.append(head.strip())
            if not current:
                current = sentence
            elif len(current) + 1 + len(sentence) <= target_chars:
                current = f"{current} {sentence}"
            else:
                chunks.append(current.strip())
                tail = current[-overlap_chars:] if overlap_chars and len(current) > overlap_chars else ""
                current = f"{tail} {sentence}".strip()
    if current.strip():
        chunks.append(current.strip())
    return [truncate_bytes(chunk, 3900) for chunk in chunks if chunk.strip()]


def chunk_text(text: str, target_chars: int = 1200, overlap_chars: int = 120) -> list[str]:
    """Split prose into overlapping, sentence-aware passages."""
    cleaned = _clean(text)
    if not cleaned:
        return []
    return _chunk_cleaned(cleaned, target_chars, overlap_chars)


def chunk_text_with_offsets(
    text: str, target_chars: int = 1200, overlap_chars: int = 120
) -> list[tuple[str, int | None, int | None]]:
    """Return passages with approximate character offsets in the cleaned input."""
    cleaned = _clean(text)
    if not cleaned:
        return []
    chunks = _chunk_cleaned(cleaned, target_chars, overlap_chars)
    results: list[tuple[str, int | None, int | None]] = []
    cursor = 0
    for chunk in chunks:
        start = cleaned.find(chunk, max(0, cursor - overlap_chars))
        if start == -1:
            start = cleaned.find(chunk)
        if start == -1:
            results.append((chunk, None, None))
            continue
        end = start + len(chunk)
        results.append((chunk, start, end))
        cursor = end
    return results


def process_pdf(data: bytes, filename: str, title: str | None = None) -> ProcessedDocument:
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover
        raise DocumentProcessingError("PDF support is unavailable on the server.") from exc

    safe_name = sanitize_filename(filename)
    try:
        document = pymupdf.open(stream=io.BytesIO(data), filetype="pdf")
    except Exception as exc:
        raise DocumentProcessingError("The uploaded file is not a readable PDF.") from exc

    if document.is_encrypted:
        document.close()
        raise DocumentProcessingError("Encrypted PDFs are not supported.")

    passages: list[tuple[str, int | None, int | None, int | None]] = []
    extracted_pages = 0
    try:
        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text") or ""
            if len(page_text.strip()) < 20:
                continue
            extracted_pages += 1
            for chunk, start, end in chunk_text_with_offsets(page_text):
                passages.append((chunk, page_number, start, end))
    finally:
        document.close()

    if not passages:
        raise DocumentProcessingError(
            "No selectable text was found. Scanned or image-only PDFs require OCR, which is not implemented."
        )

    stem = PurePath(safe_name).stem or "document"
    return ProcessedDocument(
        title=truncate_bytes((title or stem).strip(), 490) or "document",
        filename=safe_name,
        content_hash=content_hash(data),
        source_type="pdf",
        passages=passages,
    )


def process_text(data: bytes, filename: str = "pasted-evidence.txt", title: str | None = None) -> ProcessedDocument:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    safe_name = sanitize_filename(filename)
    chunks = chunk_text_with_offsets(text)
    if not chunks:
        raise DocumentProcessingError("The provided evidence text is empty.")
    stem = PurePath(safe_name).stem or "evidence"
    return ProcessedDocument(
        title=truncate_bytes((title or stem).strip(), 490) or "evidence",
        filename=safe_name,
        content_hash=content_hash(data),
        source_type="text",
        passages=[(chunk, 1, start, end) for chunk, start, end in chunks],
    )


def process_upload(
    filename: str, content_type: str | None, data: bytes, title: str | None = None
) -> ProcessedDocument:
    if not data:
        raise UploadValidationError("The uploaded file is empty.")
    suffix = PurePath(filename or "").suffix.lower()
    normalized_type = (content_type or "").split(";")[0].strip().lower()

    if normalized_type and normalized_type not in ALLOWED_CONTENT_TYPES:
        raise UploadValidationError("Only PDF and plain-text files are accepted.")
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadValidationError("Only .pdf, .txt, and .md files are accepted.")

    if suffix == ".pdf" or normalized_type == "application/pdf":
        if b"%PDF" not in data[:1024]:
            raise UploadValidationError("The file does not contain a valid PDF header.")
        return process_pdf(data, filename, title=title)

    return process_text(data, filename or "evidence.txt", title=title)
