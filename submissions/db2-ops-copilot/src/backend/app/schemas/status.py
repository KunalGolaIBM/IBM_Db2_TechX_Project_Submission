"""Status / configuration view schemas (dashboard + settings page)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import StrictModel


class DatabaseStatus(StrictModel):
    provider: str
    connected: bool
    host: str
    port: int
    database: str
    detail: str


class VectorStoreStatus(StrictModel):
    provider: str
    document_count: int
    detail: str


class ModelStatus(StrictModel):
    provider: str
    model: str
    available: bool
    detail: str
    dimensions: int | None = None


class StatusResponse(StrictModel):
    timestamp: str
    adapter_mode: Literal["mock", "real"]
    database: DatabaseStatus
    vector_store: VectorStoreStatus
    llm: ModelStatus
    embeddings: ModelStatus


class DatabaseConfigView(StrictModel):
    host: str
    port: int
    name: str
    read_only_user: str


class ModelsConfigView(StrictModel):
    llm: str
    embeddings: str
    ollama_base_url: str


class SqlPolicyView(StrictModel):
    allowed_statements: list[str] = Field(default_factory=list)
    max_sql_length: int
    max_ast_nodes: int
    max_rows: int
    query_timeout_ms: int
    denied_schemas: list[str]
    enforce_row_limit: bool


class SecurityConfigView(StrictModel):
    injection_mode: str
    max_message_length: int


class ConfigResponse(StrictModel):
    """Non-sensitive effective configuration. Secrets are never included."""

    environment: str
    debug: bool
    adapter_mode: Literal["mock", "real"]
    api_base: str
    cors_origins: list[str]
    serve_frontend: bool
    database: DatabaseConfigView
    models: ModelsConfigView
    sql_policy: SqlPolicyView
    security: SecurityConfigView
