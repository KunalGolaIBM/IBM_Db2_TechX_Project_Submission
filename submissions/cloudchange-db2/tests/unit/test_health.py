"""Unit tests for System Health API."""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check():
    """Verify that /health returns 200 OK and valid status dictionary."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "cloudchange-api"
    assert "version" in data
