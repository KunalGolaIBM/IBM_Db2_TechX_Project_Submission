"""API contract v1.1.0 (see docs/API_CONTRACT.md). Changing a field here is a contract change.

1.1.0 is additive over 1.0.0: no field was removed or renamed.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from metricguard.core.plan import QueryPlan

JsonScalar = Union[str, int, float, None]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------------------
# Shared
# --------------------------------------------------------------------------------------
class ValidationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    EXECUTED_WITH_WARNINGS = "EXECUTED_WITH_WARNINGS"
    AMBIGUOUS = "AMBIGUOUS"
    BLOCKED = "BLOCKED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUDIT_NOT_FOUND = "AUDIT_NOT_FOUND"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    PLANNER_UNAVAILABLE = "PLANNER_UNAVAILABLE"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    DB2_ERROR = "DB2_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(_Model):
    field: str | None = Field(None, description="Request field path, e.g. 'question'")
    issue: str


class ErrorBody(_Model):
    code: ErrorCode
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    sqlstate: str | None = Field(None, description="Db2 SQLSTATE when the error came from Db2")


class ErrorResponse(_Model):
    request_id: str | None = None
    error: ErrorBody


# --------------------------------------------------------------------------------------
# GET /api/health
# --------------------------------------------------------------------------------------
class DatabaseHealth(_Model):
    status: Literal["up", "down"]
    vendor: Literal["IBM Db2"] = "IBM Db2"
    server_version: str | None = Field(None, examples=["DB2/LINUXX8664 12.01.0500"])
    service_level: str | None = Field(None, examples=["DB2 v12.1.5.0"])
    database: str
    schema_name: str = Field(examples=["METRICGUARD"])
    latency_ms: float | None = None
    tables_present: int | None = None
    tables_expected: int = 6
    error: ErrorBody | None = None


class RegistryHealth(_Model):
    metrics: int
    fingerprint: str
    db_hash_match: bool | None = Field(None, description="null when Db2 is down")


ExecutionMode = Literal["LLM", "DEMO_RULE_BASED"]


class PlannerHealth(_Model):
    status: Literal["ready", "not_configured"]
    provider: str | None = Field(None, examples=["meta", "anthropic", "metricguard-rules"])
    model: str | None = None
    execution_mode: ExecutionMode | None = Field(
        None, description="Mode POST /api/analyze will use: LLM (LangChain + a real model provider) or DEMO_RULE_BASED. "
        "null when no planner is available.")


class HealthResponse(_Model):
    status: Literal["ok", "degraded"]
    api_version: str
    service_version: str
    time: datetime
    database: DatabaseHealth
    registry: RegistryHealth
    planner: PlannerHealth


# --------------------------------------------------------------------------------------
# GET /api/metrics
# --------------------------------------------------------------------------------------
class MetricInfo(_Model):
    name: str
    version: str
    display_name: str
    description: str
    calculation: str
    unit: Literal["USD", "COUNT", "RATIO"]
    scale: int
    kind: Literal["BASE", "DERIVED"]
    additive: bool
    eligible_order_statuses: list[str]
    date_attribution: str
    null_handling: str
    refund_treatment: str
    discount_treatment: str
    allowed_dimensions: list[str]
    allowed_filters: list[str]
    synonyms: list[str]
    lifecycle_status: Literal["APPROVED", "DRAFT", "DEPRECATED"]
    owner: str
    definition_hash: str


class DimensionInfo(_Model):
    name: str
    display_name: str
    description: str
    data_type: Literal["string"]
    allowed_values: list[str] | None


class FilterInfo(_Model):
    name: str
    display_name: str
    operators: list[Literal["in"]]
    allowed_values: list[str]


class DataCoverage(_Model):
    start_date: date
    end_date: date
    timezone: Literal["UTC"] = "UTC"


class MetricsResponse(_Model):
    registry_fingerprint: str
    data_coverage: DataCoverage
    metrics: list[MetricInfo]
    dimensions: list[DimensionInfo]
    filters: list[FilterInfo]


# --------------------------------------------------------------------------------------
# GET /api/examples
# --------------------------------------------------------------------------------------
class ExampleInfo(_Model):
    id: str
    question: str
    category: Literal["trend", "comparison", "ranking", "kpi", "governance"]
    description: str
    expected_status: ValidationStatus


class ExamplesResponse(_Model):
    examples: list[ExampleInfo]


# --------------------------------------------------------------------------------------
# POST /api/analyze
# --------------------------------------------------------------------------------------
class AnalyzeOptions(_Model):
    max_rows: int = Field(100, ge=1, le=500, description="Maximum rows returned in result.rows")


class AnalyzeRequest(_Model):
    question: str = Field(min_length=3, max_length=1000, examples=["What was net revenue by month in H1 2026?"])
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class MetricUsage(_Model):
    name: str
    version: str
    display_name: str
    unit: Literal["USD", "COUNT", "RATIO"]
    scale: int
    definition_hash: str


class SqlParameterOut(_Model):
    position: int = Field(description="1-based position of the '?' marker")
    name: str = Field(description="Semantic name, e.g. date_start_inclusive")
    db2_type: str = Field(examples=["TIMESTAMP", "VARCHAR(16)"])
    value: JsonScalar


class SqlBlock(_Model):
    text: str = Field(description="Exact SQL text sent to Db2 (parameter markers, not interpolated values)")
    dialect: Literal["db2"] = "db2"
    parameters: list[SqlParameterOut]
    generated_by: Literal["metricguard-compiler"] = "metricguard-compiler"
    sql_hash: str = Field(description="SHA-256 of text")
    tables: list[str]


class ResultColumn(_Model):
    name: str = Field(description="Key used in result.rows objects")
    label: str
    role: Literal["dimension", "metric"]
    data_type: Literal["string", "integer", "decimal"]
    unit: Literal["USD", "COUNT", "RATIO"] | None = None
    scale: int | None = None


class ResultBlock(_Model):
    columns: list[ResultColumn]
    rows: list[dict[str, JsonScalar]]
    row_count: int
    truncated: bool


class ChartPoint(_Model):
    x: str | None
    y: float | None


class ChartSeries(_Model):
    key: str = Field(description="Stable series id: metric name, or '<metric>:<dimension value>'")
    label: str
    metric: str
    unit: Literal["USD", "COUNT", "RATIO"]
    points: list[ChartPoint]


class ChartAxis(_Model):
    field: str
    label: str


class ChartSpec(_Model):
    type: Literal["kpi", "line", "bar", "grouped_bar", "table"]
    title: str
    x: ChartAxis | None
    series: list[ChartSeries]


class Headline(_Model):
    metric: str
    label: str
    value: float | int | None
    unit: Literal["USD", "COUNT", "RATIO"]
    formatted: str = Field(examples=["$615,704.13", "7.78%", "2,581"])


class Answer(_Model):
    summary: str = Field(description="One or two plain-language sentences generated from result values")
    headline: Headline | None = None


class Assumption(_Model):
    code: str = Field(examples=["DEFAULT_DATE_RANGE"])
    message: str


class Reason(_Model):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class VerificationCheck(_Model):
    id: str = Field(examples=["V09"])
    name: str = Field(examples=["reconciliation"])
    status: CheckStatus
    detail: str


class Verification(_Model):
    status: ValidationStatus
    summary: str
    reasons: list[Reason]
    checks: list[VerificationCheck]


class ClarificationOption(_Model):
    id: str
    label: str
    description: str
    suggested_question: str = Field(description="Re-submit this text as a new question to pick the option")


class Clarification(_Model):
    prompt: str
    options: list[ClarificationOption] = Field(min_length=2)


class Timing(_Model):
    total_ms: float
    planning_ms: float
    validation_ms: float
    execution_ms: float | None
    verification_ms: float | None


class PlannerInfo(_Model):
    name: str = Field(examples=["langchain-meta", "langchain-anthropic", "rules-demo"])
    model: str | None = Field(None, description="LLM model id; null for the rule-based demo planner")
    provider: Literal["meta", "anthropic", "metricguard-rules"] | None = Field(
        None, description="Who produced the plan (added in 1.2.0). 'meta' = Meta Model API, 'anthropic' = Anthropic, "
        "'metricguard-rules' = the deterministic demo planner.")
    execution_mode: ExecutionMode = Field(
        description="LLM: plan produced by LangChain + a real model provider (see `provider`). DEMO_RULE_BASED: deterministic keyword rules, "
        "not an LLM - the UI must disclose this.")
    disclosure: str | None = Field(None, description="User-facing disclosure text; set for DEMO_RULE_BASED")


class AuditRef(_Model):
    persisted: bool
    url: str | None = Field(None, examples=["/api/audit/0b6f..."])


class AnalyzeResponse(_Model):
    request_id: str
    created_at: datetime
    api_version: str
    status: ValidationStatus
    question: str
    answer: Answer | None
    plan: QueryPlan | None
    assumptions: list[Assumption]
    metrics: list[MetricUsage]
    sql: SqlBlock | None
    result: ResultBlock | None
    chart: ChartSpec | None
    verification: Verification
    clarification: Clarification | None
    timing: Timing
    planner: PlannerInfo
    audit: AuditRef
    error: ErrorBody | None


# --------------------------------------------------------------------------------------
# GET /api/audit, GET /api/audit/{request_id}
# --------------------------------------------------------------------------------------
class AuditSummary(_Model):
    request_id: str
    created_at: datetime
    question: str
    status: ValidationStatus
    metric_refs: list[str] = Field(examples=[["net_revenue@1.0.0"]])
    row_count: int | None
    total_ms: float | None
    planner: str | None
    execution_mode: ExecutionMode | None = Field(None, description="null for rows written before v1.1.0")


class AuditListResponse(_Model):
    items: list[AuditSummary]
    total: int
    limit: int
    offset: int


class AuditSql(_Model):
    text: str
    parameters: list[SqlParameterOut]
    sql_hash: str


class AuditTiming(_Model):
    total_ms: float | None
    planning_ms: float | None
    validation_ms: float | None
    execution_ms: float | None
    verification_ms: float | None


class AuditMetricDefinition(_Model):
    ref: str = Field(examples=["net_revenue@1.0.0"])
    definition_hash: str
    db2_hash_match: bool | None = Field(None, description="null when the Db2 registry was not read")


class AuditDetail(_Model):
    request_id: str
    created_at: datetime
    api_version: str
    question: str
    status: ValidationStatus
    status_reason: str | None
    planner: str | None
    metric_refs: list[str]
    plan: QueryPlan | None
    sql: AuditSql | None
    verification: Verification | None
    result_preview: ResultBlock | None = Field(description="First 20 rows of the result")
    row_count: int | None
    timing: AuditTiming
    error: ErrorBody | None
    execution_mode: ExecutionMode | None = None
    planner_model: str | None = None
    metric_definitions: list[AuditMetricDefinition] = Field(default_factory=list)
    answer_summary: str | None = None
