"""Chat service — the request flow behind POST /api/v1/chat.

Flow (identical for mock and real modes):

1. Prompt-injection screening (block/flag/off per settings).
2. Orchestrate (mock canned pipeline | real LangChain pipeline).
3. Re-validate any emitted SQL through the real sqlglot gate — even if the
   orchestrator already checked it (defense in depth, never trust the model).
4. Best-effort audit write (failures are logged + surfaced as warnings, they
   never break the user response; audit correctness is verified in M2 against
   the real APP_AUDIT table).
"""

from __future__ import annotations

import logging
import time

from app.adapters.base import AuditRecord
from app.adapters.registry import AdapterRegistry
from app.core.config import Settings
from app.core.errors import AppError, PromptInjectionBlockedError
from app.schemas.chat import ChatRequest, ChatResponse, Timings
from app.security.injection import screen_message

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, settings: Settings, registry: AdapterRegistry) -> None:
        self._settings = settings
        self._registry = registry

    # ------------------------------------------------------------------
    def ask(self, request: ChatRequest, request_id: str) -> ChatResponse:
        start = time.perf_counter()
        warnings: list[str] = []
        intent = "general"

        try:
            verdict = screen_message(request.message, self._settings.injection_mode)
            if verdict.flagged:
                warnings.extend(verdict.warnings)

            result = self._registry.orchestrator.respond(
                request.message, request.mode
            )
            intent = result.intent

            sql = result.sql
            if sql:
                validation = self._registry.validator.validate(sql)
                if validation.valid:
                    warnings.extend(
                        f"{w.code}: {w.message}" for w in validation.warnings
                    )
                else:
                    sql = None
                    codes = ", ".join(v.code for v in validation.violations)
                    warnings.append(
                        f"generated SQL rejected by validation gate ({codes})"
                    )

            total_ms = int((time.perf_counter() - start) * 1000)
            response = ChatResponse(
                reply=result.reply,
                intent=intent,  # type: ignore[arg-type]
                citations=[
                    {
                        "source": c.source,
                        "title": c.title,
                        "snippet": c.snippet,
                        "score": c.score,
                    }
                    for c in result.citations
                ],
                sql=sql,
                mock=self._registry.mode == "mock",
                request_id=request_id,
                timings=Timings(
                    total_ms=total_ms,
                    retrieval_ms=result.retrieval_ms,
                    generation_ms=result.generation_ms,
                ),
                warnings=warnings,
            )
            audit_status = "OK"
            audit_detail = "; ".join(warnings) or None
            audit_intent = intent

        except AppError as exc:
            # Re-raise after auditing — failures must be traceable too.
            total_ms = int((time.perf_counter() - start) * 1000)
            self._safe_audit(
                AuditRecord(
                    intent="error",
                    question=request.message,
                    status="BLOCKED"
                    if isinstance(exc, PromptInjectionBlockedError)
                    else "ERROR",
                    latency_ms=total_ms,
                    detail=f"{exc.code}: {exc.message}",
                    request_id=request_id,
                    timestamp=_now(),
                )
            )
            raise

        self._safe_audit(
            AuditRecord(
                intent=audit_intent,
                question=request.message,
                status=audit_status,
                latency_ms=response.timings.total_ms,
                detail=audit_detail,
                request_id=request_id,
                timestamp=_now(),
            )
        )
        return response

    # ------------------------------------------------------------------
    def _safe_audit(self, entry: AuditRecord) -> None:
        try:
            self._registry.audit.record(entry)
        except Exception as exc:  # noqa: BLE001 — audit is best-effort at runtime
            logger.error(
                "audit write failed (%s): %s", type(exc).__name__, exc, exc_info=True
            )


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
