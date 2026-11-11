"""EXPLAIN service — ``POST /api/v1/sql/explain``.

Order of operations (same safety contract as execution):

1. Validate through the sqlglot gate (fail-closed, rejection is audited).
2. Apply the deterministic row cap, so the *same* statement that would run is
   the one explained.
3. Ask the adapter for the access plan. The adapter never raises: a missing
   driver / EXPLAIN tables / privilege is reported as ``UNAVAILABLE`` with an
   actionable hint (graceful fallback), a statement Db2 rejects as ``FAILED``.
4. Summarize the plan in plain language (full scans, sorts, joins).

EXPLAIN never executes the statement.
"""

from __future__ import annotations

import json
import logging
import time

from app.adapters.base import AuditRecord, ExplainResult
from app.adapters.registry import AdapterRegistry
from app.core.clock import utc_now_iso
from app.core.config import Settings
from app.core.errors import SqlRejectedError
from app.schemas.dba import (
    ExplainObjectModel,
    ExplainOperatorModel,
    ExplainResponse,
)
from app.security.sanitize import sanitize_metadata
from app.services.sql_guard_service import SqlGuardService

logger = logging.getLogger(__name__)

_OPERATOR_TEXT = {
    "TBSCAN": "full table scan",
    "IXSCAN": "index scan",
    "FETCH": "row fetch via index",
    "SORT": "sort",
    "HSJOIN": "hash join",
    "NLJOIN": "nested-loop join",
    "MSJOIN": "merge join",
    "GRPBY": "grouping/aggregation",
    "FILTER": "post-filter",
}


def summarize_plan(result: ExplainResult) -> list[str]:
    """Plain-language findings derived only from the operators we were given."""
    if result.status != "OK":
        return []
    lines: list[str] = []
    types = [op.operator_type.upper() for op in result.operators]
    tables = [o for o in result.objects if o.object_type == "TABLE"]
    indexes = [o for o in result.objects if o.object_type == "INDEX"]
    if result.total_cost is not None:
        lines.append(f"Estimated total cost: {result.total_cost:g} timerons.")
    scans = types.count("TBSCAN")
    if scans:
        names = ", ".join(f"{t.schema_name}.{t.name}" for t in tables) or "a table"
        lines.append(
            f"{scans} full table scan(s) over {names} — consider an index on the "
            "filter/join columns if the table is large."
        )
    if indexes:
        lines.append(
            "Index access used: " + ", ".join(f"{i.schema_name}.{i.name}" for i in indexes) + "."
        )
    for kind in ("SORT", "HSJOIN", "NLJOIN", "MSJOIN", "GRPBY"):
        if kind in types:
            lines.append(f"Plan contains a {_OPERATOR_TEXT[kind]}.")
    return lines


class ExplainService:
    def __init__(
        self, settings: Settings, registry: AdapterRegistry, guard: SqlGuardService
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._guard = guard

    def explain(
        self, sql: str, *, request_id: str, session_id: str | None = None
    ) -> ExplainResponse:
        started = time.perf_counter()
        snippet = sanitize_metadata(sql) or sql[:2000]

        validation = self._guard.validate(sql)
        if not validation.valid:
            codes = ", ".join(v.code for v in validation.violations)
            self._audit(
                snippet,
                status="REJECTED_BY_GATE",
                latency_ms=_ms(started),
                request_id=request_id,
                session_id=session_id,
                detail=f"SQL rejected by validation gate: {codes}",
                extra={"violations": [v.code for v in validation.violations]},
            )
            raise SqlRejectedError(
                "SQL was rejected by the validation gate.",
                detail={
                    "violations": [
                        {"code": v.code, "message": v.message}
                        for v in validation.violations
                    ]
                },
            )

        prepared = self._guard.prepare_for_execution(validation.normalized_sql or sql)
        try:
            plan = self._registry.database.explain_plan(
                prepared.sql, self._settings.sql_query_timeout_ms
            )
        except Exception as exc:  # noqa: BLE001 — adapters must not raise; stay total
            logger.warning("explain_plan raised %s", type(exc).__name__)
            plan = ExplainResult(
                status="UNAVAILABLE",
                source="none",
                hint="EXPLAIN is temporarily unavailable.",
                detail=type(exc).__name__,
            )

        latency = _ms(started)
        self._audit(
            snippet,
            status="OK" if plan.status == "OK" else plan.status,
            latency_ms=latency,
            request_id=request_id,
            session_id=session_id,
            detail=f"EXPLAIN {plan.status} (source={plan.source})",
            extra={
                "status": plan.status,
                "source": plan.source,
                "sqlstate": plan.sqlstate,
                "total_cost": plan.total_cost,
            },
        )
        return ExplainResponse(
            request_id=request_id,
            mock=self._registry.mode == "mock",
            status=plan.status,  # type: ignore[arg-type]
            source=plan.source,  # type: ignore[arg-type]
            explained_sql=prepared.sql,
            total_cost=plan.total_cost,
            operators=[
                ExplainOperatorModel(
                    operator_id=o.operator_id,
                    operator_type=o.operator_type,
                    total_cost=o.total_cost,
                    io_cost=o.io_cost,
                    cpu_cost=o.cpu_cost,
                )
                for o in plan.operators
            ],
            objects=[
                ExplainObjectModel(
                    schema_name=o.schema_name, name=o.name, object_type=o.object_type
                )
                for o in plan.objects
            ],
            summary=summarize_plan(plan),
            sqlstate=plan.sqlstate,
            hint=plan.hint,
            detail=plan.detail,
            warnings=list(plan.warnings) + list(prepared.warnings),
            latency_ms=latency,
        )

    def _audit(
        self,
        snippet: str,
        *,
        status: str,
        latency_ms: int,
        request_id: str,
        session_id: str | None,
        detail: str,
        extra: dict,
    ) -> None:
        try:
            self._registry.audit.record(
                AuditRecord(
                    intent="data",
                    question=f"Explain SQL: {snippet[:200]}",
                    status=status,
                    latency_ms=latency_ms,
                    request_id=request_id,
                    session_id=session_id,
                    operation="sql_explain",
                    sql_text=snippet,
                    detail=detail,
                    metadata=json.dumps(extra, default=str),
                    timestamp=utc_now_iso(),
                )
            )
        except Exception as exc:  # noqa: BLE001 — audit is best-effort
            logger.warning("explain audit write failed (%s)", type(exc).__name__)


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
