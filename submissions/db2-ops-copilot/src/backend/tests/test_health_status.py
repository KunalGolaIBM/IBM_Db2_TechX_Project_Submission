"""Health and status endpoints — offline (mock adapters) behaviour."""

from __future__ import annotations


def test_health_ok_in_mock_mode(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"
    assert body["api_version"] == "v1"
    names = {check["name"] for check in body["checks"]}
    assert names == {
        "database",
        "vector_store",
        "llm",
        "embeddings",
        "orchestrator",
        "audit",
    }
    assert all(check["status"] == "ok" for check in body["checks"])
    assert all(check["mode"] == "mock" for check in body["checks"])


def test_health_is_degraded_not_down_when_a_probe_fails(client):
    registry = client.app.state.registry

    def broken_ping():
        from app.adapters.base import ProbeResult

        return ProbeResult(
            name="database", status="unavailable", mode="mock", latency_ms=0.0, detail="broken"
        )

    registry.database.ping = broken_ping
    response = client.get("/api/v1/health")
    assert response.status_code == 200  # app itself is healthy
    body = response.json()
    assert body["status"] == "degraded"
    db_check = next(c for c in body["checks"] if c["name"] == "database")
    assert db_check["status"] == "unavailable"
    assert db_check["detail"] == "broken"


def test_status_dashboard(client):
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["adapter_mode"] == "mock"
    assert body["database"]["connected"] is True
    assert body["database"]["provider"] == "mock"
    assert body["llm"]["available"] is True
    assert body["embeddings"]["dimensions"] == 768
    assert body["vector_store"]["document_count"] >= 5


def test_status_never_leaks_secrets(client):
    response = client.get("/api/v1/status")
    text = response.text.lower()
    for forbidden in ("password", "secret", "token", "credential"):
        assert forbidden not in text
