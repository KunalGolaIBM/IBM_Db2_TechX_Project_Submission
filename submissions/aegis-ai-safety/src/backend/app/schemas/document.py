"""Pydantic schemas for evidence documents."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    document_id: int
    title: str
    filename: str
    content_hash: str
    source_type: str
    processing_status: str = "READY"
    external_id: str | None = None
    passage_count: int
    created_at: datetime
    already_existed: bool = False


class DocumentSummary(BaseModel):
    document_id: int
    title: str
    filename: str
    source_type: str
    processing_status: str = "READY"
    passage_count: int
    created_at: datetime


class PassageSummary(BaseModel):
    passage_id: int
    document_id: int
    passage_text: str
    page_number: int | None = None
    passage_index: int
    char_start: int | None = None
    char_end: int | None = None


class DocumentDetail(DocumentSummary):
    content_hash: str
    external_id: str | None = None
    passages: list[PassageSummary] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary] = Field(default_factory=list)
