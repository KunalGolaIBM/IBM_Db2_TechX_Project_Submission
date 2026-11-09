"""Pydantic models for investigations, evidence, recommendations and review."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from civiclens.domain.models import Category

MAX_EVIDENCE_PER_RECOMMENDATION = 50


class InvestigationStatus(StrEnum):
    OPEN = "OPEN"
    RUNNING = "RUNNING"
    PENDING_REVIEW = "PENDING_REVIEW"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class RecommendationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_INFO = "NEEDS_INFO"


class GeneratorType(StrEnum):
    LLM = "LLM"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    MANUAL = "MANUAL"
    UNKNOWN = "UNKNOWN"


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=3, max_length=2000)


class Investigation(BaseModel):
    investigation_id: int
    title: str
    question: str
    status: InvestigationStatus
    created_by: str
    created_at: datetime
    closed_at: datetime | None


class EvidenceCreate(BaseModel):
    complaint_ids: list[StrictInt] = Field(min_length=1, max_length=MAX_EVIDENCE_PER_RECOMMENDATION)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("complaint_ids")
    @classmethod
    def _positive_unique(cls, ids: list[int]) -> list[int]:
        if any(i < 1 for i in ids):
            raise ValueError("complaint ids must be positive")
        return sorted(set(ids))


class EvidenceItem(BaseModel):
    investigation_id: int
    complaint_id: int
    relevance: float
    note: str | None
    added_at: datetime
    title: str
    category: Category
    geo_cell: str
    severity: int
    reported_at: datetime
    is_synthetic: bool


class RecommendationDraft(BaseModel):
    """What a generator (LLM, rules or a human) proposes. Status is never part of the draft."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    summary: str = Field(min_length=5, max_length=500)
    rationale: str = Field(min_length=10, max_length=8000)
    priority: int = Field(ge=1, le=5, description="1 = most urgent, 5 = least urgent")
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[StrictInt] = Field(min_length=1, max_length=MAX_EVIDENCE_PER_RECOMMENDATION)

    @field_validator("evidence_ids")
    @classmethod
    def _positive_unique(cls, ids: list[int]) -> list[int]:
        if any(i < 1 for i in ids):
            raise ValueError("evidence ids must be positive integers")
        return sorted(set(ids))


class ReviewDecision(BaseModel):
    decision_id: int
    recommendation_id: int
    reviewer: str
    decision: Literal["APPROVED", "REJECTED", "NEEDS_INFO"]
    comment: str | None
    decided_at: datetime


class Recommendation(BaseModel):
    recommendation_id: int
    investigation_id: int
    summary: str
    rationale: str
    priority: int
    confidence: float
    evidence_ids: list[int]
    generator_type: GeneratorType
    model_name: str | None
    status: RecommendationStatus
    created_at: datetime
    review: ReviewDecision | None = None


class RecommendationListItem(Recommendation):
    """A recommendation plus the context a reviewer needs to triage it without extra requests."""

    investigation_title: str
    investigation_status: InvestigationStatus
    investigation_created_by: str


class DecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision: Literal["APPROVED", "REJECTED"]
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _reject_needs_comment(self) -> DecisionRequest:
        if self.decision == "REJECTED" and not (self.comment and len(self.comment) >= 3):
            raise ValueError("A comment of at least 3 characters is required to reject.")
        return self


class AuditEntry(BaseModel):
    audit_id: int
    actor_type: str
    actor_id: str
    action: str
    tool_name: str | None
    input_json: str | None
    output_summary: str | None
    success: bool
    created_at: datetime


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["auto", "llm", "fallback"] = "auto"
    days: int = Field(default=30, ge=1, le=365)
    category: Category | None = None
    max_hotspots: int = Field(default=3, ge=1, le=5)


class RunResult(BaseModel):
    investigation_id: int
    status: InvestigationStatus
    generator: GeneratorType
    model_name: str | None
    llm_configured: bool
    fallback_reason: str | None
    steps: int
    tool_calls: int
    recommendation_ids: list[int]
    notice: str
