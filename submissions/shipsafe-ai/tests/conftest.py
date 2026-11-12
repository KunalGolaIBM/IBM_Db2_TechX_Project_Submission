"""Shared fixtures. Every test that needs a database uses the REAL IBM Db2 from .env
(TESTDB on :50001 by default) in a dedicated schema, SHIPSAFE_TEST, which is dropped
and recreated once per test session. Tests that need a model use the real Granite
models in Ollama. Nothing is mocked: if Db2 or Ollama is missing, those tests fail
with a message saying what to start.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
TEST_SCHEMA = os.getenv("SHIPSAFE_TEST_SCHEMA", "SHIPSAFE_TEST")

# The schema must be set before shipsafe.config reads the environment in any test module.
os.environ["DB2_SCHEMA"] = TEST_SCHEMA


def _drop_schema(config) -> None:
    """SYSPROC.ADMIN_DROP_SCHEMA removes the schema and everything in it (tables, views, procedures)."""
    import ibm_db

    conn = ibm_db.connect(config.db2.connection_string(), "", "")
    try:
        exists = ibm_db.fetch_tuple(ibm_db.exec_immediate(
            conn, f"SELECT COUNT(*) FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = '{TEST_SCHEMA}'"))[0]
        if exists:
            ibm_db.callproc(conn, "SYSPROC.ADMIN_DROP_SCHEMA", (TEST_SCHEMA, None, "SYSTOOLS", "SHIPSAFE_DROP_ERR"))
            ibm_db.commit(conn)
    finally:
        ibm_db.close(conn)


@pytest.fixture(scope="session")
def config():
    from shipsafe.config import ShipSafeConfig

    cfg = ShipSafeConfig.load()
    cfg.db2.schema = TEST_SCHEMA
    cfg.allowed_roots = [str(FIXTURES)]
    cfg.pip_audit = "off"
    if not cfg.db2.password:
        pytest.fail("DB2_PASSWORD is not set. Point .env at your Db2 instance (see README).")
    return cfg


@pytest.fixture(scope="session")
def db2_schema(config):
    """A fresh SHIPSAFE_TEST schema with every table, view and procedure."""
    try:
        _drop_schema(config)
        from shipsafe.db2 import Db2Repository

        repo = Db2Repository(config.db2)
    except Exception as exc:  # pragma: no cover - environment problem, reported clearly
        pytest.fail(f"IBM Db2 is not reachable at {config.db2.host}:{config.db2.port}/{config.db2.database}: {exc}")
    yield repo
    repo.close()


@pytest.fixture()
def repo(db2_schema, config):
    """A separate live connection per test (same schema)."""
    from shipsafe.db2 import Db2Repository

    r = Db2Repository(config.db2, init_schema=False)
    yield r
    r.rollback()
    r.close()


@pytest.fixture(scope="session")
def granite(config):
    """Fails (does not skip) when Ollama or a Granite model is missing."""
    from shipsafe.llm import ollama_status

    st = ollama_status(config.llm)
    if not st["running"]:
        pytest.fail(f"Ollama is not running at {config.llm.host}. Start it, then rerun.")
    missing = [m for m, ok in ((config.llm.chat_model, st["chat_model_ready"]),
                               (config.llm.embed_model, st["embed_model_ready"])) if not ok]
    if missing:
        pytest.fail(f"Missing Granite model(s): {', '.join(missing)}. Run: ollama pull <model>")
    return config.llm


@pytest.fixture(scope="session")
def services(db2_schema, config, granite):
    from shipsafe.services import ShipSafeServices

    svc = ShipSafeServices(config, workspace_root=str(FIXTURES))
    yield svc
    svc._reset_repository()


@pytest.fixture()
def workspace(tmp_path):
    """A throwaway project folder for tools that write files."""
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return tmp_path
