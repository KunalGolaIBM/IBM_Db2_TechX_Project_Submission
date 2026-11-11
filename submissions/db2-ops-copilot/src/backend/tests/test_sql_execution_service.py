"""SqlExecutionService — ordering, failure modes and best-effort bookkeeping."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.adapters.registry import AdapterRegistry
from app.core.config import Settings
from app.core.errors import (
    AdapterUnavailableError,
    SqlRejectedError,
    UpstreamTimeoutError,
)
from app.services.sql_execution_service import SqlExecutionService, _json_safe
from app.services.sql_guard_service import SqlGuardService

SAFE_SQL = "SELECT * FROM DEMO_SERVERS"


def _service(**overrides) -> tuple[SqlExecutionService, AdapterRegistry]:
    settings = Settings(_env_file=None, **overrides)
    registry = AdapterRegistry(settings)
    service = SqlExecutionService(
        settings, registry, SqlGuardService(registry.validator)
    )
    return service, registry


# -- happy path & bookkeeping ---------------------------------------------------
def test_success_records_history_and_audit():
    service, registry = _service()
    result = service.execute(SAFE_SQL, request_id="req-1", session_id="s-1")

    assert result.row_count == 4
    history = registry.database.list_executions(limit=5)
    assert len(history) == 1
    assert history[0].execution_status == "OK"
    assert history[0].validation_status == "PASSED"
    assert history[0].request_id == "req-1"
    assert history[0].timestamp

    newest = registry.audit.list_recent(limit=1)[0]
    assert newest.operation == "sql_execute"
    assert newest.status == "OK"
    assert newest.session_id == "s-1"
    assert newest.timestamp


def test_rejection_records_history_and_audit_then_raises():
    service, registry = _service()
    with pytest.raises(SqlRejectedError) as excinfo:
        service.execute("DROP TABLE DEMO_SERVERS", request_id="req-2")
    assert excinfo.value.detail["violations"]

    history = registry.database.list_executions(limit=5)
    assert history[0].validation_status == "REJECTED"
    assert history[0].execution_status == "REJECTED"
    assert history[0].explain_status == "SKIPPED"

    newest = registry.audit.list_recent(limit=1)[0]
    assert newest.status == "REJECTED_BY_GATE"
    assert newest.timestamp
    assert newest.question
    assert newest.sql_text and "DROP TABLE" in newest.sql_text


def test_rejected_sql_is_never_explained_or_executed():
    service, registry = _service()
    seen: list[str] = []
    registry.database.explain = lambda sql, timeout_ms=None: seen.append(sql) or True
    registry.database.execute_readonly = lambda *a, **k: seen.append("EXEC")
    with pytest.raises(SqlRejectedError):
        service.execute("DELETE FROM DEMO_SERVERS")
    assert seen == []


def test_audit_metadata_is_valid_json():
    import json

    service, registry = _service()
    service.execute(SAFE_SQL)
    metadata = registry.audit.list_recent(limit=1)[0].metadata
    assert json.loads(metadata)["row_count"] == 4


# -- EXPLAIN behaviour ---------------------------------------------------------
def test_explain_disabled_by_setting():
    service, _ = _service(sql_explain_dry_run=False)
    assert service.execute(SAFE_SQL).explain_status == "DISABLED"


def test_explain_failure_does_not_block_execution():
    service, registry = _service()
    registry.database.explain = lambda sql, timeout_ms=None: False
    result = service.execute(SAFE_SQL)
    assert result.explain_status == "FAILED"
    assert result.row_count == 4
    assert any("EXPLAIN" in w for w in result.warnings)


def test_explain_exception_does_not_block_execution():
    service, registry = _service()

    def boom(sql, timeout_ms=None):
        raise RuntimeError("plan table missing")

    registry.database.explain = boom
    result = service.execute(SAFE_SQL)
    assert result.explain_status == "FAILED"
    assert result.row_count == 4


# -- execution failures --------------------------------------------------------
def test_adapter_error_is_recorded_and_reraised():
    service, registry = _service()

    def fail(sql, params=None, timeout_ms=None):
        raise AdapterUnavailableError(
            "Query execution failed", detail={"sqlstate": "42704"}
        )

    registry.database.execute_readonly = fail
    with pytest.raises(AdapterUnavailableError):
        service.execute(SAFE_SQL, request_id="req-err")

    record = registry.database.list_executions(limit=1)[0]
    assert record.execution_status == "ERROR"
    assert record.sqlstate == "42704"
    assert registry.audit.list_recent(limit=1)[0].status == "ERROR"


def test_timeout_is_recorded_as_timeout():
    service, registry = _service()

    def slow(sql, params=None, timeout_ms=None):
        raise UpstreamTimeoutError("timed out", detail={"sqlstate": "57014"})

    registry.database.execute_readonly = slow
    with pytest.raises(UpstreamTimeoutError):
        service.execute(SAFE_SQL)
    assert registry.database.list_executions(limit=1)[0].execution_status == "TIMEOUT"
    assert registry.audit.list_recent(limit=1)[0].status == "TIMEOUT"


def test_timeout_value_comes_from_policy():
    service, registry = _service(sql_query_timeout_ms=1234)
    captured = {}
    original = registry.database.execute_readonly

    def spy(sql, params=None, timeout_ms=None):
        captured["timeout_ms"] = timeout_ms
        return original(sql, params, timeout_ms)

    registry.database.execute_readonly = spy
    service.execute(SAFE_SQL)
    assert captured["timeout_ms"] == 1234


# -- best-effort side effects ---------------------------------------------------
def test_history_write_failure_never_masks_result():
    service, registry = _service()

    def broken(record):
        raise RuntimeError("history table unavailable")

    registry.database.record_execution = broken
    assert service.execute(SAFE_SQL).row_count == 4


def test_audit_write_failure_never_masks_result():
    service, registry = _service()

    def broken(entry):
        raise RuntimeError("audit table unavailable")

    registry.audit.record = broken
    assert service.execute(SAFE_SQL).row_count == 4
    with pytest.raises(SqlRejectedError):  # rejection path stays a rejection
        service.execute("DROP TABLE DEMO_SERVERS")


# -- row cap / truncation ------------------------------------------------------
def test_truncation_adds_warning_and_flag():
    service, _ = _service(sql_max_rows=2)
    result = service.execute(SAFE_SQL)
    assert result.row_limit == 2
    assert result.row_count == 2
    assert result.truncated is True
    assert any("truncated" in w.lower() for w in result.warnings)


def test_row_limit_enforcement_can_be_disabled():
    service, _ = _service(sql_enforce_row_limit=False)
    result = service.execute(SAFE_SQL)
    assert result.row_limit_applied is False
    assert result.executed_sql.strip().upper() == SAFE_SQL


# -- value normalisation -------------------------------------------------------
def test_json_safe_normalises_driver_types():
    assert _json_safe(Decimal("1.50")) == 1.5
    assert _json_safe(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05"
    assert _json_safe(date(2026, 1, 2)) == "2026-01-02"
    assert _json_safe(b"\x01\xff") == "01ff"
    assert _json_safe(None) is None
    assert _json_safe(object()).startswith("<object")
