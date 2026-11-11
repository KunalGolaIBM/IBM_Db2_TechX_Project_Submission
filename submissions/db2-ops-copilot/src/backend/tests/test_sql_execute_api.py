"""POST /api/v1/sql/execute — API-level behaviour (mock mode, offline)."""

from __future__ import annotations

import pytest


def _newest_audit(client):
    return client.get("/api/v1/audit", params={"limit": 1}).json()["entries"][0]


def test_execute_valid_select_returns_rows(client):
    response = client.post(
        "/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mock"] is True
    assert body["columns"][0] == "SERVER_ID"
    assert body["row_count"] == len(body["rows"]) == 4
    assert body["request_id"]
    assert body["row_limit"] == 100


def test_execute_applies_hard_row_cap_wrapper(client):
    body = client.post(
        "/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"}
    ).json()
    assert body["row_limit_applied"] is True
    assert "FETCH FIRST 100 ROWS ONLY" in body["executed_sql"].upper()


def test_execute_keeps_existing_small_fetch_first(client):
    body = client.post(
        "/api/v1/sql/execute",
        json={"sql": "SELECT * FROM DEMO_SERVERS FETCH FIRST 2 ROWS ONLY"},
    ).json()
    assert body["row_limit_applied"] is False
    assert body["row_count"] == 2


def test_execute_reports_explain_status(client):
    body = client.post(
        "/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"}
    ).json()
    assert body["explain_status"] == "OK"


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE DEMO_SERVERS",
        "DELETE FROM DEMO_SERVERS",
        "UPDATE DEMO_SERVERS SET HOSTNAME = 'x'",
        "INSERT INTO DEMO_SERVERS VALUES (9, 'x', 'dev', 'y', 1.0)",
        "SELECT * FROM SYSCAT.TABLES",
        "SELECT 1 FROM SYSIBM.SYSDUMMY1; DROP TABLE DEMO_SERVERS",
        "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE APP.X')",
    ],
)
def test_execute_rejects_unsafe_sql(client, sql):
    response = client.post("/api/v1/sql/execute", json={"sql": sql})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "SQL_REJECTED"
    assert error["detail"]["violations"]


def test_execute_rejection_never_reaches_database(client, app):
    calls: list[str] = []
    original = app.state.registry.database.execute_readonly

    def spy(sql, params=None, timeout_ms=None):
        calls.append(sql)
        return original(sql, params, timeout_ms)

    app.state.registry.database.execute_readonly = spy
    client.post("/api/v1/sql/execute", json={"sql": "DROP TABLE DEMO_SERVERS"})
    assert calls == []
    client.post("/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"})
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"sql": ""},
        {"sql": "x" * 5001},
        {"sql": "SELECT 1", "unexpected": True},
    ],
)
def test_execute_malformed_requests_use_validation_envelope(client, payload):
    response = client.post("/api/v1/sql/execute", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_execute_success_is_audited_with_timestamp(client):
    client.post(
        "/api/v1/sql/execute",
        json={"sql": "SELECT * FROM DEMO_SERVERS", "session_id": "sess-1"},
    )
    entry = _newest_audit(client)
    assert entry["operation"] == "sql_execute"
    assert entry["status"] == "OK"
    assert entry["timestamp"]
    assert entry["question"].startswith("Execute SQL:")


def test_execute_rejection_is_audited_with_timestamp_and_question(client):
    client.post("/api/v1/sql/execute", json={"sql": "DROP TABLE DEMO_SERVERS"})
    entry = _newest_audit(client)
    assert entry["operation"] == "sql_execute"
    assert entry["status"] == "REJECTED_BY_GATE"
    # Regression: both used to be empty strings.
    assert entry["timestamp"]
    assert "DROP TABLE" in entry["question"]
    assert "statement_not_allowed" in (entry["detail"] or "")


def test_execute_response_does_not_leak_secrets(client):
    text = client.post(
        "/api/v1/sql/execute", json={"sql": "SELECT * FROM DEMO_SERVERS"}
    ).text.lower()
    for forbidden in ("password", "secret", "api_key"):
        assert forbidden not in text
