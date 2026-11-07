"""End-to-end verification pipeline.

Order of operations:
1. Ingest optional pasted evidence (and validate document IDs).
2. Persist a PROCESSING session.
3. Extract atomic claims with LangChain.
4. Retrieve Db2-backed lexical candidates per claim.
5. Ask the LLM for an evidence-grounded judgment.
6. Validate evidence references and persist everything atomically.
"""

from __future__ import annotations

import logging
import time

from app.config_helpers import truncate_bytes
from app.core.config import Settings, get_settings
from app.core.errors import AegisError, LLMUnavailableError, PipelineError
from app.db.repository import Db2Repository
from app.models.domain import SessionStatus
from app.services.claim_extraction import ClaimExtractionService
from app.services.claim_verification import ClaimVerificationService
from app.services.documents import DocumentService
from app.services.evidence_retrieval import RetrievalBackend
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)


class VerificationPipeline:
    def __init__(
        self,
        repository: Db2Repository,
        document_service: DocumentService,
        extractor: ClaimExtractionService,
        retriever: RetrievalBackend,
        verifier: ClaimVerificationService,
        llm: LLMClient,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.document_service = document_service
        self.extractor = extractor
        self.retriever = retriever
        self.verifier = verifier
        self.llm = llm
        self.settings = settings or get_settings()

    def verify(
        self,
        submitted_text: str,
        document_ids: list[int],
        evidence_text: str | None = None,
        evidence_title: str | None = None,
    ) -> dict:
        selected_documents = list(dict.fromkeys(int(doc_id) for doc_id in document_ids))

        if evidence_text and evidence_text.strip():
            ingested = self.document_service.ingest_pasted(evidence_text, evidence_title)
            if ingested["document_id"] not in selected_documents:
                selected_documents.append(ingested["document_id"])

        for document_id in selected_documents:
            # Raises a 404 rather than silently verifying against no evidence.
            self.repository.get_document(document_id)

        provider_label = f"{self.settings.llm_provider}/{self.settings.llm_model}"
        session_id = self.repository.create_session(submitted_text, provider_label)
        started = time.monotonic()

        def duration_ms() -> int:
            return int((time.monotonic() - started) * 1000)

        try:
            claims = self.extractor.extract(submitted_text)
            if not claims:
                self.repository.set_session_status(
                    session_id,
                    SessionStatus.COMPLETED.value,
                    duration_ms=duration_ms(),
                )
                logger.info("Session %s completed with no extractable claims", session_id)
                return self.repository.get_session(session_id)

            results = []
            for claim in claims:
                candidates = self.retriever.retrieve(claim, selected_documents)
                assessment = self.verifier.verify(claim, candidates)
                results.append((claim, assessment))

            self.repository.save_results(
                session_id,
                results,
                status=SessionStatus.COMPLETED.value,
                duration_ms=duration_ms(),
            )
            logger.info("Session %s completed with %d claims", session_id, len(claims))
            return self.repository.get_session(session_id)
        except LLMUnavailableError:
            self.repository.mark_session_failed(
                session_id, "The language model was unavailable.", duration_ms()
            )
            raise
        except AegisError as exc:
            self.repository.mark_session_failed(
                session_id, truncate_bytes(exc.message, 1900), duration_ms()
            )
            raise
        except Exception as exc:
            logger.exception("Unexpected pipeline failure for session %s", session_id)
            self.repository.mark_session_failed(
                session_id, "An unexpected internal error occurred.", duration_ms()
            )
            raise PipelineError("The verification pipeline failed unexpectedly.") from exc
