"""Adapter contracts — the clean interfaces between the app and its integrations.

Every external concern is expressed as a Protocol so the application core never
imports a driver, SDK or framework directly:

1. Db2 database connectivity        -> ``DatabaseAdapter``
2. Db2 vector-store operations      -> ``VectorStoreAdapter``
3. Ollama chat model                -> ``ChatModelAdapter``
4. Ollama embedding model           -> ``EmbeddingModelAdapter``
5. LangChain orchestration          -> ``OrchestrationAdapter``
6. SQL validation                   -> ``SqlValidator``
7. Audit persistence                -> ``AuditAdapter``

Two implementations exist for each service adapter:

- ``mock_*``   — deterministic, in-memory, fully offline (development/tests).
- real ones    — lazy-import their driver and report ``unavailable`` via
                 ``ping()`` when the dependency/service is missing (M2+).

Mocks are NEVER the production implementation: ``ADAPTER_MODE=real`` selects
the real adapters (see ``app.adapters.registry``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence, runtime_checkable

from app.schemas.sql import SqlValidateResponse

ProbeStatus = Literal["ok", "degraded", "unavailable"]
AdapterKind = Literal["mock", "real"]
Intent = Literal["docs", "data", "general"]


# --------------------------------------------------------------------------
# Shared value objects
# --------------------------------------------------------------------------
@dataclass(slots=True)
class ProbeResult:
    name: str
    status: ProbeStatus
    mode: AdapterKind
    latency_ms: float
    detail: str


@dataclass(slots=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    latency_ms: float = 0.0


@dataclass(slots=True)
class SchemaColumn:
    name: str
    data_type: str
    nullable: bool = True


@dataclass(slots=True)
class SchemaTable:
    name: str
    schema_name: str | None
    columns: list[SchemaColumn] = field(default_factory=list)


@dataclass(slots=True)
class SchemaSnapshot:
    tables: list[SchemaTable]
    source: str  # "mock" | "SYSCAT"
    latency_ms: float = 0.0


@dataclass(slots=True)
class ExplainOperator:
    """One row of EXPLAIN_OPERATOR (or its mock equivalent)."""

    operator_id: int
    operator_type: str  # TBSCAN, IXSCAN, FETCH, SORT, HSJOIN, RETURN, ...
    total_cost: float | None = None
    io_cost: float | None = None
    cpu_cost: float | None = None


@dataclass(slots=True)
class ExplainObject:
    """A table/index touched by the plan (EXPLAIN_OBJECT)."""

    schema_name: str
    name: str
    object_type: str  # TABLE | INDEX


@dataclass(slots=True)
class ExplainResult:
    """Outcome of an EXPLAIN attempt. Never raises: failures are statuses.

    ``status``:
    - ``OK``          a plan was produced (``source`` says by whom)
    - ``UNAVAILABLE`` Db2 cannot explain here (no connection, driver, EXPLAIN
                      tables or privilege) — ``hint`` says how to fix it
    - ``FAILED``      Db2 rejected the statement itself
    """

    status: str
    source: str  # "db2" | "mock" | "none"
    total_cost: float | None = None
    operators: list[ExplainOperator] = field(default_factory=list)
    objects: list[ExplainObject] = field(default_factory=list)
    sqlstate: str | None = None
    hint: str | None = None
    detail: str | None = None
    warnings: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


@dataclass(slots=True)
class DbaToolResult:
    """Rows returned by one DBA tool (catalog or monitoring)."""

    tool_id: str
    source: str  # "db2" | "mock"
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool = False
    latency_ms: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AdminResult:
    """Outcome of executing one APPROVED maintenance statement."""

    status: str  # EXECUTED | SIMULATED
    simulated: bool
    detail: str
    latency_ms: float = 0.0


@dataclass(slots=True)
class DocumentInput:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VectorHit:
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelResult:
    text: str
    model: str
    latency_ms: float
    usage: dict[str, int] | None = None


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dimensions: int
    latency_ms: float


@dataclass(slots=True)
class CitationDraft:
    source: str
    title: str
    snippet: str
    score: float | None = None


@dataclass(slots=True)
class OrchestratorResult:
    reply: str
    intent: Intent
    citations: list[CitationDraft] = field(default_factory=list)
    sql: str | None = None
    retrieval_ms: int | None = None
    generation_ms: int | None = None


@dataclass(slots=True)
class AuditRecord:
    intent: str
    question: str
    status: str
    latency_ms: int
    detail: str | None = None
    request_id: str | None = None
    id: int = 0
    timestamp: str = ""
    # M2 extensions — persisted into the extended APP_AUDIT schema:
    operation: str = "chat"  # chat | sql_validate | sql_execute | ...
    session_id: str | None = None
    sql_text: str | None = None
    # Sanitized JSON (never passwords/tokens/DSNs — adapters re-sanitize).
    metadata: str | None = None


@dataclass(slots=True)
class ExecutionRecord:
    """One row of APP.QUERY_EXECUTIONS (history of executed/rejected queries)."""

    sql: str
    validation_status: str  # PASSED | REJECTED
    explain_status: str | None = None  # OK | FAILED | SKIPPED | DISABLED
    execution_status: str = "NOT_EXECUTED"  # OK | ERROR | TIMEOUT | REJECTED
    row_count: int | None = None
    truncated: bool = False
    latency_ms: int = 0
    sqlstate: str | None = None
    request_id: str | None = None
    detail: str | None = None
    id: int = 0
    timestamp: str = ""


# --------------------------------------------------------------------------
# Protocols (the actual contracts)
# --------------------------------------------------------------------------
@runtime_checkable
class DatabaseAdapter(Protocol):
    """Read-only Db2 connectivity (execute + schema introspection)."""

    probe_name: str
    provider_id: str
    mode: AdapterKind

    def ping(self) -> ProbeResult: ...

    def execute_readonly(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        timeout_ms: int | None = None,
    ) -> QueryResult: ...

    def explain(self, sql: str, timeout_ms: int | None = None) -> bool:
        """Best-effort EXPLAIN dry-run for an already-validated statement.

        Returns True when the server accepted the plan, False otherwise.
        NEVER raises: the dry-run is advisory (accounts often lack EXPLAIN
        privileges / plan tables) and must not block execution.
        """

    def execute_admin_statement(self, statement: str) -> AdminResult:
        """Execute ONE human-approved maintenance statement (RUNSTATS, CREATE INDEX).

        Only ``app.services.approval_service`` may call this, after the
        approval state machine and ``app.agent.actions.prepare_action``
        re-validation. The mock simulates; the real adapter uses the separate
        privileged account and raises when it is not configured.
        """

    def explain_plan(self, sql: str, timeout_ms: int | None = None) -> ExplainResult:
        """EXPLAIN an already-validated SELECT and return the access plan.

        NEVER raises — see :class:`ExplainResult` for the status contract.
        """

    def fetch_schema(self) -> SchemaSnapshot: ...

    # Execution history (APP.QUERY_EXECUTIONS in real mode, memory in mock).
    def record_execution(self, record: ExecutionRecord) -> int: ...

    def list_executions(self, limit: int = 20) -> list[ExecutionRecord]: ...

    def close(self) -> None: ...


@runtime_checkable
class VectorStoreAdapter(Protocol):
    """Db2-backed vector store operations (DB2VS in real mode)."""

    probe_name: str
    provider_id: str
    mode: AdapterKind

    def ping(self) -> ProbeResult: ...

    def similarity_search(
        self, query: str, k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[VectorHit]: ...

    def upsert_documents(self, documents: list[DocumentInput]) -> int: ...

    def delete(self, ids: list[str]) -> int: ...

    def count(self) -> int: ...

    def close(self) -> None: ...


@runtime_checkable
class ChatModelAdapter(Protocol):
    """Chat/completion model (Ollama in real mode)."""

    probe_name: str
    provider_id: str
    mode: AdapterKind

    def ping(self) -> ProbeResult: ...

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> ModelResult: ...

    def close(self) -> None: ...


@runtime_checkable
class EmbeddingModelAdapter(Protocol):
    """Embedding model (nomic-embed-text via Ollama in real mode)."""

    probe_name: str
    provider_id: str
    mode: AdapterKind

    def ping(self) -> ProbeResult: ...

    def embed(self, texts: list[str]) -> EmbeddingResult: ...

    @property
    def dimensions(self) -> int: ...

    def close(self) -> None: ...


@runtime_checkable
class OrchestrationAdapter(Protocol):
    """Pipeline orchestration (LangChain in real mode)."""

    probe_name: str
    provider_id: str
    mode: AdapterKind

    def ping(self) -> ProbeResult: ...

    def respond(self, message: str, mode: str = "auto") -> OrchestratorResult: ...

    def close(self) -> None: ...


@runtime_checkable
class SqlValidator(Protocol):
    """AST-based SQL validation gate (local compute — always 'real')."""

    def validate(self, sql: str) -> SqlValidateResponse: ...


@runtime_checkable
class AuditAdapter(Protocol):
    """Audit persistence (APP_AUDIT table in Db2 in real mode)."""

    probe_name: str
    provider_id: str
    mode: AdapterKind

    def ping(self) -> ProbeResult: ...

    def record(self, entry: AuditRecord) -> int: ...

    def list_recent(self, limit: int = 50) -> list[AuditRecord]: ...

    def close(self) -> None: ...
