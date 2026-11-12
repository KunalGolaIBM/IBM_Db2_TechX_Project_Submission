"""Integration test setup: every test runs against a real IBM Db2 database and, for AI features, a
real local Ollama server. Nothing is mocked.

Defaults match the local Db2 instance used for development (TESTDB on localhost:50000); override
with DB2_HOST / DB2_PORT / DB2_DATABASE (or DB2_NAME) / DB2_USER (or DB2_USERNAME) / DB2_PASSWORD.
At the start of a run the application's tables are dropped and recreated, so results are repeatable.
Set NSIN_KEEP_DB=1 to skip the reset (e.g. when running as the least-privilege login).
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("DB2_HOST", "localhost")
os.environ.setdefault("DB2_PORT", "50000")
if not (os.environ.get("DB2_DATABASE") or os.environ.get("DB2_NAME")):
    os.environ["DB2_DATABASE"] = "TESTDB"
if not (os.environ.get("DB2_USER") or os.environ.get("DB2_USERNAME")):
    os.environ["DB2_USER"] = "db2inst1"
os.environ.setdefault("DB2_PASSWORD", "1234")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.database import base as db_base  # noqa: E402
from backend.app.database.db2_adapter import Db2Adapter  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models.entities import Base  # noqa: E402

DEMO_PASSWORD = "Password123!"
EXTRA_TABLES = ("INCIDENT_EMBEDDINGS", "NSIN_PROTOCOL_PASSAGES")


def reset_database() -> None:
    """Drop the application's tables in Db2 (vector tables first, then the ORM tables)."""
    engine = create_engine(Db2Adapter().sqlalchemy_url())
    with engine.begin() as conn:
        for table in EXTRA_TABLES:
            if conn.execute(text("SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = :t"),
                            {"t": table}).first():
                conn.execute(text(f"DROP TABLE {table}"))
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    if os.environ.get("NSIN_KEEP_DB") != "1":
        reset_database()
    db_base.init_db()


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
