"""M3 approval workflow: state machine, tamper checks, audit, execution gating.

Offline unit tests for ``app.agent.approvals``, ``app.agent.actions`` and
``app.services.approval_service``. No database, no network, no native driver:
execution goes through fakes, and the real adapter is only exercised up to its
pre-connection guards (which fire before ``import ibm_db_dbi``).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.agent import actions as actions_mod
from app.agent import approvals as states
from app.agent.actions import ActionError, PreparedAction, prepare_action
from app.agent.approvals import (
    ApprovalDecisionError,
    ApprovalExpiredError,
    ApprovalStateError,
    ApprovalStore,
)
from app.adapters.base import AdminResult, AuditRecord
from app.adapters.db.db2_db import Db2DatabaseAdapter
from app.core.errors import AdapterUnavailableError, AppError
from app.services.approval_service import ApprovalService, clean_actor
from db2_fakes import install_fake_dbi, real_settings

# ===================================================================================
# Fakes
# ===================================================================================
class FakeClock:
    """Deterministic injectable clock (ApprovalStore takes it as ``clock``)."""

    def __init__(self) -> None:
        self._now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)


class RecordingAudit:
    """Captures every AuditRecord the service writes."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def record(self, entry: AuditRecord) -> int:
        self.records.append(entry)
        return len(self.records)

    def statuses(self) -> list[str]:
        return [r.status for r in self.records]

    def by_status(self, status: str) -> list[AuditRecord]:
        return [r for r in self.records if r.status == status]


class ScriptedDatabase:
    """Fake database adapter recording admin-execution calls."""

    def __init__(
        self,
        result: AdminResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._result = result or AdminResult(
            status="EXECUTED",
            simulated=False,
            detail="Statement executed by the maintenance account.",
            latency_ms=1.0,
        )
        self._error = error

    def execute_admin_statement(self, statement: str) -> AdminResult:
        self.calls.append(statement)
        if self._error is not None:
            raise self._error
        return self._result


class FakeRegistry:
    """Duck-typed stand-in for AdapterRegistry (service only uses 2 members)."""

    def __init__(self, database, audit) -> None:
        self.database = database
        self.audit = audit


def _service(*, settings=None, database=None, audit=None, clock=None):
    settings = settings or real_settings()
    audit = audit if audit is not None else RecordingAudit()
    database = database if database is not None else ScriptedDatabase()
    store = ApprovalStore(clock=clock or FakeClock())
    service = ApprovalService(settings, FakeRegistry(database, audit), store)
    return service, database, audit, store


def _prepared(action_type: str = "runstats", **params) -> PreparedAction:
    base: dict[str, str] = {"schema": "APP", "table": "DEMO_SERVERS"}
    if action_type == "create_index":
        base["column"] = "HOSTNAME"
    base.update(params)
    return prepare_action(action_type, base)


def _propose(service: ApprovalService, prepared: PreparedAction | None = None):
    return service.propose(
        prepared or _prepared(),
        rationale="optimizer statistics are stale",
        request_id="req-1",
        session_id=None,
    )


def _decide(service: ApprovalService, approval, decision: str, **kwargs):
    kwargs.setdefault("decided_by", "operator-1")
    kwargs.setdefault("reason", "reviewed")
    return service.decide(approval.id, decision, **kwargs)


# ===================================================================================
# 1–2. Proposal lifecycle: PENDING, never executed on propose
# ===================================================================================
def test_proposal_starts_pending():
    service, database, audit, _ = _service()
    approval = _propose(service)

    assert approval.status == states.PENDING
    assert approval.id.startswith("apr_")
    assert approval.execution is None
    assert approval.risk == "low"  # from ActionSpec for runstats
    assert audit.statuses() == ["APPROVAL_REQUESTED"]


def test_proposal_does_not_execute_the_action():
    service, database, audit, _ = _service()
    approval = _propose(service)

    assert database.calls == []  # propose never executes
    assert approval.execution is None
    assert approval.status == states.PENDING


# ===================================================================================
# 3–4. Rejection / approval transitions
# ===================================================================================
def test_rejection_reaches_terminal_state_and_blocks_approval():
    service, database, audit, _ = _service()
    approval = _propose(service)

    rejected = _decide(service, approval, "reject")

    assert rejected.status == states.REJECTED
    assert rejected.decided_by == "operator-1"
    assert rejected.decided_at is not None
    assert database.calls == []  # a rejection never executes
    assert "REJECTED" in audit.statuses()
    # terminal: any further decision is a conflict
    with pytest.raises(ApprovalStateError):
        _decide(service, rejected, "approve")


def test_approval_executes_and_reaches_executed_state():
    service, database, audit, _ = _service()
    approval = _propose(service)

    executed = _decide(service, approval, "approve")

    assert executed.status == states.EXECUTED
    assert executed.decided_by == "operator-1"
    assert database.calls == [approval.statement]
    assert executed.execution is not None
    assert executed.execution["status"] == "EXECUTED"
    assert executed.execution["simulated"] is False
    statuses = audit.statuses()
    assert "APPROVED" in statuses
    assert "EXECUTED" in statuses
    assert "EXECUTION_FAILED" not in statuses


# ===================================================================================
# 5. Invalid transitions rejected
# ===================================================================================
def test_invalid_state_transitions_raise_conflict():
    clock = FakeClock()
    store = ApprovalStore(clock=clock)
    approval = store.create(
        action_type="runstats",
        params={"schema": "APP", "table": "T"},
        statement="CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE APP.T "
        "WITH DISTRIBUTION AND DETAILED INDEXES ALL')",
        title="stats",
        rationale="r",
        risk="low",
        ttl_seconds=900,
        request_id=None,
        session_id=None,
    )

    # PENDING may only move to APPROVED / REJECTED / EXPIRED
    with pytest.raises(ApprovalStateError):
        store.transition(approval.id, states.EXECUTED, by="x")
    with pytest.raises(ApprovalStateError):
        store.transition(approval.id, states.FAILED, by="x")

    store.transition(approval.id, states.REJECTED, by="x")
    # REJECTED is terminal
    with pytest.raises(ApprovalStateError):
        store.transition(approval.id, states.APPROVED, by="x")
    with pytest.raises(ApprovalStateError):
        store.transition(approval.id, states.EXECUTED, by="x")
    assert approval.status == states.REJECTED

    # EXECUTED is terminal
    store2 = ApprovalStore(clock=clock)
    done = store2.create(
        action_type="runstats",
        params={"schema": "APP", "table": "T"},
        statement="S",
        title="t",
        rationale="r",
        risk="low",
        ttl_seconds=900,
        request_id=None,
        session_id=None,
    )
    store2.transition(done.id, states.APPROVED, by="x")
    store2.transition(done.id, states.EXECUTED, by="x")
    with pytest.raises(ApprovalStateError):
        store2.transition(done.id, states.FAILED, by="x")


# ===================================================================================
# 6–7. Expiry
# ===================================================================================
def test_decide_on_expired_approval_raises_expired_error():
    clock = FakeClock()
    service, database, audit, _ = _service(clock=clock)
    approval = _propose(service)

    clock.advance(service._settings.approval_ttl_seconds + 1)

    with pytest.raises(ApprovalExpiredError):
        _decide(service, approval, "approve")
    assert approval.status == states.EXPIRED
    assert database.calls == []  # an expired approval can never execute
    assert "EXPIRED" in audit.statuses()


def test_expire_due_expires_only_overdue_pending():
    clock = FakeClock()
    store = ApprovalStore(clock=clock)

    def create(ttl: int = 900):
        return store.create(
            action_type="runstats",
            params={"schema": "APP", "table": "T"},
            statement="S",
            title="t",
            rationale="r",
            risk="low",
            ttl_seconds=ttl,
            request_id=None,
            session_id=None,
        )

    first = create()
    clock.advance(901)
    second = create()  # created later -> still inside its own window

    expired = store.expire_due()
    assert expired == [first]
    assert first.status == states.EXPIRED
    assert second.status == states.PENDING

    # An APPROVED (decided) approval never expires
    approved = create()
    store.transition(approved.id, states.APPROVED, by="x")
    clock.advance(100_000)
    later_expired = store.expire_due()
    assert approved not in later_expired
    assert approved.status == states.APPROVED
    assert second in later_expired  # only the still-PENDING one aged out
    assert second.status == states.EXPIRED


# ===================================================================================
# 8–9. Tamper detection at execution time
# ===================================================================================
def test_tampered_statement_fails_execution_before_database():
    service, database, audit, _ = _service()
    approval = _propose(service)

    approval.statement = "DELETE FROM APP.DEMO_SERVERS"  # tamper after approval
    result = _decide(service, approval, "approve")

    assert result.status == states.FAILED
    assert database.calls == []  # nothing ran
    assert result.execution is not None
    assert result.execution["status"] == "FAILED"
    assert result.execution["code"] == "INVALID_ACTION"
    assert "Re-validation failed" in result.execution["detail"]
    assert "EXECUTION_FAILED" in audit.statuses()
    assert "EXECUTED" not in audit.statuses()


def test_tampered_parameters_fail_execution_before_database():
    service, database, audit, _ = _service()
    approval = _propose(service)

    approval.params = {"schema": "APP", "table": "OTHER_TABLE"}  # tamper params
    result = _decide(service, approval, "approve")

    assert result.status == states.FAILED
    assert database.calls == []
    assert result.execution is not None
    assert result.execution["code"] == "INVALID_ACTION"


# ===================================================================================
# 10–11. Action allow-list, reserved schemas, forbidden verbs
# ===================================================================================
def test_unknown_action_type_is_rejected():
    with pytest.raises(ActionError) as excinfo:
        prepare_action("drop_table", {"schema": "APP", "table": "T"})
    assert excinfo.value.code == "INVALID_ACTION"
    assert excinfo.value.detail == {"supported": ["create_index", "runstats"]}


def test_reserved_schema_is_rejected():
    for schema in ("SYSIBM", "SYSCAT", "SYSTOOLS", "NULLID"):
        with pytest.raises(ActionError):
            prepare_action("runstats", {"schema": schema, "table": "T"})
        with pytest.raises(ActionError):
            prepare_action(
                "create_index", {"schema": schema, "table": "T", "column": "C"}
            )


def test_rendered_statements_contain_no_forbidden_verbs_and_match_allow_list():
    statements = [
        _prepared("runstats").statement,
        _prepared("create_index").statement,
    ]
    for statement in statements:
        assert ";" not in statement
        assert actions_mod._FORBIDDEN_WORDS.search(statement.upper()) is None
        assert any(rx.fullmatch(statement) for rx in actions_mod._ALLOWED)


def test_forbidden_construct_from_renderer_is_rejected(monkeypatch):
    # Defense in depth: even if rendering ever produced a forbidden statement,
    # prepare_action must refuse it before anything can execute.
    monkeypatch.setattr(
        actions_mod, "render_statement", lambda *a, **k: "DROP TABLE APP.T"
    )
    with pytest.raises(ActionError) as excinfo:
        prepare_action("runstats", {"schema": "APP", "table": "T"})
    assert "forbidden construct" in str(excinfo.value)


def test_non_allowlisted_render_is_rejected(monkeypatch):
    monkeypatch.setattr(
        actions_mod, "render_statement", lambda *a, **k: "SELECT 1 FROM T"
    )
    with pytest.raises(ActionError) as excinfo:
        prepare_action("runstats", {"schema": "APP", "table": "T"})
    assert "allow-list" in str(excinfo.value)


# ===================================================================================
# 11. Missing / unexpected parameters
# ===================================================================================
def test_missing_and_unexpected_parameters_are_rejected():
    with pytest.raises(ActionError) as missing:
        prepare_action("runstats", {"schema": "APP"})
    assert missing.value.detail == {"unexpected": [], "missing": ["table"]}

    with pytest.raises(ActionError) as unexpected:
        prepare_action(
            "runstats", {"schema": "APP", "table": "T", "extra": "1"}
        )
    assert unexpected.value.detail == {"unexpected": ["extra"], "missing": []}

    with pytest.raises(ActionError) as no_column:
        prepare_action("create_index", {"schema": "APP", "table": "T"})
    assert no_column.value.detail == {"unexpected": [], "missing": ["column"]}


# ===================================================================================
# 12. Statement rendering uses validated/normalized parameters
# ===================================================================================
def test_statement_rendering_uses_normalized_identifiers():
    runstats = prepare_action(
        "runstats", {"schema": "app", "table": "demo_servers"}
    )
    assert runstats.statement == (
        "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE APP.DEMO_SERVERS "
        "WITH DISTRIBUTION AND DETAILED INDEXES ALL')"
    )

    index = prepare_action(
        "create_index",
        {"schema": "app", "table": "demo_servers", "column": "hostname"},
    )
    assert index.statement == (
        "CREATE INDEX APP.IDX_DEMO_SERVERS_HOSTNAME "
        "ON APP.DEMO_SERVERS (HOSTNAME)"
    )

    # identifiers are validated: injection-shaped values never render
    with pytest.raises(ActionError):
        prepare_action(
            "runstats", {"schema": "APP", "table": "T; DROP TABLE X"}
        )
    with pytest.raises(ActionError):
        prepare_action(
            "create_index",
            {"schema": "APP", "table": "T", "column": "C) ON APP.T; --"},
        )


# ===================================================================================
# 13. Every transition is audited
# ===================================================================================
def test_every_approval_transition_is_audited():
    clock = FakeClock()
    service, database, audit, _ = _service(clock=clock)

    rejected = _propose(service)
    _decide(service, rejected, "reject")

    executed = _propose(service)
    _decide(service, executed, "approve")

    failed = _propose(service)
    failed.statement = "UPDATE APP.DEMO_SERVERS SET OWNER_TEAM = 'x'"
    _decide(service, failed, "approve")

    expiring = _propose(service)
    clock.advance(service._settings.approval_ttl_seconds + 1)
    service.list()  # sweeps expired approvals

    statuses = audit.statuses()
    for expected in (
        "APPROVAL_REQUESTED",  # every propose
        "REJECTED",
        "APPROVED",
        "EXECUTED",
        "EXECUTION_FAILED",  # tampered statement
        "EXPIRED",
    ):
        assert expected in statuses, f"missing audit status {expected}: {statuses}"

    # every record carries the approval id in its metadata
    for record in audit.records:
        payload = json.loads(record.metadata or "{}")
        assert payload["approval_id"].startswith("apr_")
        assert record.operation == "approval"
    assert expiring.status == states.EXPIRED


def test_audit_failure_never_masks_the_outcome():
    class BrokenAudit:
        def record(self, entry: AuditRecord) -> int:
            raise RuntimeError("audit store offline")

    service, database, audit, _ = _service(audit=BrokenAudit())
    approval = _propose(service)
    result = _decide(service, approval, "approve")
    # audit is best-effort: the approval outcome still completes
    assert result.status == states.EXECUTED
    assert database.calls == [approval.statement]


# ===================================================================================
# 14. Actor sanitization
# ===================================================================================
def test_actor_strings_are_sanitized():
    assert clean_actor(None) == "operator"
    assert clean_actor("   ") == "operator"

    long_dirty = "lead\x00\x07operator\n" + "x" * 200
    cleaned = clean_actor(long_dirty)
    assert "\x00" not in cleaned and "\x07" not in cleaned and "\n" not in cleaned
    assert len(cleaned) <= 64

    service, database, audit, _ = _service()
    approval = _propose(service)
    decided = _decide(service, approval, "reject", decided_by=long_dirty)
    assert decided.decided_by == cleaned
    assert "\x00" not in decided.decided_by
    # the audit trail stores the same sanitized actor
    record = audit.by_status("REJECTED")[0]
    assert "\x00" not in (record.metadata or "")
    assert json.loads(record.metadata or "{}")["actor"] == cleaned


# ===================================================================================
# 15. Failed execution records a sanitized failure
# ===================================================================================
def test_failed_execution_records_password_free_failure():
    secret = "pw-" + "s3cr3t-value"
    database = ScriptedDatabase(
        error=AdapterUnavailableError(
            f"Maintenance connection failed password={secret}",
            detail={"sqlstate": "08001"},
        )
    )
    service, database, audit, _ = _service(database=database)
    approval = _propose(service)

    result = _decide(service, approval, "approve")

    assert result.status == states.FAILED
    assert result.execution is not None
    assert result.execution["status"] == "FAILED"
    assert secret not in result.execution["detail"]
    assert "password=***" in result.execution["detail"]
    # the raw secret never reaches the audit trail either
    for record in audit.records:
        blob = f"{record.detail}{record.metadata}{record.question}"
        assert secret not in blob
    assert database.calls == [approval.statement]  # attempt happened, then FAILED


def test_unexpected_exception_failure_hides_driver_internals():
    database = ScriptedDatabase(error=RuntimeError("raw driver gibberish"))
    service, database, audit, _ = _service(database=database)
    approval = _propose(service)

    result = _decide(service, approval, "approve")

    assert result.status == states.FAILED
    assert result.execution is not None
    assert result.execution["code"] == "INTERNAL_ERROR"
    assert "raw driver gibberish" not in result.execution["detail"]
    assert "RuntimeError" in result.execution["detail"]
    assert "EXECUTION_FAILED" in audit.statuses()


# ===================================================================================
# 16. ACTIONS_DISABLED / ADMIN_NOT_CONFIGURED never execute
# ===================================================================================
def test_actions_disabled_is_recorded_not_executed(monkeypatch):
    dbi = install_fake_dbi(monkeypatch)
    settings = real_settings(agent_actions_enabled=False)
    adapter = Db2DatabaseAdapter(settings)
    service, database, audit, _ = _service(settings=settings, database=adapter)
    approval = _propose(service)

    result = _decide(service, approval, "approve")

    assert result.status == states.APPROVED  # stays APPROVED, not executed
    assert result.execution is not None
    assert result.execution["status"] == "NOT_EXECUTED"
    assert result.execution["reason"] == "ACTIONS_DISABLED"
    assert dbi.connections == []  # the driver was never even imported/connected
    statuses = audit.statuses()
    assert "APPROVED_NOT_EXECUTED" in statuses
    assert "EXECUTED" not in statuses


def test_admin_not_configured_is_recorded_not_executed(monkeypatch):
    dbi = install_fake_dbi(monkeypatch)
    settings = real_settings(
        agent_actions_enabled=True, db2_admin_user="", db2_admin_password=""
    )
    adapter = Db2DatabaseAdapter(settings)
    service, database, audit, _ = _service(settings=settings, database=adapter)
    approval = _propose(service)

    result = _decide(service, approval, "approve")

    assert result.status == states.APPROVED
    assert result.execution is not None
    assert result.execution["status"] == "NOT_EXECUTED"
    assert result.execution["reason"] == "ADMIN_NOT_CONFIGURED"
    assert dbi.connections == []
    assert "APPROVED_NOT_EXECUTED" in audit.statuses()
    assert "EXECUTED" not in audit.statuses()


# ===================================================================================
# 17. The admin execution path runs only after approval
# ===================================================================================
def test_admin_execution_happens_only_after_approval():
    service, database, audit, _ = _service()
    pending = _propose(service)

    # reads never execute
    service.get(pending.id)
    service.list()
    assert database.calls == []
    assert pending.status == states.PENDING

    # rejection never executes
    _decide(service, pending, "reject")
    assert database.calls == []

    # approval executes exactly once, with the statement the human saw
    approved = _propose(service)
    _decide(service, approved, "approve")
    assert database.calls == [approved.statement]
    assert len(database.calls) == 1


# ===================================================================================
# P0.3 — exact decision values only (fail-closed BEFORE any state change)
# ===================================================================================
def test_valid_approve_decision_is_accepted_and_executes():
    service, database, audit, _ = _service()
    approval = _propose(service)

    result = _decide(service, approval, "approve")

    assert result.status == states.EXECUTED
    assert database.calls == [approval.statement]
    statuses = audit.statuses()
    assert "APPROVED" in statuses
    assert "EXECUTED" in statuses


def test_valid_reject_decision_is_accepted():
    service, database, audit, _ = _service()
    approval = _propose(service)

    result = _decide(service, approval, "reject")

    assert result.status == states.REJECTED
    assert database.calls == []  # a rejection never executes
    assert "REJECTED" in audit.statuses()


@pytest.mark.parametrize(
    "decision",
    [
        pytest.param("DELETE", id="unknown-verb"),
        pytest.param("", id="empty"),
        pytest.param("APPROVE", id="all-caps"),
        pytest.param("Reject", id="mixed-case"),
        pytest.param(" approve", id="leading-space"),
        pytest.param("approve ", id="trailing-space"),
        pytest.param("reject\n", id="trailing-newline"),
        pytest.param("aprove", id="typo"),
    ],
)
def test_invalid_decision_is_rejected_before_any_state_change(decision):
    service, database, audit, _ = _service()
    approval = _propose(service)
    snapshot = {
        "status": approval.status,
        "decided_by": approval.decided_by,
        "decided_at": approval.decided_at,
        "execution": approval.execution,
        "history": list(approval.history),
    }

    with pytest.raises(ApprovalDecisionError) as excinfo:
        _decide(service, approval, decision)

    # existing exception conventions: an AppError subclass with a stable code
    assert excinfo.value.code == "APPROVAL_INVALID_DECISION"
    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == {"supported": ["approve", "reject"]}

    # approval state is completely untouched
    assert approval.status == snapshot["status"] == states.PENDING
    assert approval.decided_by is snapshot["decided_by"] is None
    assert approval.decided_at is snapshot["decided_at"] is None
    assert approval.execution is snapshot["execution"] is None
    assert approval.history == snapshot["history"]

    # no statement ever executed; no extra audit rows were written
    assert database.calls == []
    assert audit.statuses() == ["APPROVAL_REQUESTED"]


def test_invalid_decision_does_not_bypass_audit_safeguards():
    service, database, audit, _ = _service()
    approval = _propose(service)

    with pytest.raises(ApprovalDecisionError):
        _decide(service, approval, "DELETE")

    # nothing transitioned, so no transition audit rows were forged
    assert approval.status == states.PENDING
    assert database.calls == []
    assert audit.statuses() == ["APPROVAL_REQUESTED"]

    # and the audit path still works normally for a subsequent valid decision
    result = _decide(service, approval, "reject", decided_by="operator-2")
    assert result.status == states.REJECTED
    statuses = audit.statuses()
    assert "REJECTED" in statuses
    assert "APPROVED" not in statuses
    assert "EXECUTED" not in statuses
    assert database.calls == []
