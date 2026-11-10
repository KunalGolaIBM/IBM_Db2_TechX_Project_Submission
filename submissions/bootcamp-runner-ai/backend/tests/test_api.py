import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from backend.main import app


def test_profile_validation():
    with TestClient(app) as client:
        response = client.post("/players/profile", json={"player_id": "", "display_name": "A", "email": "a@b.test"})
        assert response.status_code == 422


def test_health_explicit_offline_without_db():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] in {"ok", "offline"}


def test_write_returns_offline_when_db2_is_unavailable():
    with TestClient(app) as client:
        response = client.post("/game/sessions", json={"player_id": "player-1"})
        assert response.status_code == 503
        assert response.json()["detail"]["status"] == "offline"
