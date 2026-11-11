"""DBA tools API + service (mock mode, offline)."""

from __future__ import annotations

import pytest

from app.dba.specs import TOOLS


def _run(client, tool_id, params=None, **extra):
    return client.post(
        f"/api/v1/dba/tools/{tool_id}/run", json={"params": params or {}, **extra}
    )


def _newest_audit(client):
    return client.get("/api/v1/audit", params={"limit": 1}).json()["entries"][0]


# -- catalogue ------------------------------------------------------------------
def test_list_tools_describes_every_tool(client):
    body = client.get("/api/v1/dba/tools").json()
    assert body["mock"] is True
    assert {t["id"] for t in body["tools"]} == {t.id for t in TOOLS}
    columns = next(t for t in body["tools"] if t["id"] == "catalog.columns")
    assert {p["name"] for p in columns["params"]} == {"schema", "table", "limit"}
    assert next(p for p in columns["params"] if p["name"] == "table")["required"] is True
    assert all(t["requires"] for t in body["tools"])


# -- every tool has a working mock equivalent -------------------------------------
@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.id)
def test_every_tool_runs_in_mock_mode(client, spec):
    params = {"table": "DEMO_INCIDENTS"} if any(p.name == "table" and p.required for p in spec.params) else {}
    response = _run(client, spec.id, params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tool_id"] == spec.id
    assert body["kind"] == spec.kind
    assert body["mock"] is True and body["source"] == "mock"
    assert body["columns"]
    assert body["row_count"] == len(body["rows"]) > 0
    assert all(len(row) == len(body["columns"]) for row in body["rows"])
    assert any("mock" in n.lower() for n in body["notes"])


def test_catalog_tables_lists_app_tables(client):
    body = _run(client, "catalog.tables").json()
    names = [r[0] for r in body["rows"]]
    assert "DEMO_SERVERS" in names and "DEMO_INCIDENTS" in names
    assert body["params"]["schema"] == "APP"


def test_catalog_columns_match_schema_for_table(client):
    body = _run(client, "catalog.columns", {"table": "demo_servers"}).json()
    assert body["params"]["table"] == "DEMO_SERVERS"
    assert [r[0] for r in body["rows"]] == [
        "SERVER_ID", "HOSTNAME", "ENVIRONMENT", "OWNER_TEAM", "UPTIME_PCT",
    ]
    assert body["rows"][4][2] == "DECIMAL" and body["rows"][4][3:5] == [5, 2]


def test_catalog_indexes_and_constraints_mirror_migrations(client):
    idx = _run(client, "catalog.indexes", {"table": "DEMO_INCIDENTS"}).json()
    assert {r[0] for r in idx["rows"]} >= {"IDX_INCIDENTS_SERVER", "IDX_INCIDENTS_SEVERITY"}
    con = _run(client, "catalog.constraints", {"table": "DEMO_INCIDENTS"}).json()
    assert {r[1] for r in con["rows"]} == {"P", "F"}


def test_unknown_table_returns_empty_not_error(client):
    body = _run(client, "catalog.columns", {"table": "NO_SUCH_TABLE"}).json()
    assert body["rows"] == [] and body["row_count"] == 0


def test_other_schema_returns_empty(client):
    assert _run(client, "catalog.tables", {"schema": "OTHER"}).json()["rows"] == []


def test_stale_statistics_flags_missing_stats(client):
    rows = _run(client, "catalog.stale_statistics").json()["rows"]
    by_name = {r[0]: r[6] for r in rows}
    assert by_name["DOCUMENT_METADATA"] == "NO_STATS"
    assert by_name["APP_AUDIT"] == "COLLECTED"
    assert rows[0][0] == "DOCUMENT_METADATA"  # never-collected sorts first


def test_monitoring_tells_the_missing_index_story(client):
    hot = _run(client, "monitor.table_activity").json()["rows"]
    assert hot[0][1] == "DEMO_INCIDENTS"  # most rows read
    assert hot == sorted(hot, key=lambda r: -r[3])
    unused = _run(client, "monitor.index_usage").json()["rows"]
    assert unused[0][2] == 0  # least-used index first
    slow = _run(client, "monitor.slow_statements").json()["rows"]
    assert "RESOLVED_AT" in slow[0][5]


def test_bufferpool_hit_ratio_is_computed(client):
    row = _run(client, "monitor.bufferpool_hit_ratio").json()["rows"][0]
    assert row[0] == "IBMDEFAULTBP"
    logical, physical = row[1] + row[3], row[2] + row[4]
    assert row[5] == pytest.approx(1 - physical / logical, abs=1e-4)


def test_limit_truncates_and_flags(client):
    body = _run(client, "catalog.tables", {"limit": 2}).json()
    assert body["row_count"] == 2 and body["truncated"] is True
    assert body["params"]["limit"] == 2


# -- errors -----------------------------------------------------------------------
def test_unknown_tool_is_404_with_available_list(client):
    response = _run(client, "catalog.nope")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert "catalog.tables" in error["detail"]["available"]


@pytest.mark.parametrize(
    ("tool", "params"),
    [
        ("catalog.columns", {}),
        ("catalog.columns", {"table": "T; DROP TABLE X"}),
        ("catalog.tables", {"schema": "SYSCAT"}),
        ("catalog.tables", {"limit": 0}),
        ("catalog.tables", {"limit": 1000}),
        ("catalog.tables", {"sql": "SELECT 1"}),
        ("monitor.slow_statements", {"table": "X"}),
    ],
)
def test_invalid_params_are_422_invalid_tool_params(client, tool, params):
    response = _run(client, tool, params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_TOOL_PARAMS"


def test_malformed_body_uses_validation_envelope(client):
    response = client.post(
        "/api/v1/dba/tools/catalog.tables/run", json={"params": {}, "extra": 1}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# -- audit ------------------------------------------------------------------------
def test_successful_run_is_audited(client):
    _run(client, "catalog.tables", session_id="s-1")
    entry = _newest_audit(client)
    assert entry["operation"] == "dba_tool"
    assert entry["status"] == "OK"
    assert entry["question"] == "Run DBA tool: catalog.tables"
    assert entry["timestamp"]


def test_rejected_params_are_audited(client):
    _run(client, "catalog.columns", {"table": "T; DROP"})
    entry = _newest_audit(client)
    assert entry["operation"] == "dba_tool"
    assert entry["status"] == "REJECTED"
    assert "INVALID_TOOL_PARAMS" in entry["detail"]


def test_audit_failure_does_not_break_tool(client, app):
    def broken(entry):
        raise RuntimeError("audit down")

    app.state.registry.audit.record = broken
    assert _run(client, "catalog.tables").status_code == 200


# -- default (mock-only) installation ---------------------------------------------------
def test_mock_mode_never_needs_the_db2_driver(monkeypatch):
    """The default install has no ibm_db/sqlalchemy: mock mode must not care."""
    import sys

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    for module in ("ibm_db", "ibm_db_dbi", "ibm_db_sa", "sqlalchemy"):
        monkeypatch.setitem(sys.modules, module, None)  # import raises ImportError
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        assert _run(client, "catalog.tables").status_code == 200
        plan = client.post("/api/v1/sql/explain", json={"sql": "SELECT * FROM DEMO_SERVERS"})
        assert plan.json()["status"] == "OK"
        run = client.post("/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"})
        assert run.status_code == 200
    application.state.registry.close_all()
    get_settings.cache_clear()


# -- safety -------------------------------------------------------------------------
def test_statement_text_from_monitoring_is_redacted(client, app):
    from app.dba import mock_data

    original = mock_data.SLOW_STATEMENTS
    mock_data.SLOW_STATEMENTS = [
        (1, 1, 1, 1, 1, "SELECT * FROM T WHERE note = 'x' AND password=hunter2"),
    ]
    try:
        text = _run(client, "monitor.slow_statements").text
    finally:
        mock_data.SLOW_STATEMENTS = original
    assert "hunter2" not in text


def test_tool_run_never_passes_user_text_into_sql(client, app):
    seen = []
    original = app.state.registry.database.run_dba_tool

    def spy(tool_id, sql, params, limit):
        seen.append((sql, tuple(params)))
        return original(tool_id, sql, params, limit)

    app.state.registry.database.run_dba_tool = spy
    _run(client, "catalog.columns", {"table": "demo_servers", "schema": "app", "limit": 7})
    sql, params = seen[0]
    assert params == ("APP", "DEMO_SERVERS")
    assert "DEMO_SERVERS" not in sql and "FETCH FIRST 7 ROWS ONLY" in sql
