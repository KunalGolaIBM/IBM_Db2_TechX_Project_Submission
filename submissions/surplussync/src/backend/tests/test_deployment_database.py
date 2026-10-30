"""Deployment database selection must never fall back to ephemeral SQLite."""
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from backend import database
from backend.seed_presentation_demo import enabled


def clear_remote_settings(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)


def test_vercel_requires_configured_persistent_database(monkeypatch):
    clear_remote_settings(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    with pytest.raises(RuntimeError, match="persistent Turso database"):
        with database.connection():
            pytest.fail("must not create a temporary local database on Vercel")


def test_remote_database_requires_both_private_settings(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.invalid")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)

    with pytest.raises(RuntimeError, match="Both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN"):
        with database.connection():
            pytest.fail("partial remote configuration must fail closed")


def test_remote_connection_uses_serverless_driver_without_local_file(monkeypatch, tmp_path):
    class FakeConnection:
        def __init__(self):
            self.statements = []
            self.committed = False
            self.closed = False
            self.row_factory = None

        def execute(self, sql):
            self.statements.append(sql)

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("successful transaction should not roll back")

        def close(self):
            self.closed = True

    remote = FakeConnection()
    row_factory = object()
    connect_calls = []

    def connect(url, *, auth_token):
        connect_calls.append((url, auth_token))
        return remote

    driver = SimpleNamespace(connect=connect, Row=row_factory)
    monkeypatch.setitem(sys.modules, "turso_serverless", driver)
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.invalid")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "test-only-token")
    monkeypatch.setenv("VERCEL", "1")
    local_db = tmp_path / "must-not-be-created.db"
    monkeypatch.setattr(database, "DB_PATH", local_db)

    with database.connection(immediate=True) as db:
        assert db is remote
        assert db.row_factory is row_factory

    assert connect_calls == [("libsql://example.invalid", "test-only-token")]
    assert remote.statements == ["PRAGMA foreign_keys=ON", "BEGIN IMMEDIATE"]
    assert remote.committed and remote.closed
    assert not local_db.exists()


def test_presentation_seed_is_opt_in_and_render_image_contains_its_entrypoint(monkeypatch):
    monkeypatch.delenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED", raising=False)
    assert not enabled()
    monkeypatch.setenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED", "false")
    assert not enabled()
    monkeypatch.setenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED", "true")
    assert enabled()

    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    blueprint = (root / "render.yaml").read_text(encoding="utf-8")
    assert "backend/seed_presentation_demo.py" in dockerfile
    assert "backend/seed_demo_workflows.py" in dockerfile
    assert "SURPLUSSYNC_PRESENTATION_DEMO_ENABLED" in blueprint
    assert 'value: "false"' in blueprint
    assert "mountPath: /var/data" in blueprint
    assert "--port ${PORT:-10000}" in dockerfile
