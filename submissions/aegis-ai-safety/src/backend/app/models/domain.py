"""Domain types shared across the verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Classification(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VERIFICATION_ERROR = "VERIFICATION_ERROR"


class SessionStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True)
class ExtractedClaim:
    original_claim: str
    normalized_claim: str
    claim_type: str
    position_start: int | None = None
    position_end: int | None = None


@dataclass(slots=True)
class PassageCandidate:
    passage_id: int
    document_id: int
    document_title: str
    filename: str
    passage_text: str
    page_number: int | None
    passage_index: int
    retrieval_score: float = 0.0


@dataclass(slots=True)
class EvidenceReference:
    passage_id: int
    relevance_score: float
    document_title: str
    page_number: int | None


@dataclass(slots=True)
class ClaimAssessment:
    classification: Classification
    explanation: str
    limitations: str
    evidence: list[EvidenceReference] = field(default_factory=list)
    numerical_analysis: str | None = None
    verification_method: str = "langchain_llm+db2_lexical_retrieval"


@dataclass(slots=True)
class ClaimResult:
    claim_id: int
    assessment: ClaimAssessment
