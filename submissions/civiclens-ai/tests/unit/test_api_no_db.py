"""API tests that do not need a database (liveness, validation, 503 handling).

Phase 01B: /api/health reveals no version, /api/health/db reveals nothing, the 503 body is generic,
and complaint intake requires an analyst token (so invalid bodies are 401 before they are 422).
"""

import pytest
from fastapi.testclient import TestClient

from civiclens.api.deps import get_db
from civiclens.api.main import create_app

ANALYST = "a" * 30


@pytest.fixture()
def tokens(monkeypatch):
    monkeypatch.setenv("CIVICLENS_AUTH_TOKENS", f"alice:analyst:{ANALYST},rita:reviewer:{'r' * 30}")


def test_health_is_db_independent_and_minimal():
    r = TestClient(create_app()).get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}  # no version, no environment details


def test_db_health_returns_generic_503_without_credentials(monkeypatch):
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    r = TestClient(create_app()).get("/api/health/db")
    assert r.status_code == 503
    assert r.json()["detail"] == {
        "code": "DB_UNAVAILABLE",
        "message": "The database is temporarily unavailable.",
    }
    for leaked in ("DB2_PASSWORD", "db2inst1", "localhost", "50000", "CIVICDB"):
        assert leaked not in r.text


def test_invalid_complaint_is_rejected_before_db(tokens):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None  # never reached for invalid bodies
    r = TestClient(app).post(
        "/api/complaints",
        json={"category": "NOPE", "title": "x"},
        headers={"Authorization": f"Bearer {ANALYST}"},
    )
    assert r.status_code == 422
