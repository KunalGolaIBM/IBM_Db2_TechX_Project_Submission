"""FastAPI dependency wiring."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.db.repository import Db2Repository
from app.services.claim_extraction import ClaimExtractionService
from app.services.claim_verification import ClaimVerificationService
from app.services.documents import DocumentService
from app.services.evidence_retrieval import build_retrieval_backend
from app.services.llm import LangChainLLMClient
from app.services.pipeline import VerificationPipeline


@lru_cache
def get_repository() -> Db2Repository:
    return Db2Repository(get_settings())


@lru_cache
def get_document_service() -> DocumentService:
    return DocumentService(get_repository(), get_settings())


@lru_cache
def get_llm_client() -> LangChainLLMClient:
    return LangChainLLMClient(get_settings())


@lru_cache
def get_pipeline() -> VerificationPipeline:
    settings: Settings = get_settings()
    llm = get_llm_client()
    return VerificationPipeline(
        repository=get_repository(),
        document_service=get_document_service(),
        extractor=ClaimExtractionService(llm, max_claims=settings.llm_max_claims),
        retriever=build_retrieval_backend(get_repository(), settings),
        verifier=ClaimVerificationService(llm),
        llm=llm,
        settings=settings,
    )
