"""Chat workspace schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import StrictModel

ChatMode = Literal["auto", "rag", "sql"]
Intent = Literal["docs", "data", "general"]


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)
    mode: ChatMode = "auto"


class Citation(StrictModel):
    source: str
    title: str
    snippet: str
    score: float | None = None


class Timings(StrictModel):
    total_ms: int = 0
    retrieval_ms: int | None = None
    generation_ms: int | None = None


class ChatResponse(StrictModel):
    reply: str
    intent: Intent
    citations: list[Citation] = Field(default_factory=list)
    sql: str | None = None
    mock: bool
    request_id: str
    timings: Timings = Field(default_factory=Timings)
    warnings: list[str] = Field(default_factory=list)
