"""Shared test setup. Tests run against an isolated, auto-seeded SQLite file by default;
set NSIN_TEST_DB2=1 (plus DB2_* variables) to run the Db2 integration tests as well."""
import os
import sys
import uuid
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

TEST_DB = SRC_DIR / "test_neighbourhood_safety.db"
if os.environ.get("NSIN_TEST_DB2") != "1":
    os.environ["DATABASE_MODE"] = "sqlite"
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
    if TEST_DB.exists():
        TEST_DB.unlink()  # start every run from a freshly seeded database

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.database.base import init_db  # noqa: E402
from backend.app.main import app  # noqa: E402

DEMO_PASSWORD = "Password123!"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def auth_headers(client, email: str, password: str = DEMO_PASSWORD) -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.org"


@pytest.fixture
def resident(client):
    return auth_headers(client, "resident@neighbourhood.org")


@pytest.fixture
def responder(client):
    return auth_headers(client, "responder@neighbourhood.org")


@pytest.fixture
def admin(client):
    return auth_headers(client, "admin@neighbourhood.org")
