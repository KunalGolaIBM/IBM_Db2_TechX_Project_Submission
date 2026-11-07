"""Pydantic response schemas for health and error envelopes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str = "aegis-api"
    version: str
    environment: str
    llm_provider: str
    llm_model: str
    database: str


class DbHealthResponse(BaseModel):
    connected: bool
    database: str
    host: str
    schema_name: str = Field(serialization_alias="schema")
    server: str | None = None
    server_time: datetime | None = None
    tables: list[str] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)
    message: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
