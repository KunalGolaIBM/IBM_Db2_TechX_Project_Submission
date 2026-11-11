"""Real Db2 adapter: DBA tools, EXPLAIN and SQLSTATE -> API error mapping.

Everything runs against the scriptable fake ``ibm_db_dbi`` (see db2_fakes.py).
This verifies OUR statements, binding, fallbacks and error mapping — it does
not and cannot validate behaviour on a live Db2.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.adapters.db.db2_db import Db2DatabaseAdapter, map_db_error
from app.core.config import get_settings
from app.core.errors import (
    AdapterUnavailableError,
    DbError,
    DbObjectNotFoundError,
    DbPermissionError,
    DbSqlError,
    UpstreamTimeoutError,
)
from app.dba.specs import TOOLS_BY_ID
from app.main import create_app

from db2_fakes import dbi, real_settings  # noqa: F401  (dbi is a fixture)


# ===================================================================================
# map_db_error — SQLSTATE taxonomy
# ===================================================================================
@pytest.mark.parametrize(
    ("text", "error", "status"),
    [
        ("SQL0952N cancelled SQLSTATE=57014", UpstreamTimeoutError, 504),
        ("SQL0551N not authorized SQLSTATE=42501", DbPermissionError, 403),
        ("SQL0204N undefined name SQLSTATE=42704", DbObjectNotFoundError, 404),
        ("SQL0104N syntax SQLSTATE=42601", DbSqlError, 422),
        ("SQL0206N bad column SQLSTATE=42703", DbSqlError, 422),
        ("SQL30081N comm error SQLSTATE=08001", AdapterUnavailableError, 503),
        ("login failed SQLSTATE=28000", AdapterUnavailableError, 503),
        ("SQL0911N rolled back SQLSTATE=40001", DbError, 502),
        ("something nobody has seen before", DbError, 502),
    ],
)
def test_sqlstate_maps_to_http_error(text, error, status):
    mapped = map_db_error(Exception(text), real_settings(), action="Query")
    assert type(mapped) is error
    assert mapped.status_code == status
    assert mapped.detail["sqlstate"]  # always present for diagnostics
    assert mapped.detail["hint"]


def test_mapped_errors_never_contain_the_password():
    settings = real_settings()
    secret = settings.db2_ro_password.get_secret_value()
    for state in ("42501", "42704", "08001", "42601"):
        mapped = map_db_error(
            Exception(f"failed pwd={secret} {secret} SQLSTATE={state}"),
            settings,
            action="Query",
        )
        assert secret not in mapped.message
        assert secret not in json.dumps(mapped.detail, default=str)


# ===================================================================================
# run_dba_tool
# ===================================================================================
def test_run_dba_tool_binds_params_and_caps_rows(dbi):
    spec = TOOLS_BY_ID["catalog.columns"]
    dbi.script = [
        ("SYSCAT.COLUMNS", {"columns": ["COLNAME", "COLNO"], "rows": [(f"C{i}", i) for i in range(10)]}),
    ]
    adapter = Db2DatabaseAdapter(real_settings())
    result = adapter.run_dba_tool(spec.id, spec.render(3), ("APP", "T1"), 3)

    assert result.source == "db2" and result.tool_id == spec.id
    assert result.columns == ["COLNAME", "COLNO"]
    assert len(result.rows) == 3 and result.truncated is True
    conn = dbi.connections[0]
    assert conn.executed[0][0].startswith("SET CURRENT QUERY TIMEOUT")
    sql, params = conn.executed[1]
    assert params == ("APP", "T1")
    assert "T1" not in sql  # values are bound, never interpolated
    assert conn.closed


def test_run_dba_tool_without_params_passes_none(dbi):
    spec = TOOLS_BY_ID["monitor.slow_statements"]
    dbi.script = [("MON_GET_PKG_CACHE_STMT", {"columns": ["N"], "rows": [(1,)]})]
    result = Db2DatabaseAdapter(real_settings()).run_dba_tool(spec.id, spec.render(5), (), 5)
    assert result.rows == [[1]] and result.truncated is False
    assert dbi.connections[0].executed[1][1] is None


@pytest.mark.parametrize(
    ("driver_error", "expected"),
    [
        ("SQL0551N not authorized SQLSTATE=42501", DbPermissionError),
        ("SQL0204N MON_GET_X undefined SQLSTATE=42704", DbObjectNotFoundError),
        ("SQL0952N SQLSTATE=57014", UpstreamTimeoutError),
    ],
)
def test_run_dba_tool_maps_errors_and_closes_connection(dbi, driver_error, expected):
    spec = TOOLS_BY_ID["monitor.table_activity"]
    dbi.script = [("MON_GET_TABLE", Exception(driver_error))]
    with pytest.raises(expected):
        Db2DatabaseAdapter(real_settings()).run_dba_tool(spec.id, spec.render(5), ("APP",), 5)
    assert dbi.connections[0].closed


def test_run_dba_tool_connection_failure_is_503(dbi):
    dbi.connect_error = Exception("refused SQLSTATE=08001")
    spec = TOOLS_BY_ID["catalog.tables"]
    with pytest.raises(AdapterUnavailableError) as excinfo:
        Db2DatabaseAdapter(real_settings()).run_dba_tool(spec.id, spec.render(5), ("APP",), 5)
    assert excinfo.value.status_code == 503


def test_closed_adapter_refuses_dba_tools(dbi):
    adapter = Db2DatabaseAdapter(real_settings())
    adapter.close()
    with pytest.raises(AdapterUnavailableError):
        adapter.run_dba_tool("catalog.tables", "SELECT 1", (), 1)


# ===================================================================================
# explain_plan
# ===================================================================================
def _plan_script(**overrides):
    script = {
        "stmt": ("FROM SYSTOOLS.EXPLAIN_STATEMENT S WHERE", {"columns": ["TOTAL_COST"], "rows": [(25.5,)]}),
        "ops": (
            "FROM SYSTOOLS.EXPLAIN_OPERATOR O",
            {
                "columns": ["A", "B", "C", "D", "E"],
                "rows": [(1, "RETURN ", 25.5, 3.0, 9000.0), (2, "TBSCAN", 25.0, 3.0, 8000.0)],
            },
        ),
        "objs": (
            "FROM SYSTOOLS.EXPLAIN_OBJECT B",
            {"columns": ["A", "B", "C"], "rows": [("APP", "DEMO_SERVERS", "TA"), ("APP", "IDX1", "IX")]},
        ),
    }
    script.update(overrides)
    return list(script.values())


def test_explain_plan_runs_explain_reads_plan_and_cleans_up(dbi):
    dbi.script = _plan_script()
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT * FROM APP.DEMO_SERVERS")

    assert (result.status, result.source, result.total_cost) == ("OK", "db2", 25.5)
    assert [(o.operator_id, o.operator_type) for o in result.operators] == [(1, "RETURN"), (2, "TBSCAN")]
    assert [(o.name, o.object_type) for o in result.objects] == [
        ("DEMO_SERVERS", "TABLE"), ("IDX1", "INDEX"),
    ]
    conn = dbi.connections[0]
    stmts = conn.statements()
    explain_stmt = next(s for s in stmts if s.startswith("EXPLAIN PLAN"))
    tag = re.search(r"SET QUERYTAG = '([0-9a-f]{32})' FOR SELECT \* FROM APP.DEMO_SERVERS", explain_stmt).group(1)
    # The plan is read back by that exact tag (bound), then deleted.
    for sql, params in conn.executed:
        if "EXPLAIN_STATEMENT S WHERE" in sql or "EXPLAIN_OPERATOR O" in sql or "EXPLAIN_OBJECT B" in sql:
            assert params == (tag,)
    assert any(s.startswith("DELETE FROM SYSTOOLS.EXPLAIN_INSTANCE") for s in stmts)
    assert conn.commits == 1 and conn.closed


def test_each_explain_uses_a_fresh_tag(dbi):
    dbi.script = _plan_script()
    adapter = Db2DatabaseAdapter(real_settings())
    adapter.explain_plan("SELECT 1 FROM T")
    adapter.explain_plan("SELECT 1 FROM T")
    tags = [
        re.search(r"QUERYTAG = '([0-9a-f]+)'", s).group(1)
        for c in dbi.connections
        for s in c.statements()
        if s.startswith("EXPLAIN PLAN")
    ]
    assert len(tags) == 2 and tags[0] != tags[1]


def test_explain_schema_is_configurable(dbi):
    dbi.script = [
        ("FROM DB2INST1.EXPLAIN_STATEMENT S WHERE", {"columns": ["C"], "rows": [(1.0,)]}),
    ]
    result = Db2DatabaseAdapter(real_settings(db2_explain_schema="db2inst1")).explain_plan("SELECT 1 FROM T")
    assert result.status == "OK"
    assert all("SYSTOOLS" not in s for s in dbi.connections[0].statements())


def test_missing_explain_tables_is_unavailable_with_setup_hint(dbi):
    dbi.script = [("EXPLAIN PLAN", Exception("SQL0219N The required explain table does not exist. SQLSTATE=42704"))]
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert result.status == "UNAVAILABLE" and result.source == "none"
    assert result.sqlstate == "42704"
    assert "SYSINSTALLOBJECTS" in result.hint
    assert dbi.connections[0].rollbacks == 1 and dbi.connections[0].closed


def test_missing_privilege_is_unavailable_with_grant_hint(dbi):
    dbi.script = [("EXPLAIN PLAN", Exception("SQL0551N not authorized SQLSTATE=42501"))]
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert (result.status, result.sqlstate) == ("UNAVAILABLE", "42501")
    assert "005_dba_tools.sql" in result.hint


def test_unknown_object_in_statement_is_failed_not_unavailable(dbi):
    dbi.script = [("EXPLAIN PLAN", Exception("SQL0204N NOPE is an undefined name. SQLSTATE=42704"))]
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM NOPE")
    assert (result.status, result.sqlstate) == ("FAILED", "42704")


def test_syntax_error_is_failed(dbi):
    dbi.script = [("EXPLAIN PLAN", Exception("SQL0104N unexpected token SQLSTATE=42601"))]
    assert Db2DatabaseAdapter(real_settings()).explain_plan("SELECT FROM").status == "FAILED"


def test_timeout_is_unavailable(dbi):
    dbi.script = [("EXPLAIN PLAN", Exception("SQL0952N SQLSTATE=57014"))]
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert result.status == "UNAVAILABLE" and result.sqlstate == "57014"


def test_connection_failure_is_unavailable_never_raises(dbi):
    dbi.connect_error = Exception("refused SQLSTATE=08001")
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert result.status == "UNAVAILABLE" and result.source == "none"
    assert "live connection" in result.hint


def test_missing_driver_is_unavailable_never_raises(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "ibm_db_dbi", None)
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert result.status == "UNAVAILABLE"


def test_plan_not_readable_is_unavailable(dbi):
    dbi.script = [("FROM SYSTOOLS.EXPLAIN_STATEMENT S WHERE", {"columns": ["C"], "rows": []})]
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert result.status == "UNAVAILABLE" and "read back" in result.hint


def test_cleanup_failure_only_adds_a_warning(dbi):
    dbi.script = [("DELETE FROM SYSTOOLS", Exception("SQL0551N SQLSTATE=42501"))] + _plan_script()
    result = Db2DatabaseAdapter(real_settings()).explain_plan("SELECT 1 FROM T")
    assert result.status == "OK"
    assert any("left in the EXPLAIN tables" in w for w in result.warnings)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DROP TABLE T",
        "DELETE FROM T",
        "SELECT 1 FROM T; DROP TABLE T",
        "CALL SYSPROC.ADMIN_CMD('x')",
    ],
)
def test_adapter_refuses_anything_but_a_single_select(dbi, sql):
    result = Db2DatabaseAdapter(real_settings()).explain_plan(sql)
    assert result.status == "FAILED"
    assert dbi.connections == []  # not even a connection was opened


def test_explain_bool_wrapper(dbi):
    dbi.script = _plan_script()
    adapter = Db2DatabaseAdapter(real_settings())
    assert adapter.explain("SELECT 1 FROM T") is True
    dbi.script = [("EXPLAIN PLAN", Exception("SQL0551N SQLSTATE=42501"))]
    assert adapter.explain("SELECT 1 FROM T") is False


def test_explain_schema_must_be_a_plain_identifier():
    with pytest.raises(ValueError):
        real_settings(db2_explain_schema="SYSTOOLS; DROP TABLE X")


def test_closed_adapter_explain_is_unavailable(dbi):
    adapter = Db2DatabaseAdapter(real_settings())
    adapter.close()
    assert adapter.explain_plan("SELECT 1 FROM T").status == "UNAVAILABLE"


# ===================================================================================
# SQLAlchemy / ibm_db_sa URL helper
#
# Unit test: URL construction ONLY. Never call create_engine() here — that
# loads the ibm_db_sa dialect and the native ibm_db driver, which some
# hosts block (Application Control). Driver/dialect loading lives in the
# explicitly marked integration test (test_db2_dialect_integration.py).
# ===================================================================================
def test_sqlalchemy_url_uses_ibm_db_sa_dialect_and_masks_password():
    from sqlalchemy.engine import URL

    from app.database.dsn import sqlalchemy_url

    settings = real_settings(db2_host="db.example.test", db2_port=50001, db2_dbname="prod")
    url = sqlalchemy_url(settings)
    secret = settings.db2_ro_password.get_secret_value()

    assert isinstance(url, URL)
    assert url.drivername == "db2+ibm_db"
    assert (url.host, url.port, url.database) == ("db.example.test", 50001, "prod")
    assert url.username == settings.db2_ro_user

    # The credential IS carried inside the URL object (not dropped)...
    assert url.password == secret
    assert secret in url.render_as_string(hide_password=False)

    # ...but every supported rendering masks it.
    assert secret not in repr(url)
    assert secret not in str(url)
    assert secret not in url.render_as_string()  # default: hide_password=True
    masked = url.render_as_string(hide_password=True)
    assert secret not in masked and "***" in masked


# ===================================================================================
# End-to-end HTTP mapping in REAL mode (fake driver, no Db2)
# ===================================================================================
@pytest.fixture()
def real_client(monkeypatch, dbi):
    monkeypatch.setenv("ADAPTER_MODE", "real")
    monkeypatch.setenv("DB2_RO_PASSWORD", "pw-throwaway")
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application, raise_server_exceptions=False) as client:
        client.dbi = dbi  # type: ignore[attr-defined]
        yield client
    application.state.registry.close_all()
    get_settings.cache_clear()


def _error(response):
    return response.json()["error"]


def test_http_permission_denied_is_403(real_client):
    real_client.dbi.script = [("MON_GET_TABLE", Exception("SQL0551N SQLSTATE=42501"))]
    response = real_client.post("/api/v1/dba/tools/monitor.table_activity/run", json={})
    assert response.status_code == 403
    assert _error(response)["code"] == "DB_PERMISSION_DENIED"
    assert _error(response)["detail"]["sqlstate"] == "42501"


def test_http_object_not_found_is_404(real_client):
    real_client.dbi.script = [("SYSCAT.INDEXES", Exception("SQL0204N SQLSTATE=42704"))]
    response = real_client.post(
        "/api/v1/dba/tools/catalog.indexes/run", json={"params": {"table": "T"}}
    )
    assert response.status_code == 404
    assert _error(response)["code"] == "DB_OBJECT_NOT_FOUND"


def test_http_timeout_is_504(real_client):
    real_client.dbi.script = [("MON_GET_LOCKS", Exception("SQL0952N SQLSTATE=57014"))]
    response = real_client.post("/api/v1/dba/tools/monitor.lock_waits/run", json={})
    assert response.status_code == 504
    assert _error(response)["code"] == "UPSTREAM_TIMEOUT"


def test_http_db_down_is_503(real_client):
    real_client.dbi.connect_error = Exception("refused SQLSTATE=08001")
    response = real_client.post("/api/v1/dba/tools/catalog.tables/run", json={})
    assert response.status_code == 503
    assert _error(response)["code"] == "ADAPTER_UNAVAILABLE"


def test_http_syntax_error_in_execute_is_422_db_sql_error(real_client):
    real_client.dbi.script = [("FROM DEMO_SERVERS", Exception("SQL0104N bad SQLSTATE=42601"))]
    response = real_client.post("/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"})
    assert response.status_code == 422
    assert _error(response)["code"] == "DB_SQL_ERROR"


def test_http_successful_tool_run_reads_rows_from_db2(real_client):
    real_client.dbi.script = [
        ("FROM SYSCAT.TABLES", {"columns": ["TABNAME", "TYPE", "CARD", "NPAGES", "STATS_TIME", "TBSPACE"], "rows": [("T1", "T", 5, 1, None, "USERSPACE1")]}),
    ]
    body = real_client.post("/api/v1/dba/tools/catalog.tables/run", json={}).json()
    assert (body["mock"], body["source"]) == (False, "db2")
    assert body["rows"] == [["T1", "T", 5, 1, None, "USERSPACE1"]]


def test_http_explain_unavailable_is_200_with_hint(real_client):
    real_client.dbi.script = [("EXPLAIN PLAN", Exception("SQL0219N missing SQLSTATE=42704"))]
    response = real_client.post("/api/v1/sql/explain", json={"sql": "SELECT * FROM DEMO_SERVERS"})
    assert response.status_code == 200  # graceful fallback, not an error
    body = response.json()
    assert (body["status"], body["source"], body["mock"]) == ("UNAVAILABLE", "none", False)
    assert "SYSINSTALLOBJECTS" in body["hint"]


def test_http_explain_ok_returns_real_plan_shape(real_client):
    real_client.dbi.script = _plan_script()
    body = real_client.post("/api/v1/sql/explain", json={"sql": "SELECT * FROM DEMO_SERVERS"}).json()
    assert (body["status"], body["source"]) == ("OK", "db2")
    assert body["total_cost"] == 25.5
    assert any("full table scan" in line for line in body["summary"])


def test_http_tool_runs_write_audit_rows_to_db2(real_client):
    real_client.dbi.script = [("FROM SYSCAT.TABLES", {"columns": ["T"], "rows": [("T1",)]})]
    real_client.post("/api/v1/dba/tools/catalog.tables/run", json={})
    inserts = [
        (sql, params)
        for conn in real_client.dbi.connections
        for sql, params in conn.executed
        if sql.startswith("INSERT INTO APP.APP_AUDIT")
    ]
    assert inserts, "audit row should have been written through the Db2 audit adapter"
    params = inserts[-1][1]
    assert params[3] == "dba_tool" and params[4] == "ops"
    assert json.loads(params[-1])["tool"] == "catalog.tables"
