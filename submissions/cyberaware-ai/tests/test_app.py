import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"CyberAware AI" in response.data


def test_health_endpoint(client):
    response = client.get("/api/health")

    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "running"
    assert data["application"] == "CyberAware AI"


def test_assistant_endpoint(client):
    response = client.post(
        "/api/ask",
        json={"question": "How can I avoid scams?"}
    )

    assert response.status_code == 200

    data = response.get_json()
    assert "answer" in data
    assert "Cybersecurity Tip" in data["answer"]


def test_empty_question(client):
    response = client.post(
        "/api/ask",
        json={"question": ""}
    )

    assert response.status_code == 400
