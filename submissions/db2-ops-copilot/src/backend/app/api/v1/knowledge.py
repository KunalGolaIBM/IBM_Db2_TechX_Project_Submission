"""Knowledge-base routes, currently available for offline mock demonstrations."""

from fastapi import APIRouter, Request

from app.adapters.base import DocumentInput
from app.api.deps import get_app_settings, get_registry
from app.core.errors import AppError
from app.schemas.knowledge import KnowledgeIngestRequest, KnowledgeIngestResponse

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/documents", response_model=KnowledgeIngestResponse)
def ingest_documents(
    payload: KnowledgeIngestRequest, request: Request
) -> KnowledgeIngestResponse:
    settings = get_app_settings()
    if not settings.is_mock:
        raise AppError(
            "Knowledge ingestion is only enabled in mock mode until the Db2/Ollama path is verified.",
            code="KB_INGESTION_UNVERIFIED",
            status_code=503,
        )
    documents = [
        DocumentInput(text=document.text, metadata=document.metadata)
        for document in payload.documents
    ]
    added = get_registry(request).vector_store.upsert_documents(documents)
    return KnowledgeIngestResponse(documents_added=added, mock=True)
