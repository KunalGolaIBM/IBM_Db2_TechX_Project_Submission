"""DBA tool and EXPLAIN API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.common import StrictModel

ToolKindLiteral = Literal["catalog", "monitoring"]


class DbaToolParam(StrictModel):
    name: str
    required: bool
    description: str


class DbaToolInfo(StrictModel):
    id: str
    kind: ToolKindLiteral
    title: str
    description: str
    params: list[DbaToolParam]
    requires: str


class DbaToolsResponse(StrictModel):
    tools: list[DbaToolInfo]
    mock: bool


class DbaRunRequest(StrictModel):
    # Free-form so that unknown names produce a precise INVALID_TOOL_PARAMS
    # error (with the allowed list) instead of a generic schema error.
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = Field(default=None, max_length=64)


class DbaRunResponse(StrictModel):
    request_id: str
    tool_id: str
    kind: ToolKindLiteral
    title: str
    mock: bool
    source: Literal["db2", "mock"]
    params: dict[str, Any]
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    latency_ms: int
    notes: list[str] = Field(default_factory=list)


class ExplainRequest(StrictModel):
    sql: str = Field(min_length=1, max_length=5000)
    session_id: str | None = Field(default=None, max_length=64)


class ExplainOperatorModel(StrictModel):
    operator_id: int
    operator_type: str
    total_cost: float | None = None
    io_cost: float | None = None
    cpu_cost: float | None = None


class ExplainObjectModel(StrictModel):
    schema_name: str
    name: str
    object_type: str


class ExplainResponse(StrictModel):
    request_id: str
    mock: bool
    status: Literal["OK", "UNAVAILABLE", "FAILED"]
    source: Literal["db2", "mock", "none"]
    explained_sql: str
    total_cost: float | None = None
    operators: list[ExplainOperatorModel] = Field(default_factory=list)
    objects: list[ExplainObjectModel] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    sqlstate: str | None = None
    hint: str | None = None
    detail: str | None = None
    warnings: list[str] = Field(default_factory=list)
    latency_ms: int = 0
