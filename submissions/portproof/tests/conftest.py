"""Shared fixtures.

The unit tests never touch Db2, so they run anywhere. Tests that need a live
database are marked ``db2`` and skip themselves cleanly when it is unreachable,
so ``pytest -q`` passes on a machine with no container running.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# The suite must not depend on, or spend, anybody's API key. Whatever .env says,
# tests run on the deterministic tiers; the tests that exercise the model tiers
# bring a scripted model of their own. Set before src.config is imported, and
# dotenv does not override what is already in the environment.
os.environ["LLM_PROVIDER"] = os.environ.get("PORTPROOF_TEST_LLM_PROVIDER", "mock")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _db2_available() -> tuple[bool, str]:
    try:
        from src import db
        from src.config import setup_config

        conn = db.connect(setup_config(), role="setup")
        version = db.server_version(conn)
        import ibm_db

        ibm_db.close(conn)
        return True, version
    except Exception as exc:  # pragma: no cover - environment dependent
        return False, str(exc)[:120]


DB2_UP, DB2_WHY = _db2_available()


def pytest_collection_modifyitems(config, items):
    """Skip everything marked ``db2`` when no database answers."""
    if DB2_UP:
        return
    skip = pytest.mark.skip(reason=f"Db2 not reachable: {DB2_WHY}")
    for item in items:
        if "db2" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def owner_conn():
    from src import db
    from src.config import setup_config

    conn = db.connect(setup_config(), role="setup")
    yield conn
    try:
        import ibm_db

        ibm_db.close(conn)
    except Exception:
        pass


@pytest.fixture(scope="session")
def app_conn():
    from src import db
    from src.config import runtime_config

    conn = db.connect(runtime_config(), role="app")
    db.execute(conn, "SET CURRENT SCHEMA PORTPROOF")
    yield conn
    try:
        import ibm_db

        ibm_db.close(conn)
    except Exception:
        pass


@pytest.fixture(scope="session")
def loaded_target(owner_conn):
    """Db2 side of the differential harness, with the base fixture loaded."""
    from src.corpus import BASE
    from src.counterexample import Db2Target, ensure_fixture_schema

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    target.load(BASE)
    return target
