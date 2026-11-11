"""Real Db2 adapters exercised against a FAKE ``ibm_db_dbi`` module.

No Db2 server, driver install or network is involved: a minimal stand-in
module is injected into ``sys.modules``. This verifies our code (parameter
binding, caps, error mapping, redaction, transactions) — it does NOT validate
behaviour of a live Db2. Live validation is covered by the opt-in
``integration`` tests only.
"""

from __future__ import annotations

import json
import sys
import types
import uuid

import pytest

from app.adapters.audit.db2_audit import Db2AuditAdapter
from app.adapters.base import AuditRecord, ExecutionRecord
from app.adapters.db.db2_db import Db2DatabaseAdapter, classify_db_error
from app.core.config import Settings
from app.core.errors import (
    AdapterUnavailableError,
    DbObjectNotFoundError,
    UpstreamTimeoutError,
)

# Generated per run: a throwaway value, never a committed credential.
PASSWORD = "pw-" + uuid.uuid4().hex


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self._conn = conn
        self.description = None
        self.lastrowid = 7
        self._rows: list[tuple] = []

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        for needle, outcome in self._conn.script:
            if needle in sql:
                if isinstance(outcome, BaseException):
                    raise outcome
                self.description = [(c,) for c in outcome["columns"]]
                self._rows = list(outcome["rows"])
                return
        self.description = None
        self._rows = []

    def fetchmany(self, n):
        out, self._rows = self._rows[:n], self._rows[n:]
        return out

    def fetchall(self):
        out, self._rows = self._rows, []
        return out


class FakeConnection:
    def __init__(self, script):
        self.script = script
        self.executed: list[tuple] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.fixture()
def fake_dbi(monkeypatch):
    """Install a fake ibm_db_dbi; returns a controller object."""
    ctl = types.SimpleNamespace(script=[], connections=[], connect_error=None, args=None)

    def connect(dsn, user, password):
        ctl.args = (dsn, user, password)
        if ctl.connect_error:
            raise ctl.connect_error
        conn = FakeConnection(ctl.script)
        ctl.connections.append(conn)
        return conn

    module = types.ModuleType("ibm_db_dbi")
    module.connect = connect
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", module)
    monkeypatch.setitem(sys.modules, "ibm_db", types.ModuleType("ibm_db"))
    return ctl


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        adapter_mode="real",
        db2_ro_password=PASSWORD,
        sql_max_rows=3,
    )


# -- error classification -------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "sqlstate", "category"),
    [
        ("[IBM][CLI Driver][DB2/NT64] SQL0204N  \"X\" is an undefined name. SQLSTATE=42704", "42704", "schema"),
        ("SQL0551N not authorized SQLSTATE=42501", "42501", "authorization"),
        ("SQL30082N Security processing failed SQLSTATE=08001", "08001", "connectivity"),
        ("login failed SQLSTATE=28000", "28000", "authentication"),
        ("SQL0952N Processing was cancelled SQLSTATE=57014", "57014", "timeout"),
        ("SQL0911N deadlock SQLSTATE=40001 ", "40001", "unknown"),
        ("SQL0204N only message id here", "42704", "schema"),
        ("totally unrelated failure", "unknown", "unknown"),
    ],
)
def test_classify_db_error(text, sqlstate, category):
    info = classify_db_error(Exception(text))
    assert info.sqlstate == sqlstate
    assert info.category == category


# -- Db2DatabaseAdapter ----------------------------------------------------------
def test_execute_readonly_caps_rows_and_sets_timeout(fake_dbi, settings):
    fake_dbi.script = [
        ("SELECT", {"columns": ["A"], "rows": [(i,) for i in range(10)]}),
    ]
    adapter = Db2DatabaseAdapter(settings)
    result = adapter.execute_readonly("SELECT A FROM T", timeout_ms=5000)

    assert result.row_count == 3
    assert result.truncated is True
    assert result.columns == ["A"]
    conn = fake_dbi.connections[0]
    assert conn.executed[0][0] == "SET CURRENT QUERY TIMEOUT 5"
    assert conn.closed is True


def test_execute_readonly_not_truncated_when_within_cap(fake_dbi, settings):
    fake_dbi.script = [("SELECT", {"columns": ["A"], "rows": [(1,), (2,)]})]
    result = Db2DatabaseAdapter(settings).execute_readonly("SELECT A FROM T")
    assert (result.row_count, result.truncated) == (2, False)


def test_execute_readonly_passes_qmark_params(fake_dbi, settings):
    fake_dbi.script = [("SELECT", {"columns": ["A"], "rows": []})]
    Db2DatabaseAdapter(settings).execute_readonly("SELECT A FROM T WHERE B = ?", params=[5])
    assert fake_dbi.connections[0].executed[-1] == ("SELECT A FROM T WHERE B = ?", (5,))


def test_connection_uses_dsn_without_credentials(fake_dbi, settings):
    fake_dbi.script = [("SELECT", {"columns": ["A"], "rows": []})]
    Db2DatabaseAdapter(settings).execute_readonly("SELECT 1 FROM T")
    dsn, user, password = fake_dbi.args
    assert PASSWORD not in dsn and "pwd" not in dsn.lower()
    assert user == settings.db2_ro_user
    assert password == PASSWORD


def test_query_timeout_maps_to_upstream_timeout(fake_dbi, settings):
    fake_dbi.script = [("SELECT", Exception("SQL0952N cancelled SQLSTATE=57014"))]
    with pytest.raises(UpstreamTimeoutError) as excinfo:
        Db2DatabaseAdapter(settings).execute_readonly("SELECT 1 FROM T")
    assert excinfo.value.detail["sqlstate"] == "57014"


def test_query_error_is_classified_and_connection_closed(fake_dbi, settings):
    fake_dbi.script = [("SELECT", Exception("SQL0204N undefined SQLSTATE=42704"))]
    with pytest.raises(DbObjectNotFoundError) as excinfo:
        Db2DatabaseAdapter(settings).execute_readonly("SELECT 1 FROM NOPE")
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail["sqlstate"] == "42704"
    assert fake_dbi.connections[0].closed is True


def test_connect_failure_never_leaks_password(fake_dbi, settings):
    fake_dbi.connect_error = Exception(
        f"connect failed uid=db2ro pwd={PASSWORD} password {PASSWORD} SQLSTATE=08001"
    )
    with pytest.raises(AdapterUnavailableError) as excinfo:
        Db2DatabaseAdapter(settings).execute_readonly("SELECT 1 FROM T")
    assert PASSWORD not in str(excinfo.value)
    assert PASSWORD not in json.dumps(excinfo.value.detail, default=str)


def test_missing_driver_is_actionable(monkeypatch, settings):
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", None)  # forces ImportError
    with pytest.raises(AdapterUnavailableError) as excinfo:
        Db2DatabaseAdapter(settings).execute_readonly("SELECT 1 FROM T")
    assert "requirements-integration.txt" in str(excinfo.value)


def test_fetch_schema_reads_syscat_for_app_schema(fake_dbi, settings):
    fake_dbi.script = [
        ("SYSCAT.TABLES", {"columns": ["TABNAME"], "rows": [("T1",)]}),
        (
            "SYSCAT.COLUMNS",
            {
                "columns": ["TABNAME", "COLNAME", "TYPENAME", "NULLS"],
                "rows": [("T1", "ID", "INTEGER", "N"), ("T1", "NAME", "VARCHAR", "Y")],
            },
        ),
    ]
    snapshot = Db2DatabaseAdapter(settings).fetch_schema()
    assert snapshot.source == "SYSCAT"
    assert [c.name for c in snapshot.tables[0].columns] == ["ID", "NAME"]
    assert [c.nullable for c in snapshot.tables[0].columns] == [False, True]
    for _sql, params in fake_dbi.connections[0].executed:
        assert params == ("APP",)  # bound parameter, never interpolated


def test_record_execution_binds_params_commits_and_sanitizes(fake_dbi, settings):
    adapter = Db2DatabaseAdapter(settings)
    new_id = adapter.record_execution(
        ExecutionRecord(
            sql="SELECT 1 FROM T",
            validation_status="PASSED",
            execution_status="ERROR",
            truncated=True,
            latency_ms=12,
            request_id="r-1",
            detail="failed with password=hunter2",
        )
    )
    conn = fake_dbi.connections[0]
    sql, params = conn.executed[0]
    assert sql.startswith("INSERT INTO APP.QUERY_EXECUTIONS")
    assert params[0] == "r-1" and params[6] == "Y"
    assert "hunter2" not in params[-1]
    assert conn.commits == 1 and conn.closed is True
    assert new_id == 7


def test_record_execution_failure_is_classified(fake_dbi, settings):
    fake_dbi.script = [("INSERT", Exception("SQL0551N denied SQLSTATE=42501"))]
    with pytest.raises(AdapterUnavailableError) as excinfo:
        Db2DatabaseAdapter(settings).record_execution(
            ExecutionRecord(sql="SELECT 1", validation_status="PASSED")
        )
    assert excinfo.value.detail["table"] == "QUERY_EXECUTIONS"


def test_explain_failure_returns_false_never_raises(fake_dbi, settings):
    fake_dbi.script = [("EXPLAIN", Exception("SQL0551N SQLSTATE=42501"))]
    assert Db2DatabaseAdapter(settings).explain("SELECT 1 FROM T") is False


def test_transaction_rolls_back_on_error(fake_dbi, settings):
    adapter = Db2DatabaseAdapter(settings)
    with pytest.raises(RuntimeError):
        with adapter.transaction():
            raise RuntimeError("boom")
    conn = fake_dbi.connections[0]
    assert conn.rollbacks == 1 and conn.commits == 0 and conn.closed


def test_closed_adapter_refuses_work(fake_dbi, settings):
    adapter = Db2DatabaseAdapter(settings)
    adapter.close()
    with pytest.raises(AdapterUnavailableError):
        adapter.execute_readonly("SELECT 1 FROM T")
    assert adapter.explain("SELECT 1 FROM T") is False


# -- Db2AuditAdapter ---------------------------------------------------------------
def test_audit_record_writes_extended_columns(fake_dbi, settings):
    adapter = Db2AuditAdapter(settings)
    adapter.record(
        AuditRecord(
            intent="data",
            question="Execute SQL: SELECT 1",
            status="REJECTED_BY_GATE",
            latency_ms=3,
            request_id="r-9",
            session_id="s-9",
            operation="sql_execute",
            sql_text="DROP TABLE X",
            detail="rejected; token=abc123",
            metadata=json.dumps({"violations": ["statement_not_allowed"]}),
        )
    )
    conn = fake_dbi.connections[0]
    sql, params = conn.executed[0]
    assert sql.startswith("INSERT INTO APP.APP_AUDIT")
    assert params[1:5] == ("s-9", "r-9", "sql_execute", "data")
    metadata = json.loads(params[-1])  # must be ONE valid JSON document
    assert metadata["violations"] == ["statement_not_allowed"]
    assert metadata["operation"] == "sql_execute"
    assert "abc123" not in params[-1]
    assert conn.commits == 1 and conn.closed


def test_audit_metadata_is_none_when_nothing_to_store(fake_dbi, settings):
    Db2AuditAdapter(settings).record(
        AuditRecord(intent="docs", question="q", status="OK", latency_ms=1)
    )
    assert fake_dbi.connections[0].executed[0][1][-1] is None


def test_audit_write_failure_raises_sanitized_error(fake_dbi, settings):
    fake_dbi.script = [("INSERT", Exception(f"pwd={PASSWORD} SQLSTATE=08001"))]
    with pytest.raises(AdapterUnavailableError) as excinfo:
        Db2AuditAdapter(settings).record(
            AuditRecord(intent="docs", question="q", status="OK", latency_ms=1)
        )
    assert PASSWORD not in str(excinfo.value)


def test_audit_list_recent_maps_rows(fake_dbi, settings):
    from datetime import datetime

    fake_dbi.script = [
        (
            "FROM APP.APP_AUDIT",
            {
                "columns": ["AUDIT_ID"],
                "rows": [
                    (
                        5,
                        datetime(2026, 11, 10, 1, 2, 3),
                        "sql_execute",
                        "data",
                        "Execute SQL: SELECT 1",
                        "OK",
                        4,
                        "req-5",
                        "sess-5",
                        '{"row_count": 1}',
                    )
                ],
            },
        )
    ]
    [entry] = Db2AuditAdapter(settings).list_recent(limit=10)
    assert entry.id == 5
    assert entry.timestamp == "2026-11-10T01:02:03"
    assert entry.operation == "sql_execute"
    assert entry.request_id == "req-5"
    assert "FETCH FIRST 10 ROWS ONLY" in fake_dbi.connections[0].executed[0][0]
