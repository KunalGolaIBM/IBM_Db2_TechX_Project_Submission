from __future__ import annotations

from starlette.testclient import TestClient

from backend.app.main import create_app

from .conftest import DisabledCoach, FakeCoach, FakeRepository, request_payload


def test_game_history_analytics_and_coaching_api(settings) -> None:
    repository = FakeRepository()
    client = TestClient(create_app(settings, repository, FakeCoach()))
    payload = request_payload()

    first = client.post("/api/v1/games", json=payload)
    retry = client.post("/api/v1/games", json=payload)
    listing = client.get("/api/v1/games", params={"limit": 10, "offset": 0})
    detail = client.get(f"/api/v1/games/{payload['client_game_id']}")
    analytics = client.get("/api/v1/analytics/summary")
    coaching = client.post("/api/v1/coaching", json={"game_id": payload["client_game_id"]})

    assert first.status_code == 201 and first.json()["created"] is True
    assert retry.status_code == 200 and retry.json()["created"] is False
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert detail.status_code == 200 and len(detail.json()["moves"]) == 7
    assert analytics.status_code == 200 and analytics.json()["wins"] == 1
    assert coaching.status_code == 200 and coaching.json()["provider"] == "fake"


def test_disabled_coaching_does_not_affect_health_or_analytics(settings) -> None:
    repository = FakeRepository()
    client = TestClient(create_app(settings, repository, DisabledCoach()))

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "database": "ok",
        "coaching_enabled": False,
        "llm_provider": None,
    }
    assert client.get("/api/v1/analytics/summary").status_code == 200
    response = client.post("/api/v1/coaching", json={})
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "coaching_disabled", "detail": "AI coaching is disabled"}}


def test_validation_errors_are_structured_and_lists_are_bounded(settings) -> None:
    client = TestClient(create_app(settings, FakeRepository(), FakeCoach()))

    invalid = client.post("/api/v1/games", json={})
    too_large = client.get("/api/v1/games", params={"limit": 101})

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert too_large.status_code == 422
    assert too_large.json()["error"]["code"] == "validation_error"


def test_unexpected_errors_do_not_leak_driver_or_credential_details(settings) -> None:
    repository = FakeRepository()

    def fail_summary():
        raise RuntimeError("DB2_PASSWORD=do-not-leak")

    repository.analytics_summary = fail_summary  # type: ignore[method-assign]
    client = TestClient(create_app(settings, repository, FakeCoach()), raise_server_exceptions=False)

    response = client.get("/api/v1/analytics/summary")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "detail": "Unexpected server error"}}
    assert "do-not-leak" not in response.text

