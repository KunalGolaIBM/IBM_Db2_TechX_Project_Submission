"""Pydantic request/response schemas for verification."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VerifyRequest(BaseModel):
    submitted_text: str = Field(min_length=10, max_length=30000)
    document_ids: list[int] = Field(default_factory=list, max_length=25)
    evidence_text: str | None = Field(default=None, max_length=30000)
    evidence_title: str | None = Field(default=None, max_length=500)

    @field_validator("submitted_text")
    @classmethod
    def submitted_text_within_db_limit(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("submitted_text must contain at least 10 characters")
        if len(value.encode("utf-8")) > 32000:
            raise ValueError("submitted_text exceeds the 32,000-byte storage limit")
        return value

    @field_validator("evidence_text")
    @classmethod
    def evidence_text_within_db_limit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if len(value.encode("utf-8")) > 32000:
            raise ValueError("evidence_text exceeds the 32,000-byte storage limit")
        return value

    @field_validator("document_ids")
    @classmethod
    def valid_document_ids(cls, value: list[int]) -> list[int]:
        if any(document_id <= 0 for document_id in value):
            raise ValueError("document_ids must be positive integers")
        return list(dict.fromkeys(value))


class EvidenceResponse(BaseModel):
    passage_id: int
    passage_text: str
    page_number: int | None = None
    passage_index: int
    document_id: int
    document_title: str
    filename: str
    evidence_relationship: str | None = None
    relevance_score: float


class ClaimResponse(BaseModel):
    claim_id: int
    original_claim: str
    normalized_claim: str
    claim_type: str
    position_start: int | None = None
    position_end: int | None = None
    classification: str | None = None
    explanation: str | None = None
    limitations: str | None = None
    numerical_analysis: str | None = None
    human_review_status: str = "PENDING"
    verification_method: str | None = None
    result_created_at: datetime | None = None
    evidence: list[EvidenceResponse] = Field(default_factory=list)


class VerificationCounts(BaseModel):
    total: int = 0
    supported: int = 0
    contradicted: int = 0
    insufficient_evidence: int = 0
    verification_error: int = 0


class VerificationResponse(BaseModel):
    session_id: int
    submitted_text: str
    model_provider: str
    status: str
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    counts: VerificationCounts
    claims: list[ClaimResponse] = Field(default_factory=list)


class VerificationSummary(BaseModel):
    session_id: int
    status: str
    model_provider: str
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    preview: str
    total_claims: int
    counts: VerificationCounts


class VerificationListResponse(BaseModel):
    verifications: list[VerificationSummary] = Field(default_factory=list)


class EvaluationResponse(BaseModel):
    status: str
    dataset: str = "SciFact"
    license: str = "CC BY-NC 2.0"
    message: str
    results: dict | None = None
