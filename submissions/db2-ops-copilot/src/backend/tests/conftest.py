"""Shared fixtures — every test runs fully offline against mock adapters."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def pytest_collection_modifyitems(config, items):
    """Enforce the ``integration`` marker contract (see pyproject.toml).

    Real-service integration tests are opt-in: they are skipped unless
    ``ADAPTER_MODE=real`` AND ``RUN_REAL_INTEGRATION=1``. This keeps an
    offline run green without ever reporting a skipped/absent service as a
    passing integration.
    """
    enabled = (
        os.environ.get("ADAPTER_MODE") == "real"
        and os.environ.get("RUN_REAL_INTEGRATION") == "1"
    )
    if enabled:
        return
    skip_integration = pytest.mark.skip(
        reason=(
            "integration tests are opt-in: set ADAPTER_MODE=real and "
            "RUN_REAL_INTEGRATION=1 to enable"
        )
    )
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip_integration)


@pytest.fixture()
def app():
    """Fresh app instance with mock mode and a cleared settings cache."""
    get_settings.cache_clear()
    application = create_app()
    yield application
    application.state.registry.close_all()
    get_settings.cache_clear()


@pytest.fixture()
def client(app) -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
