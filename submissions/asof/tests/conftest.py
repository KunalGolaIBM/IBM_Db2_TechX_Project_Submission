"""Shared fixtures. Db2 tests run against a throwaway ASOF_TEST schema and skip when Db2 is down."""

from __future__ import annotations

import os

# FastAPI's TestClient sends Host: testserver; the app answers only to listed hosts.
os.environ.setdefault("ASOF_ALLOWED_HOSTS", "127.0.0.1,localhost,::1,testserver")
# Tests never write to the real chain-head anchor log (var/anchors): anchors go to a throwaway directory.
import tempfile  # noqa: E402

os.environ["ASOF_ANCHOR_DIR"] = tempfile.mkdtemp(prefix="asof-test-anchors-")
# ... and never read the real anchor key: tests that need one make their own.
os.environ["ASOF_ANCHOR_KEY_FILE"] = os.path.join(os.environ["ASOF_ANCHOR_DIR"], "no-such-anchor.key")
os.environ.pop("ASOF_ANCHOR_KEY", None)

import pytest

from asof import db, schema, seed
from asof.config import ConfigError, Settings
from asof.embeddings import get_embeddings

TEST_SCHEMA = "ASOF_TEST"


def pytest_collection_modifyitems(config, items):
    """Tests that call paid or remote services run only when asked:
    ASOF_RUN_LLM_TESTS=1 pytest -m llm, ASOF_RUN_NETWORK_TESTS=1 pytest -m network, and the slow backup drill with
    ASOF_RUN_BACKUP_TESTS=1 pytest -m backup."""
    import os

    gates = {"llm": ("ASOF_RUN_LLM_TESTS", "calls a real LLM"),
             "network": ("ASOF_RUN_NETWORK_TESTS", "Db2 calls a remote embedding endpoint"),
             "backup": ("ASOF_RUN_BACKUP_TESTS", "creates and drops two Db2 databases (minutes)")}
    for marker, (env, why) in gates.items():
        if os.environ.get(env) == "1":
            continue
        skip = pytest.mark.skip(reason=f"{why}; set {env}=1 to run")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def admin_conn(settings):
    try:
        conn = db.connect(settings, "admin")
    except (ConfigError, db.DatabaseError) as exc:
        pytest.skip(f"Db2 not available for integration tests: {exc}")
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def embeddings(settings):
    return get_embeddings(settings.embedding_model)


@pytest.fixture(scope="session")
def test_schema(admin_conn, embeddings, settings):
    """Install, seed and grant a fresh ASOF_TEST schema; drop it after the session."""
    schema.drop(admin_conn, TEST_SCHEMA)
    schema.install(admin_conn, TEST_SCHEMA)
    seed.seed_policy(admin_conn, embeddings, TEST_SCHEMA)
    seed.seed_chain_head(admin_conn, TEST_SCHEMA)
    seed.seed_published_answers(admin_conn, TEST_SCHEMA)
    seed.seed_faq(admin_conn, embeddings, TEST_SCHEMA)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, TEST_SCHEMA)
    yield TEST_SCHEMA
    schema.drop(admin_conn, TEST_SCHEMA)


@pytest.fixture
def app_conn(settings, test_schema):
    """A connection as the least-privilege runtime user (skips if that user cannot log in)."""
    try:
        conn = db.connect(settings, "app")
    except (ConfigError, db.DatabaseError) as exc:
        pytest.skip(f"app user cannot connect (run python -m asof.setup first): {exc}")
    yield conn
    conn.rollback()
    conn.close()
