"""Approval service: proposals, human decisions, authorized execution, audit.

Safety contract (each point has a test):

1. The agent can only *create* PENDING approvals (``propose``). It has no
   handle on ``decide``; deciding is a separate API call made by a human.
2. Rejected / expired / already-decided approvals can never execute.
3. At execution time the statement is re-rendered from the structured
   parameters, compared with what the human approved and matched against the
   allow-list (``prepare_action``). Tampering -> FAILED, nothing runs.
4. Execution uses ``DatabaseAdapter.execute_admin_statement`` — the separate,
   opt-in privileged path. The free-form SQL gate and read-only account are
   never involved or weakened.
5. Every transition (requested, approved, rejected, expired, executed, failed)
   is written to the audit trail (best-effort, never masks the outcome).
6. ``decide`` accepts ONLY the exact strings ``"approve"`` / ``"reject"``;
   any other value raises ``ApprovalDecisionError`` (422) BEFORE any state
   change, so a typo can never be mistaken for an approval (P0.3).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.adapters.base import AuditRecord
from app.adapters.registry import AdapterRegistry
from app.agent import approvals as states
from app.agent.actions import ActionError, PreparedAction, prepare_action
from app.agent.approvals import (
    Approval,
    ApprovalDecisionError,
    ApprovalStore,
)
from app.core.clock import utc_now_iso
from app.core.config import Settings
from app.core.errors import AppError
from app.security.sanitize import sanitize_metadata

logger = logging.getLogger(__name__)

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_actor(value: str | None) -> str:
    """Bounded, control-character-free actor label for the audit trail."""
    cleaned = _CONTROL.sub(" ", value or "").strip()[:64]
    return cleaned or "operator"


class ApprovalService:
    def __init__(self, settings: Settings, registry: AdapterRegistry, store: ApprovalStore) -> None:
        self._settings = settings
        self._registry = registry
        self._store = store

    # -- agent-facing: propose only -------------------------------------------------
    def propose(
        self,
        prepared: PreparedAction,
        *,
        rationale: str,
        request_id: str | None,
        session_id: str | None,
        title: str | None = None,
    ) -> Approval:
        approval = self._store.create(
            action_type=prepared.type,
            params=prepared.params,
            statement=prepared.statement,
            title=title or prepared.spec.title,
            rationale=rationale,
            risk=prepared.spec.risk,
            ttl_seconds=self._settings.approval_ttl_seconds,
            request_id=request_id,
            session_id=session_id,
        )
        self._audit(approval, "APPROVAL_REQUESTED", by="agent", detail="Action proposed; awaiting human decision.")
        return approval

    # -- reads ---------------------------------------------------------------------------
    def list(self, status: str | None = None, limit: int = 50) -> list[Approval]:
        self._sweep()
        return self._store.list(status, limit)

    def get(self, approval_id: str) -> Approval:
        self._sweep()
        return self._store.get(approval_id)

    # -- human-facing: decide -----------------------------------------------------------------
    def decide(
        self,
        approval_id: str,
        decision: str,
        *,
        decided_by: str | None,
        reason: str | None,
        request_id: str | None = None,
    ) -> Approval:
        # Fail closed: ONLY the exact supported decisions are accepted, and the
        # check happens before any state change or execution (P0.3). Anything
        # else — typos, casing, whitespace — must never read as an approval.
        if not isinstance(decision, str) or decision not in states.DECISIONS:
            raise ApprovalDecisionError(
                f"Unsupported decision {decision!r}: expected one of "
                f"{', '.join(sorted(states.DECISIONS))}.",
                detail={"supported": sorted(states.DECISIONS)},
            )
        actor = clean_actor(decided_by)
        note = sanitize_metadata(reason) if reason else None
        self._sweep()

        if decision == "reject":
            approval = self._store.transition(approval_id, states.REJECTED, by=actor, reason=note)
            self._audit(approval, "REJECTED", by=actor, detail=note or "Rejected by operator.", request_id=request_id)
            return approval

        approval = self._store.transition(approval_id, states.APPROVED, by=actor, reason=note)
        self._audit(approval, "APPROVED", by=actor, detail=note or "Approved by operator.", request_id=request_id)
        return self._execute(approval, actor, request_id)

    # -- authorized execution ------------------------------------------------------------------
    def _execute(self, approval: Approval, actor: str, request_id: str | None) -> Approval:
        try:
            prepared = prepare_action(approval.action_type, approval.params, approval.statement)
        except ActionError as exc:
            return self._fail(approval, actor, request_id, f"Re-validation failed: {exc.message}", code=exc.code)

        try:
            result = self._registry.database.execute_admin_statement(prepared.statement)
        except AppError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if detail.get("code") in {"ACTIONS_DISABLED", "ADMIN_NOT_CONFIGURED"}:
                # Approved, but this deployment is not allowed to execute: recorded, not run.
                execution = {
                    "status": "NOT_EXECUTED",
                    "simulated": False,
                    "detail": exc.message,
                    "reason": detail["code"],
                }
                approval = self._store.record_execution(approval.id, execution, "approved but execution is disabled")
                self._audit(approval, "APPROVED_NOT_EXECUTED", by="system", detail=exc.message, request_id=request_id)
                return approval
            return self._fail(approval, actor, request_id, exc.message, code=exc.code)
        except Exception as exc:  # noqa: BLE001 — never leak driver internals
            logger.warning("approved action raised %s", type(exc).__name__)
            return self._fail(approval, actor, request_id, f"Unexpected {type(exc).__name__}", code="INTERNAL_ERROR")

        execution = {
            "status": result.status,
            "simulated": result.simulated,
            "detail": result.detail,
            "latency_ms": int(result.latency_ms),
            "executed_at": utc_now_iso(),
        }
        approval = self._store.transition(
            approval.id, states.EXECUTED, by="system", note=result.detail, execution=execution
        )
        self._audit(
            approval,
            "EXECUTED",
            by=actor,
            detail=result.detail,
            request_id=request_id,
            extra={"simulated": result.simulated},
        )
        return approval

    def _fail(self, approval: Approval, actor: str, request_id: str | None, message: str, *, code: str) -> Approval:
        safe = sanitize_metadata(message) or "failed"
        approval = self._store.transition(
            approval.id,
            states.FAILED,
            by="system",
            note=safe,
            execution={"status": "FAILED", "simulated": False, "detail": safe, "code": code},
        )
        self._audit(approval, "EXECUTION_FAILED", by=actor, detail=safe, request_id=request_id, extra={"code": code})
        return approval

    # -- audit ---------------------------------------------------------------------------------------
    def _sweep(self) -> None:
        for expired in self._store.expire_due():
            self._audit(expired, "EXPIRED", by="system", detail="Approval window elapsed without a decision.")

    def _audit(
        self,
        approval: Approval,
        status: str,
        *,
        by: str,
        detail: str,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        try:
            self._registry.audit.record(
                AuditRecord(
                    intent="ops",
                    question=f"Approval {approval.id}: {approval.title}",
                    status=status,
                    latency_ms=0,
                    request_id=request_id or approval.request_id,
                    session_id=approval.session_id,
                    operation="approval",
                    sql_text=approval.statement,
                    detail=detail,
                    metadata=json.dumps(
                        {
                            "approval_id": approval.id,
                            "action_type": approval.action_type,
                            "risk": approval.risk,
                            "actor": by,
                            "approval_status": approval.status,
                            **(extra or {}),
                        },
                        default=str,
                    ),
                    timestamp=utc_now_iso(),
                )
            )
        except Exception as exc:  # noqa: BLE001 — audit is best-effort
            logger.warning("approval audit write failed (%s)", type(exc).__name__)
