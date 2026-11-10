import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from backend.main import app


def test_attempt_validation():
    with TestClient(app) as client:
        response = client.post("/attempts", json={"learner_id": "", "topic": "x", "score": 101})
        assert response.status_code == 422


def test_health_explicit_offline_without_db():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] in {"ok", "offline"}


def test_write_returns_offline_when_db2_is_unavailable():
    with TestClient(app) as client:
        response = client.post("/attempts", json={
            "learner_id": "learner-1", "topic": "python", "score": 80
        })
        assert response.status_code == 503
        assert response.json()["detail"]["status"] == "offline"
