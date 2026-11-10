
import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.db import DatabaseUnavailable
from backend.main import app
from backend.repositories import Repository


def test_profile_validation():
    with TestClient(app) as client:
        response = client.post(
            "/players/profile",
            json={
                "player_id": "",
                "display_name": "A",
                "email": "a@b.test",
            },
        )

    assert response.status_code == 422


def test_health_explicit_offline_without_db():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code in {200, 503}
    assert set(response.json()) == {"status", "database", "ai_mode"}
    assert response.json()["database"] in {"connected", "unavailable"}


class HealthyDb:
    connection = object()

    def __init__(self):
        self.queries = []

    def execute(self, sql):
        self.queries.append(sql)
        return [{"1": 1}]




class FailedDb:
    connection = object()

    def connect(self):
        raise DatabaseUnavailable("Db2 connection failed")

    def close(self):
        pass

    def execute(self, sql):
        raise DatabaseUnavailable("Db2 query failed")

    def execute_insert_and_get_identity(self, sql, params=()):
        raise DatabaseUnavailable("Db2 insert failed")



def test_health_reports_healthy_db_without_reconnecting(monkeypatch):
    database = HealthyDb()
    monkeypatch.setattr(main_module, "db", database)

    response = main_module.health()

    assert response == {
        "status": "ok",
        "database": "connected",
        "ai_mode": main_module.assistant.mode,
    }
    assert database.queries == ["SELECT 1 FROM SYSIBM.SYSDUMMY1"]


def test_health_reports_missing_connection(monkeypatch):
    database = HealthyDb()
    database.connection = None
    monkeypatch.setattr(main_module, "db", database)

    response = main_module.health()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "offline",
        "database": "unavailable",
        "ai_mode": main_module.assistant.mode,
    }
    assert database.queries == []


def test_health_reports_failed_connectivity_check(monkeypatch):
    database = FailedDb()
    monkeypatch.setattr(main_module, "db", database)

    response = main_module.health()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "offline",
        "database": "unavailable",
        "ai_mode": main_module.assistant.mode,
    }


def test_write_returns_offline_when_db2_is_unavailable(monkeypatch):
    database = FailedDb()
    monkeypatch.setattr(main_module, "db", database)
    monkeypatch.setattr(main_module, "repo", Repository(database))

    with TestClient(app) as client:
        response = client.post(
            "/game/sessions",
            json={"player_id": "player-1"},
        )

    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "offline"
