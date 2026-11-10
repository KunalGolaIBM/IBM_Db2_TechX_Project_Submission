"""Tests for deployment health endpoints."""

from fastapi.testclient import TestClient

from app import api

client = TestClient(api.app)


def test_healthz_reports_db2_version(monkeypatch):
    def fake_query(sql, params=()):
        if "ENV_INST_INFO" in sql:
            return [("DB2 12.1.2",)]
        return [(1,)]

    monkeypatch.setattr(api, "query", fake_query)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db2": "DB2 12.1.2"}


def test_healthz_rejects_missing_db_version(monkeypatch):
    monkeypatch.setattr(api, "query", lambda sql, params=(): [])

    response = client.get("/healthz")

    assert response.status_code == 503


def test_health_returns_real_503_response(monkeypatch):
    def failing_query(sql, params=()):
        raise RuntimeError("Db2 unavailable")

    monkeypatch.setattr(api, "query", failing_query)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
