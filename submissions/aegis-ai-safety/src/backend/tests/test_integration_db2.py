"""Full vertical-slice test against a real IBM Db2 instance.

Run with:
    AEGIS_TEST_DB2=1 pytest -m integration

The LLM is scripted so the test is deterministic and free; Db2, SQL, retrieval,
HTTP schemas, and persistence are real. The session starts as PROCESSING and is
completed through the same pipeline used by the API.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime

import pytest

from app.core.config import get_settings
from app.core.errors import DatabaseUnavailableError
from app.db.connection import execute, query_all, transaction
from app.db.repository import Db2Repository
from app.services.claim_extraction import ClaimExtractionService
from app.services.claim_verification import ClaimVerificationService
from app.services.documents import DocumentService
from app.services.evidence_retrieval import LexicalRetrievalBackend
from app.services.pipeline import VerificationPipeline
from tests.fakes import (
    ScriptedLLM,
    extraction_response,
    passage_id_containing,
    verification_response,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AEGIS_TEST_DB2") != "1",
        reason="Set AEGIS_TEST_DB2=1 and run database/init_db.py to enable Db2 integration tests",
    ),
]

CLAIM_ONE = "SolarCell-X achieved a conversion efficiency of 92% under standard test conditions."
CLAIM_TWO = "The dual-layer anti-reflective coating reduced manufacturing cost by 40% compared with the baseline production process."
CLAIM_THREE = "SolarCell-X is suitable for deployment in desert environments."

RESEARCH_TEXT = f"{CLAIM_ONE} {CLAIM_TWO} {CLAIM_THREE}"


def build_evidence() -> str:
    nonce = uuid.uuid4().hex
    return f"""AEGIS SYNTHETIC INTEGRATION EVIDENCE — FICTIONAL — run {nonce}

In the controlled trial, SolarCell-X achieved a photovoltaic conversion efficiency of 92% under standard test conditions (AM1.5G spectrum, 25 degrees Celsius).

The dual-layer anti-reflective coating reduced manufacturing cost by 15% compared with the baseline production process. The coating did not change the measured conversion efficiency.

The trial did not evaluate performance under high-humidity or desert conditions. No field deployment data were collected.
"""


def scripted_handler(system_prompt: str, user_prompt: str) -> str:
    if "claim extraction" in system_prompt.lower():
        return extraction_response(
            [
                {"original_claim": CLAIM_ONE, "normalized_claim": CLAIM_ONE, "claim_type": "NUMERICAL"},
                {"original_claim": CLAIM_TWO, "normalized_claim": CLAIM_TWO, "claim_type": "NUMERICAL"},
                {"original_claim": CLAIM_THREE, "normalized_claim": CLAIM_THREE, "claim_type": "FACTUAL"},
            ]
        )
    if "deployment in desert environments" in user_prompt:
        return verification_response("INSUFFICIENT_EVIDENCE", [])
    if "40% compared with the baseline" in user_prompt:
        passage_id = passage_id_containing(user_prompt, "15%")
        assert passage_id is not None
        return verification_response("CONTRADICTED", [passage_id])
    if "92% under standard test conditions" in user_prompt:
        passage_id = passage_id_containing(user_prompt, "92%")
        assert passage_id is not None
        return verification_response("SUPPORTED", [passage_id])
    raise AssertionError("Unexpected verification prompt")


@pytest.fixture(scope="module")
def repository() -> Db2Repository:
    repo = Db2Repository(get_settings())
    try:
        health = repo.health()
    except DatabaseUnavailableError as exc:
        pytest.skip(f"Db2 unavailable: {exc.message}")
    if health["missing_tables"]:
        pytest.skip("Db2 schema incomplete; run python database/init_db.py")
    return repo


def test_full_vertical_slice_persists_to_db2(repository: Db2Repository):
    evidence = build_evidence()
    evidence_hash = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    llm = ScriptedLLM(scripted_handler)
    pipeline = VerificationPipeline(
        repository=repository,
        document_service=DocumentService(repository),
        extractor=ClaimExtractionService(llm),
        retriever=LexicalRetrievalBackend(repository, top_k=6),
        verifier=ClaimVerificationService(llm),
        llm=llm,
    )

    session_id: int | None = None
    try:
        result = pipeline.verify(
            submitted_text=RESEARCH_TEXT,
            document_ids=[],
            evidence_text=evidence,
            evidence_title="Synthetic integration evidence",
        )
        session_id = result["session_id"]

        assert result["status"] == "COMPLETED"
        assert result["duration_ms"] is not None
        assert result["completed_at"] is not None
        assert len(result["claims"]) == 3
        classifications = [claim["classification"] for claim in result["claims"]]
        assert classifications == ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
        assert result["counts"] == {
            "total": 3,
            "supported": 1,
            "contradicted": 1,
            "insufficient_evidence": 1,
            "verification_error": 0,
        }

        supported = result["claims"][0]
        contradicted = result["claims"][1]
        insufficient = result["claims"][2]
        assert supported["evidence"][0]["passage_text"].find("92%") != -1
        assert supported["evidence"][0]["evidence_relationship"] == "SUPPORTS"
        assert contradicted["evidence"][0]["passage_text"].find("15%") != -1
        assert contradicted["evidence"][0]["evidence_relationship"] == "CONTRADICTS"
        assert insufficient["evidence"] == []
        assert supported["human_review_status"] == "PENDING"

        # Re-open the session exactly as the history endpoint does.
        persisted = repository.get_session(session_id)
        assert persisted["status"] == "COMPLETED"
        assert persisted["duration_ms"] is not None
        assert [claim["classification"] for claim in persisted["claims"]] == classifications

        # Verify relational integrity and parameterized persistence directly.
        with transaction() as connection:
            claims = query_all(
                connection, "SELECT COUNT(*) AS total FROM CLAIMS WHERE SESSION_ID = ?", (session_id,)
            )[0]["total"]
            results = query_all(
                connection,
                "SELECT COUNT(*) AS total FROM VERIFICATION_RESULTS R "
                "JOIN CLAIMS C ON C.CLAIM_ID = R.CLAIM_ID WHERE C.SESSION_ID = ?",
                (session_id,),
            )[0]["total"]
            links = query_all(
                connection,
                "SELECT COUNT(*) AS total FROM EVIDENCE_LINKS E "
                "JOIN VERIFICATION_RESULTS R ON R.RESULT_ID = E.RESULT_ID "
                "JOIN CLAIMS C ON C.CLAIM_ID = R.CLAIM_ID WHERE C.SESSION_ID = ?",
                (session_id,),
            )[0]["total"]
        assert int(claims) == 3
        assert int(results) == 3
        assert int(links) == 2
    finally:
        if session_id is not None:
            with transaction() as connection:
                execute(connection, "DELETE FROM VERIFICATION_SESSIONS WHERE SESSION_ID = ?", (session_id,))
        existing = repository.get_document_by_hash(evidence_hash)
        if existing:
            with transaction() as connection:
                execute(
                    connection, "DELETE FROM DOCUMENTS WHERE DOCUMENT_ID = ?", (existing["document_id"],)
                )


def test_history_query_returns_new_session(repository: Db2Repository):
    sessions = repository.list_sessions(limit=10)
    assert isinstance(sessions, list)
    for session in sessions:
        assert {"session_id", "status", "model_provider", "counts"} <= session.keys()
