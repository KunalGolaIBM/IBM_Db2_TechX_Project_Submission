"""SQL execution service — the audited, capped execution path (M2.6).

The order of operations below is fixed and never re-ordered:

1. **Validate** — the sqlglot gate (fail-closed). Rejections are written to
   APP.QUERY_EXECUTIONS *and* APP_AUDIT before a ``SqlRejectedError`` is
   raised, so denied statements are traceable like successful ones.
2. **Prepare** — deterministic hard row cap (``SqlGuardService`` wrap).
3. **Explain** — best-effort dry-run (``SQL_EXPLAIN_DRY_RUN``); failure
   never blocks execution (``explain_status`` reports OK/FAILED/DISABLED).
4. **Execute** — via the ``DatabaseAdapter`` under the read-only account
   with the session query timeout; values are normalized to JSON-safe types.
5. **Record** — an APP.QUERY_EXECUTIONS row for every attempt, success or
   failure (best-effort: a history write failure is logged, never masking
   the query result or error).

Security invariants (see docs/ARCHITECTURE.md):
- Only SQL that passed the gate in step 1 reaches the database — ever.
- The service never builds SQL by string concatenation with user input;
  the row-cap wrap is a fixed template over already-validated SQL.
- Errors surfaced to callers are the application error types (sanitized
  envelope); raw driver text never leaves the adapter.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.adapters.base import AuditRecord, ExecutionRecord
from app.adapters.registry import AdapterRegistry
from app.core.clock import utc_now_iso
from app.core.config import Settings
from app.core.errors import AppError, SqlRejectedError, UpstreamTimeoutError
from app.core.serialize import json_safe
from app.schemas.sql import SqlExecutionResponse, SqlValidateResponse
from app.security.sanitize import sanitize_metadata
from app.services.sql_guard_service import SqlGuardService

logger = logging.getLogger(__name__)

_SQL_SNIPPET_MAX = 2000  # matches app.security.sanitize.MAX_LEN budget


_json_safe = json_safe  # kept for backwards-compatible imports


class SqlExecutionService:
    def __init__(
        self,
        settings: Settings,
        registry: AdapterRegistry,
        guard: SqlGuardService,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._guard = guard

    # ------------------------------------------------------------------
    def execute(
        self,
        sql: str,
        *,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> SqlExecutionResponse:
        started = time.perf_counter()
        warnings: list[str] = []

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started) * 1000)

        # 1 — validation gate (fail-closed) ------------------------------
        validation = self._guard.validate(sql)
        if not validation.valid:
            self._on_rejected(
                sql,
                validation,
                request_id=request_id,
                session_id=session_id,
                latency_ms=elapsed_ms(),
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

        # 2 — deterministic hard row cap ---------------------------------
        prepared = self._guard.prepare_for_execution(
            validation.normalized_sql or sql
        )
        warnings.extend(prepared.warnings)

        # 3 — best-effort EXPLAIN dry-run --------------------------------
        explain_status = "DISABLED"
        if self._settings.sql_explain_dry_run:
            try:
                accepted = self._registry.database.explain(prepared.sql)
            except Exception:  # noqa: BLE001 — explain must never block
                accepted = False
            explain_status = "OK" if accepted else "FAILED"
            if not accepted:
                warnings.append(
                    "EXPLAIN dry-run unavailable; execution continued "
                    "(validation gate and row/timeout caps remain enforced)."
                )

        # 4 — execution under the read-only account ----------------------
        try:
            result = self._registry.database.execute_readonly(
                prepared.sql,
                params=None,
                timeout_ms=self._settings.sql_query_timeout_ms,
            )
        except AppError as exc:
            failure_status = (
                "TIMEOUT" if isinstance(exc, UpstreamTimeoutError) else "ERROR"
            )
            snippet = sanitize_metadata(prepared.sql) or prepared.sql[:_SQL_SNIPPET_MAX]
            self._record(
                ExecutionRecord(
                    sql=snippet,
                    validation_status="PASSED",
                    explain_status=explain_status,
                    execution_status=failure_status,
                    latency_ms=elapsed_ms(),
                    sqlstate=_sqlstate_of(exc),
                    request_id=request_id,
                    detail=exc.message,
                )
            )
            self._audit(
                _sql_audit(
                    snippet,
                    status=failure_status,
                    latency_ms=elapsed_ms(),
                    request_id=request_id,
                    session_id=session_id,
                    detail=f"{exc.code}: {exc.message}",
                    extra={"sqlstate": _sqlstate_of(exc)},
                )
            )
            raise

        # 5 — execution history + audit (best-effort) ---------------------
        ok_snippet = sanitize_metadata(prepared.sql) or prepared.sql[:_SQL_SNIPPET_MAX]
        self._record(
            ExecutionRecord(
                sql=ok_snippet,
                validation_status="PASSED",
                explain_status=explain_status,
                execution_status="OK",
                row_count=result.row_count,
                truncated=result.truncated,
                latency_ms=elapsed_ms(),
                request_id=request_id,
            )
        )
        self._audit(
            _sql_audit(
                ok_snippet,
                status="OK",
                latency_ms=elapsed_ms(),
                request_id=request_id,
                session_id=session_id,
                detail=f"{result.row_count} row(s) returned",
                extra={
                    "row_count": result.row_count,
                    "truncated": result.truncated,
                    "explain_status": explain_status,
                },
            )
        )

        if result.truncated:
            warnings.append(
                f"Result truncated to the policy row cap of "
                f"{self._settings.sql_max_rows} rows."
            )

        return SqlExecutionResponse(
            request_id=request_id or "-",
            mock=self._registry.mode == "mock",
            executed_sql=prepared.sql,
            row_limit=prepared.row_limit,
            row_limit_applied=prepared.row_limit_applied,
            explain_status=explain_status,  # type: ignore[arg-type]
            columns=list(result.columns),
            rows=[[_json_safe(v) for v in row] for row in result.rows],
            row_count=result.row_count,
            truncated=result.truncated,
            latency_ms=int(result.latency_ms),
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    def _on_rejected(
        self,
        sql: str,
        validation: SqlValidateResponse,
        *,
        request_id: str | None,
        session_id: str | None,
        latency_ms: int,
    ) -> None:
        """Persist a rejected attempt (history + audit), never raising."""
        codes = ", ".join(v.code for v in validation.violations)
        snippet = sanitize_metadata(sql) or sql[:_SQL_SNIPPET_MAX]
        self._record(
            ExecutionRecord(
                sql=snippet,
                validation_status="REJECTED",
                explain_status="SKIPPED",
                execution_status="REJECTED",
                latency_ms=latency_ms,
                request_id=request_id,
                detail=f"violations: {codes}",
            )
        )
        self._audit(
            _sql_audit(
                snippet,
                status="REJECTED_BY_GATE",
                latency_ms=latency_ms,
                request_id=request_id,
                session_id=session_id,
                detail=f"SQL rejected by validation gate: {codes}",
                extra={"violations": [v.code for v in validation.violations]},
            )
        )

    def _record(self, record: ExecutionRecord) -> None:
        """Best-effort APP.QUERY_EXECUTIONS write — never masks the outcome."""
        try:
            self._registry.database.record_execution(record)
        except Exception as exc:  # noqa: BLE001 — history must not break requests
            logger.warning(
                "execution-history write failed (%s): %s",
                type(exc).__name__,
                exc,
            )

    def _audit(self, entry: AuditRecord) -> None:
        """Best-effort APP_AUDIT write for rejected executions."""
        try:
            self._registry.audit.record(entry)
        except Exception as exc:  # noqa: BLE001 — audit is best-effort here
            logger.warning("rejected-query audit write failed (%s): %s", type(exc).__name__, exc)


def _sql_audit(
    snippet: str,
    *,
    status: str,
    latency_ms: int,
    request_id: str | None,
    session_id: str | None,
    detail: str,
    extra: dict[str, Any],
) -> AuditRecord:
    """Build the APP_AUDIT row for a /sql/execute attempt.

    ``question`` carries a human-readable summary (the SQL is the "question"
    for direct execution) and the timestamp is always populated.
    """
    return AuditRecord(
        intent="data",
        question=f"Execute SQL: {snippet[:200]}",
        status=status,
        latency_ms=latency_ms,
        request_id=request_id,
        session_id=session_id,
        operation="sql_execute",
        sql_text=snippet,
        detail=detail,
        metadata=json.dumps(extra, ensure_ascii=False, default=str),
        timestamp=utc_now_iso(),
    )


def _sqlstate_of(exc: AppError) -> str | None:
    detail = exc.detail
    if isinstance(detail, dict):
        value = detail.get("sqlstate")
        if isinstance(value, str):
            return value
    return None
