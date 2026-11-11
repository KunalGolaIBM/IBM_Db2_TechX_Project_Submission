"""DBA tool service — validated, audited execution of the fixed tool templates.

Flow for ``run()``: look up the tool (404 if unknown) -> validate parameters
(422) -> execute the FIXED template through the database adapter (qmark
binding) -> sanitize statement text coming back from monitoring views ->
audit the attempt (best-effort).

Tools never accept SQL. The only caller-influenced text is a validated
identifier bound as a parameter and a validated integer row limit.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.adapters.base import AuditRecord
from app.adapters.registry import AdapterRegistry
from app.core.clock import utc_now_iso
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.serialize import json_safe
from app.dba.specs import TOOLS, TOOLS_BY_ID, ToolSpec, resolve_params
from app.schemas.dba import (
    DbaRunResponse,
    DbaToolInfo,
    DbaToolParam,
    DbaToolsResponse,
)
from app.security.sanitize import sanitize_metadata

logger = logging.getLogger(__name__)

# Columns that carry statement text from the package cache: literals inside
# can contain secrets, so they pass through the same redactor as audit rows.
_TEXT_COLUMNS = {"STMT_TEXT"}


def _info(spec: ToolSpec) -> DbaToolInfo:
    return DbaToolInfo(
        id=spec.id,
        kind=spec.kind,
        title=spec.title,
        description=spec.description,
        params=[
            DbaToolParam(name=p.name, required=p.required, description=p.description)
            for p in spec.params
        ],
        requires=spec.requires,
    )


class DbaService:
    def __init__(self, settings: Settings, registry: AdapterRegistry) -> None:
        self._settings = settings
        self._registry = registry

    def list_tools(self) -> DbaToolsResponse:
        return DbaToolsResponse(
            tools=[_info(t) for t in TOOLS], mock=self._registry.mode == "mock"
        )

    def run(
        self,
        tool_id: str,
        params: dict[str, Any] | None,
        *,
        request_id: str,
        session_id: str | None = None,
    ) -> DbaRunResponse:
        started = time.perf_counter()
        spec = TOOLS_BY_ID.get(tool_id)
        if spec is None:
            raise NotFoundError(
                f"Unknown DBA tool '{tool_id}'.",
                detail={"available": sorted(TOOLS_BY_ID)},
            )

        try:
            resolved = resolve_params(spec, params, self._settings)
            result = self._registry.database.run_dba_tool(
                spec.id, spec.render(resolved.limit), resolved.bound, resolved.limit
            )
        except AppError as exc:
            self._audit(
                spec,
                status="REJECTED" if exc.status_code == 422 else "ERROR",
                latency_ms=_ms(started),
                request_id=request_id,
                session_id=session_id,
                detail=f"{exc.code}: {exc.message}",
                extra={"params": _safe_params(params), "code": exc.code},
            )
            raise

        text_idx = {i for i, c in enumerate(result.columns) if c.upper() in _TEXT_COLUMNS}
        rows = [
            [
                (sanitize_metadata(v) if i in text_idx and isinstance(v, str) else json_safe(v))
                for i, v in enumerate(row)
            ]
            for row in result.rows
        ]
        latency = _ms(started)
        self._audit(
            spec,
            status="OK",
            latency_ms=latency,
            request_id=request_id,
            session_id=session_id,
            detail=f"{len(rows)} row(s) returned",
            extra={"params": resolved.applied, "row_count": len(rows), "source": result.source},
        )
        return DbaRunResponse(
            request_id=request_id,
            tool_id=spec.id,
            kind=spec.kind,
            title=spec.title,
            mock=self._registry.mode == "mock",
            source=result.source,  # type: ignore[arg-type]
            params=resolved.applied,
            columns=list(result.columns),
            rows=rows,
            row_count=len(rows),
            truncated=result.truncated,
            latency_ms=latency,
            notes=list(result.notes),
        )

    # ------------------------------------------------------------------
    def _audit(
        self,
        spec: ToolSpec,
        *,
        status: str,
        latency_ms: int,
        request_id: str,
        session_id: str | None,
        detail: str,
        extra: dict[str, Any],
    ) -> None:
        try:
            self._registry.audit.record(
                AuditRecord(
                    intent="ops",
                    question=f"Run DBA tool: {spec.id}",
                    status=status,
                    latency_ms=latency_ms,
                    request_id=request_id,
                    session_id=session_id,
                    operation="dba_tool",
                    detail=detail,
                    metadata=json.dumps({"tool": spec.id, **extra}, default=str),
                    timestamp=utc_now_iso(),
                )
            )
        except Exception as exc:  # noqa: BLE001 — audit is best-effort
            logger.warning("dba tool audit write failed (%s)", type(exc).__name__)


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _safe_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Echo caller params into the audit trail, bounded and stringified."""
    return {str(k)[:32]: str(v)[:64] for k, v in list((params or {}).items())[:8]}
