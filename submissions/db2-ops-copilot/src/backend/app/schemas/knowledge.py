"""Offline knowledge-document ingestion schemas."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import StrictModel


class KnowledgeDocument(StrictModel):
    text: str = Field(min_length=1, max_length=20000)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=16)

    @field_validator("metadata")
    @classmethod
    def _bounded_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 64 or len(item) > 256 for key, item in value.items()):
            raise ValueError("metadata keys must be <=64 and values <=256 characters")
        return value


class KnowledgeIngestRequest(StrictModel):
    documents: list[KnowledgeDocument] = Field(min_length=1, max_length=20)


class KnowledgeIngestResponse(StrictModel):
    documents_added: int
    mock: bool
