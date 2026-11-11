"""Approval records and their state machine.

::

    PENDING --approve--> APPROVED --executed--> EXECUTED
       |                    |  \\--execution failed--> FAILED
       |                    \\--(execution disabled: stays APPROVED, flagged)
       +--reject--> REJECTED
       +--time passes--> EXPIRED

Only ``PENDING`` can be decided. Every other state is terminal except
``APPROVED`` which moves to ``EXECUTED``/``FAILED`` once. Illegal moves raise
``ApprovalStateError`` (HTTP 409); deciding an expired approval raises
``ApprovalExpiredError`` (HTTP 410). Expiry is evaluated lazily from an
injectable clock, so it is deterministic in tests.

The store is in-memory (bounded, thread-safe). Durable history lives in the
audit trail (APP_AUDIT in Db2) — every transition is audited by the service.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.core.errors import AppError, NotFoundError

PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
EXPIRED = "EXPIRED"
EXECUTED = "EXECUTED"
FAILED = "FAILED"

STATUSES = (PENDING, APPROVED, REJECTED, EXPIRED, EXECUTED, FAILED)

TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({APPROVED, REJECTED, EXPIRED}),
    APPROVED: frozenset({EXECUTED, FAILED}),
    REJECTED: frozenset(),
    EXPIRED: frozenset(),
    EXECUTED: frozenset(),
    FAILED: frozenset(),
}


class ApprovalStateError(AppError):
    code = "APPROVAL_STATE_CONFLICT"
    status_code = 409


class ApprovalExpiredError(AppError):
    code = "APPROVAL_EXPIRED"
    status_code = 410


class ApprovalDecisionError(AppError):
    """The supplied decision is not one of the supported choices.

    Raised BEFORE any state change, so an unknown/typo'd decision value can
    never be mistaken for an approval (fail-closed, HTTP 422).
    """

    code = "APPROVAL_INVALID_DECISION"
    status_code = 422


#: The exact decision values ``ApprovalService.decide`` accepts.
DECISIONS: frozenset[str] = frozenset({"approve", "reject"})


def approval_not_found(approval_id: str) -> NotFoundError:
    return NotFoundError(f"Unknown approval '{approval_id}'.", code="APPROVAL_NOT_FOUND")


Clock = Callable[[], datetime]


def utc_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Approval:
    id: str
    status: str
    action_type: str
    params: dict[str, str]
    statement: str
    title: str
    rationale: str
    risk: str
    created_at: datetime
    expires_at: datetime
    request_id: str | None = None
    session_id: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    execution: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


class ApprovalStore:
    """Thread-safe, bounded, in-memory approval registry."""

    def __init__(self, *, clock: Clock = utc_clock, capacity: int = 500) -> None:
        self._clock = clock
        self._capacity = capacity
        self._lock = threading.RLock()
        self._items: dict[str, Approval] = {}

    @property
    def now(self) -> datetime:
        return self._clock()

    # -- creation ------------------------------------------------------------
    def create(
        self,
        *,
        action_type: str,
        params: dict[str, str],
        statement: str,
        title: str,
        rationale: str,
        risk: str,
        ttl_seconds: int,
        request_id: str | None,
        session_id: str | None,
    ) -> Approval:
        now = self._clock()
        approval = Approval(
            id="apr_" + uuid.uuid4().hex[:12],
            status=PENDING,
            action_type=action_type,
            params=dict(params),
            statement=statement,
            title=title,
            rationale=rationale,
            risk=risk,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            request_id=request_id,
            session_id=session_id,
            history=[{"at": now.isoformat(), "from": None, "to": PENDING, "by": "agent", "note": "proposed"}],
        )
        with self._lock:
            self._items[approval.id] = approval
            while len(self._items) > self._capacity:
                oldest = next(iter(self._items))
                del self._items[oldest]
        return approval

    # -- reads (never mutate except lazy expiry) -----------------------------------
    def expire_due(self) -> list[Approval]:
        """Move overdue PENDING approvals to EXPIRED; returns the newly expired."""
        now = self._clock()
        expired: list[Approval] = []
        with self._lock:
            for item in self._items.values():
                if item.status == PENDING and now >= item.expires_at:
                    self._move(item, EXPIRED, by="system", note="approval window elapsed", now=now)
                    expired.append(item)
        return expired

    def get(self, approval_id: str) -> Approval:
        with self._lock:
            item = self._items.get(approval_id)
            if item is None:
                raise approval_not_found(approval_id)
            return item

    def list(self, status: str | None = None, limit: int = 50) -> list[Approval]:
        with self._lock:
            items = list(self._items.values())
        if status:
            items = [i for i in items if i.status == status]
        items.sort(key=lambda a: a.created_at, reverse=True)
        return items[: max(limit, 0)]

    # -- transitions ---------------------------------------------------------------------
    def transition(
        self,
        approval_id: str,
        to: str,
        *,
        by: str,
        note: str | None = None,
        reason: str | None = None,
        execution: dict[str, Any] | None = None,
    ) -> Approval:
        """Atomically move an approval; raises on illegal/expired transitions."""
        with self._lock:
            item = self.get(approval_id)
            now = self._clock()
            if item.status == PENDING and now >= item.expires_at:
                self._move(item, EXPIRED, by="system", note="approval window elapsed", now=now)
            if item.status == EXPIRED and to in {APPROVED, REJECTED}:
                raise ApprovalExpiredError(
                    f"Approval {item.id} expired at {item.expires_at.isoformat()}.",
                    detail={"expires_at": item.expires_at.isoformat()},
                )
            if to not in TRANSITIONS[item.status]:
                raise ApprovalStateError(
                    f"Approval {item.id} is {item.status}; cannot move to {to}.",
                    detail={"status": item.status, "requested": to},
                )
            if to in {APPROVED, REJECTED}:
                item.decided_by = by
                item.decided_at = now
                item.decision_reason = reason
            if execution is not None:
                item.execution = execution
            self._move(item, to, by=by, note=note or reason, now=now)
            return item

    def record_execution(self, approval_id: str, execution: dict[str, Any], note: str) -> Approval:
        """Attach an execution outcome without changing status (APPROVED, not run)."""
        with self._lock:
            item = self.get(approval_id)
            if item.status != APPROVED:
                raise ApprovalStateError(
                    f"Approval {item.id} is {item.status}; execution can only be recorded on APPROVED.",
                    detail={"status": item.status},
                )
            item.execution = execution
            item.history.append(
                {"at": self._clock().isoformat(), "from": APPROVED, "to": APPROVED, "by": "system", "note": note}
            )
            return item

    @staticmethod
    def _move(item: Approval, to: str, *, by: str, note: str | None, now: datetime) -> None:
        item.history.append(
            {"at": now.isoformat(), "from": item.status, "to": to, "by": by, "note": note}
        )
        item.status = to
