"""SQL validation schemas (shared by the validator and the API)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.common import StrictModel

Severity = Literal["error", "warning"]


class Violation(StrictModel):
    code: str
    message: str
    severity: Severity = "error"


class SqlValidateRequest(StrictModel):
    sql: str = Field(min_length=1, max_length=5000)


class AppliedPolicy(StrictModel):
    max_rows: int
    timeout_ms: int
    enforce_row_limit: bool


class SqlValidateResponse(StrictModel):
    valid: bool
    statement_type: str | None = None
    dialect: str | None = None
    normalized_sql: str | None = None
    violations: list[Violation] = Field(default_factory=list)
    warnings: list[Violation] = Field(default_factory=list)
    policy: AppliedPolicy


class SqlExecutionRequest(StrictModel):
    sql: str = Field(min_length=1, max_length=5000)
    session_id: str | None = Field(default=None, max_length=64)


class SqlExecutionResponse(StrictModel):
    request_id: str
    mock: bool
    executed_sql: str
    row_limit: int
    row_limit_applied: bool
    explain_status: Literal["OK", "FAILED", "DISABLED"]
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    latency_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
