"""EXPLAIN: mock API behaviour, service fallbacks and summaries (offline)."""

from __future__ import annotations

import pytest

from app.adapters.base import ExplainObject, ExplainOperator, ExplainResult
from app.adapters.registry import AdapterRegistry
from app.core.config import Settings
from app.core.errors import SqlRejectedError
from app.services.explain_service import ExplainService, summarize_plan
from app.services.sql_guard_service import SqlGuardService


def _explain(client, sql, **extra):
    return client.post("/api/v1/sql/explain", json={"sql": sql, **extra})


def _service(**overrides):
    settings = Settings(_env_file=None, **overrides)
    registry = AdapterRegistry(settings)
    return (
        ExplainService(settings, registry, SqlGuardService(registry.validator)),
        registry,
    )


# -- API (mock) ---------------------------------------------------------------------
def test_explain_returns_labelled_mock_plan(client):
    response = _explain(client, "SELECT * FROM DEMO_SERVERS")
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["source"], body["mock"]) == ("OK", "mock", True)
    assert body["total_cost"] > 0
    types = [o["operator_type"] for o in body["operators"]]
    assert types[0] == "RETURN" and "TBSCAN" in types
    assert any(w.lower().startswith("synthetic plan") for w in body["warnings"])
    assert any("full table scan" in line for line in body["summary"])


def test_explain_explains_the_capped_statement(client):
    body = _explain(client, "SELECT * FROM DEMO_SERVERS").json()
    assert "FETCH FIRST 100 ROWS ONLY" in body["explained_sql"].upper()


def test_mock_plan_uses_index_when_filter_is_indexed(client):
    body = _explain(client, "SELECT * FROM DEMO_INCIDENTS WHERE SEVERITY = 3").json()
    types = [o["operator_type"] for o in body["operators"]]
    assert "IXSCAN" in types and "TBSCAN" not in types
    assert any(o["object_type"] == "INDEX" and o["name"] == "IDX_INCIDENTS_SEVERITY" for o in body["objects"])


def test_mock_plan_scans_when_filter_is_not_indexed(client):
    body = _explain(client, "SELECT * FROM DEMO_INCIDENTS WHERE RESOLVED_AT IS NULL").json()
    types = [o["operator_type"] for o in body["operators"]]
    assert "TBSCAN" in types and "IXSCAN" not in types


def test_mock_plan_join_and_sort_operators(client):
    body = _explain(
        client,
        "SELECT S.HOSTNAME, I.SEVERITY FROM DEMO_SERVERS S "
        "JOIN DEMO_INCIDENTS I ON I.SERVER_ID = S.SERVER_ID ORDER BY I.SEVERITY",
    ).json()
    types = [o["operator_type"] for o in body["operators"]]
    assert {"HSJOIN", "SORT", "RETURN"} <= set(types)
    assert {o["name"] for o in body["objects"] if o["object_type"] == "TABLE"} == {
        "DEMO_SERVERS", "DEMO_INCIDENTS",
    }
    assert any("hash join" in line for line in body["summary"])


@pytest.mark.parametrize(
    "sql",
    ["DROP TABLE DEMO_SERVERS", "SELECT * FROM SYSCAT.TABLES", "SELECT 1 FROM T; DROP TABLE T"],
)
def test_explain_rejects_unsafe_sql_with_422(client, sql):
    response = _explain(client, sql)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SQL_REJECTED"


def test_rejected_explain_never_reaches_database(client, app):
    calls = []
    app.state.registry.database.explain_plan = lambda *a, **k: calls.append(a)
    _explain(client, "DELETE FROM DEMO_SERVERS")
    assert calls == []


def test_explain_does_not_execute_the_statement(client, app):
    executed = []
    app.state.registry.database.execute_readonly = lambda *a, **k: executed.append(a)
    assert _explain(client, "SELECT * FROM DEMO_SERVERS").status_code == 200
    assert executed == []


def test_explain_malformed_request(client):
    assert _explain(client, "").status_code == 422
    assert client.post("/api/v1/sql/explain", json={}).json()["error"]["code"] == "VALIDATION_ERROR"


def test_explain_is_audited_with_operation_and_timestamp(client):
    _explain(client, "SELECT * FROM DEMO_SERVERS")
    entry = client.get("/api/v1/audit", params={"limit": 1}).json()["entries"][0]
    assert entry["operation"] == "sql_explain"
    assert entry["status"] == "OK" and entry["timestamp"]
    assert entry["question"].startswith("Explain SQL:")


def test_rejected_explain_is_audited(client):
    _explain(client, "DROP TABLE DEMO_SERVERS")
    entry = client.get("/api/v1/audit", params={"limit": 1}).json()["entries"][0]
    assert (entry["operation"], entry["status"]) == ("sql_explain", "REJECTED_BY_GATE")


# -- service fallbacks -----------------------------------------------------------------
def test_unavailable_plan_is_reported_not_raised():
    service, registry = _service()
    registry.database.explain_plan = lambda sql, timeout_ms=None: ExplainResult(
        status="UNAVAILABLE", source="none", sqlstate="42501", hint="grant EXPLAIN tables"
    )
    result = service.explain("SELECT * FROM DEMO_SERVERS", request_id="r1")
    assert (result.status, result.source, result.sqlstate) == ("UNAVAILABLE", "none", "42501")
    assert result.hint == "grant EXPLAIN tables"
    assert result.operators == [] and result.summary == []
    assert registry.audit.list_recent(limit=1)[0].status == "UNAVAILABLE"


def test_failed_plan_is_reported():
    service, registry = _service()
    registry.database.explain_plan = lambda sql, timeout_ms=None: ExplainResult(
        status="FAILED", source="none", sqlstate="42601", detail="bad"
    )
    assert service.explain("SELECT * FROM DEMO_SERVERS", request_id="r").status == "FAILED"


def test_adapter_exception_degrades_to_unavailable():
    service, registry = _service()

    def boom(sql, timeout_ms=None):
        raise RuntimeError("driver exploded")

    registry.database.explain_plan = boom
    result = service.explain("SELECT * FROM DEMO_SERVERS", request_id="r")
    assert result.status == "UNAVAILABLE" and result.detail == "RuntimeError"


def test_audit_failure_does_not_mask_explain():
    service, registry = _service()

    def broken(entry):
        raise RuntimeError("audit down")

    registry.audit.record = broken
    assert service.explain("SELECT * FROM DEMO_SERVERS", request_id="r").status == "OK"
    with pytest.raises(SqlRejectedError):
        service.explain("DROP TABLE X", request_id="r")


def test_session_timeout_is_passed_to_adapter():
    service, registry = _service(sql_query_timeout_ms=4321)
    seen = {}
    original = registry.database.explain_plan

    def spy(sql, timeout_ms=None):
        seen["timeout_ms"] = timeout_ms
        return original(sql, timeout_ms)

    registry.database.explain_plan = spy
    service.explain("SELECT * FROM DEMO_SERVERS", request_id="r")
    assert seen["timeout_ms"] == 4321


# -- summaries ------------------------------------------------------------------------------
def _ok(operators, objects, cost=12.5):
    return ExplainResult(status="OK", source="db2", total_cost=cost, operators=operators, objects=objects)


def test_summary_mentions_cost_scan_and_tables():
    lines = summarize_plan(
        _ok(
            [ExplainOperator(1, "RETURN"), ExplainOperator(2, "TBSCAN")],
            [ExplainObject("APP", "T1", "TABLE")],
        )
    )
    assert lines[0] == "Estimated total cost: 12.5 timerons."
    assert "1 full table scan(s) over APP.T1" in lines[1]


def test_summary_mentions_index_access_and_sort():
    lines = summarize_plan(
        _ok(
            [ExplainOperator(1, "RETURN"), ExplainOperator(2, "SORT"), ExplainOperator(3, "IXSCAN")],
            [ExplainObject("APP", "T1", "TABLE"), ExplainObject("APP", "IX1", "INDEX")],
        )
    )
    assert any("APP.IX1" in line for line in lines)
    assert any("sort" in line for line in lines)
    assert not any("full table scan" in line for line in lines)


def test_summary_is_empty_for_non_ok_plans():
    assert summarize_plan(ExplainResult(status="UNAVAILABLE", source="none")) == []
