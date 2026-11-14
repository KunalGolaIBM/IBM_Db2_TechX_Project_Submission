"""Test fixtures. FakeRepo mirrors Db2Repository in memory (test-only; the app itself always uses Db2)."""
import sys
from pathlib import Path

import os

import pytest

for _k in ("GEMINI_API_KEY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
    os.environ[_k] = ""  # tests never call external services
os.environ["EMBED_PROVIDER"] = "local"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from embeddings import LocalHashEmbedder  # noqa: E402


from adapters.memory import MemoryRepository as FakeRepo  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--db2", action="store_true", help="Run opt-in tests against real Db2")


def pytest_configure(config):
    if config.getoption("--db2"):
        os.environ["PAYGUARD_DB2_TEST"] = "1"


@pytest.fixture(scope="session")
def embedder():
    return LocalHashEmbedder(768)


@pytest.fixture()
def repo(embedder):
    return FakeRepo(embedder)


@pytest.fixture()
def client(repo, embedder, monkeypatch):
    import api.security
    import main
    from fastapi.testclient import TestClient
    from test_api import FakePayPal
    monkeypatch.setitem(main.app.state._state, "limiter", api.security.PerIPRateLimiter(1000))
    monkeypatch.setattr(api.security, "settings", api.security.settings.model_copy(
        update={"platform_api_key": "test-platform-key"}))
    svc = main.Services(repo, embedder, FakePayPal())
    main.app.dependency_overrides[main.get_services] = lambda: svc
    yield TestClient(main.app, headers={"X-API-Key": "test-platform-key"}), svc
    main.app.dependency_overrides.clear()


