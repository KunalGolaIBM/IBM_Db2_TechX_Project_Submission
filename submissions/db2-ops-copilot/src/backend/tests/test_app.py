"""Application startup, root endpoint and error-envelope behaviour."""

from __future__ import annotations


def test_app_starts_offline(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Db2 Ops Copilot"
    assert body["api"] == "/api/v1"


def test_registry_attached_at_startup(client):
    assert hasattr(client.app.state, "registry")
    assert client.app.state.registry.mode == "mock"
    assert client.app.state.started_at > 0


def test_request_id_header_present(client):
    response = client.get("/api/v1/health")
    assert "x-request-id" in response.headers


def test_request_id_echoed(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-123"})
    assert response.headers["x-request-id"] == "test-123"


def test_unknown_api_route_returns_json_envelope(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body["error"]


def test_unknown_root_route_is_404(client):
    response = client.get("/nope")
    # Without a built frontend mounted, unknown paths fall through to FastAPI 404.
    assert response.status_code == 404


def test_validation_error_envelope(client):
    response = client.post("/api/v1/chat", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["error"]["detail"], list)


def test_oversized_chat_message_rejected(client):
    response = client.post(
        "/api/v1/chat", json={"message": "x" * 5000}
    )
    assert response.status_code == 422


def test_openapi_schema_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/api/v1/health",
        "/api/v1/status",
        "/api/v1/config",
        "/api/v1/chat",
        "/api/v1/sql/validate",
        "/api/v1/audit",
    ):
        assert expected in paths
