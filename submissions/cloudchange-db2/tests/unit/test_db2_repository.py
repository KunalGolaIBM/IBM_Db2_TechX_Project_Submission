"""Unit tests for Db2RunRepository and Dependency Injection."""

import os
from unittest import mock
import pytest
from fastapi.testclient import TestClient

from backend.app.db2.adapter import Db2PersistenceAdapter
from backend.app.models.run import Run
from backend.app.repositories.db2_repo import Db2RunRepository, get_db2_run_repository
from backend.app.repositories.run_repo import RunRepository, get_run_repository
from backend.app.main import app


def test_db2_run_repository_delegation():
    """Verify Db2RunRepository delegates calls to the adapter."""
    mock_adapter = mock.MagicMock(spec=Db2PersistenceAdapter)
    mock_run = mock.MagicMock(spec=Run)
    mock_run.run_id = "test-123"

    mock_adapter.save_run.return_value = mock_run
    mock_adapter.get_run.return_value = mock_run
    mock_adapter.list_runs.return_value = [mock_run]
    mock_adapter.count_runs.return_value = 5

    repo = Db2RunRepository(adapter=mock_adapter)

    assert repo.save(mock_run) == mock_run
    mock_adapter.save_run.assert_called_once_with(mock_run)

    assert repo.get("test-123") == mock_run
    mock_adapter.get_run.assert_called_once_with("test-123")

    assert repo.list_all() == [mock_run]
    mock_adapter.list_runs.assert_called_once()

    assert repo.count() == 5
    mock_adapter.count_runs.assert_called_once()

    repo.clear()
    mock_adapter.clear.assert_called_once()


def test_get_run_repository_provider_routing():
    """Verify get_run_repository switches between memory and db2."""
    from backend.app import config

    # When DATABASE_BACKEND is memory
    with mock.patch.object(config.settings, "DATABASE_BACKEND", "memory"):
        repo = get_run_repository()
        assert isinstance(repo, RunRepository)
        assert not isinstance(repo, Db2RunRepository)

    # When DATABASE_BACKEND is db2
    with mock.patch.object(config.settings, "DATABASE_BACKEND", "db2"):
        repo = get_run_repository()
        assert isinstance(repo, Db2RunRepository)


def test_api_routes_with_db2_repo_mocked():
    """Verify API endpoints function when dependency is overridden with Db2RunRepository."""
    mock_adapter = mock.MagicMock(spec=Db2PersistenceAdapter)
    mock_adapter.get_audit_history.return_value = [
        {"event_id": "ev-1", "event_type": "RUN_CREATED", "recorded_at": "2026-10-31T12:00:00Z"}
    ]
    mock_adapter.get_high_risk_changes.return_value = []
    mock_adapter.get_verification_metrics.return_value = {"total": 0, "by_status": {}}

    db2_repo = Db2RunRepository(adapter=mock_adapter)

    # Put a dummy run
    mock_run = mock.MagicMock()
    mock_run.run_id = "run-audit-test"
    mock_adapter.get_run.return_value = mock_run

    app.dependency_overrides[get_run_repository] = lambda: db2_repo
    client = TestClient(app)

    try:
        # Test audit endpoint
        resp = client.get("/api/v1/runs/run-audit-test/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run-audit-test"
        assert len(data["audit_events"]) == 1

        # Test governance summary endpoint
        resp = client.get("/api/v1/runs/governance/summary")
        assert resp.status_code == 200
        summary = resp.json()
        assert "high_risk_changes" in summary
        assert "verification_metrics" in summary

        # Test Db2 health check endpoint
        resp = client.get("/health/db2")
        assert resp.status_code == 200
        health = resp.json()
        assert health["backend"] == "ibm_db2"
    finally:
        app.dependency_overrides.clear()
