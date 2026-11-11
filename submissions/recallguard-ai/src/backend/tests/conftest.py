"""Test fixtures. Tests run against the labelled DEV MODE engine executing the same
Db2 SQL files (no Db2 server is required). Set RG_TEST_DB2=1 with DB2_* env vars to
run the same suite against a real IBM Db2 instance."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_tmp = tempfile.mkdtemp(prefix="recallguard-test-")
if os.getenv("RG_TEST_DB2") != "1":
    os.environ["DB_MODE"] = "dev"
    os.environ["DEV_DB_PATH"] = str(Path(_tmp) / "test.sqlite")
os.environ["UPLOAD_DIR"] = str(Path(_tmp) / "uploads")
os.environ["LLM_PROVIDER"] = "none"
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("REQUIRE_AUTH_HEADERS", "false")


@pytest.fixture(scope="session")
def db():
    from app.database import init_database

    return init_database()


@pytest.fixture(scope="session")
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


ANALYST = {"X-User-Id": "analyst@test", "X-User-Role": "analyst"}
MANAGER = {"X-User-Id": "manager@test", "X-User-Role": "recall_manager"}
VIEWER = {"X-User-Id": "viewer@test", "X-User-Role": "viewer"}
