"""Document ingestion service shared by uploads, pasted evidence, and seeding."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.errors import DocumentProcessingError
from app.db.repository import Db2Repository
from app.services.document_processing import (
    ProcessedDocument,
    process_text,
    process_upload,
)


class DocumentService:
    def __init__(self, repository: Db2Repository, settings: Settings | None = None) -> None:
        self.repository = repository
        self.settings = settings or get_settings()

    def ingest_processed(self, processed: ProcessedDocument) -> dict:
        if not processed.passages:
            raise DocumentProcessingError("The document produced no usable passages.")
        existing = self.repository.get_document_by_hash(processed.content_hash)
        if existing:
            result = dict(existing)
            result["already_existed"] = True
            return result
        result = self.repository.create_document(
            title=processed.title,
            filename=processed.filename,
            content_hash=processed.content_hash,
            source_type=processed.source_type,
            passages=processed.passages,
        )
        result["already_existed"] = False
        return result

    def ingest_upload(
        self, filename: str, content_type: str | None, data: bytes, title: str | None = None
    ) -> dict:
        processed = process_upload(filename, content_type, data, title=title)
        return self.ingest_processed(processed)

    def ingest_pasted(self, text: str, title: str | None = None) -> dict:
        encoded = text.encode("utf-8")
        processed = process_text(
            encoded,
            filename="pasted-evidence.txt",
            title=title or "Pasted evidence",
        )
        return self.ingest_processed(processed)

    def list_documents(self, limit: int = 50) -> list[dict]:
        return self.repository.list_documents(limit=limit)
