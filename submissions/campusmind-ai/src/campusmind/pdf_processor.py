from io import BytesIO
from pypdf import PdfReader


def process_pdf(file_bytes: bytes, chunk_size: int = 1000, overlap: int = 150):
    """Extract PDF text page by page and split it into chunks."""

    reader = PdfReader(BytesIO(file_bytes))

    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported.")

    if len(reader.pages) > 100:
        raise ValueError("PDF cannot contain more than 100 pages.")

    chunks = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = " ".join(text.split())

        if not text:
            continue

        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            chunks.append({
                "page": page_number,
                "text": chunk_text
            })

            if end == len(text):
                break

            start = end - overlap

    if not chunks:
        raise ValueError(
            "No readable text found. This may be a scanned PDF."
        )

    return {
        "total_pages": len(reader.pages),
        "total_chunks": len(chunks),
        "chunks": chunks
    }
