"""Tests for the bridge admin client."""

import json
import subprocess

import pytest

from parity.config import DatabaseSettings
from parity.sync.bridge_admin import Db2BridgeAdmin


def settings():
    return DatabaseSettings(
        host="host.docker.internal", port=50000, user="u", password="p", database="d"
    )


def fake_run(stdout_text, returncode=0, captured=None):
    def fake_run(command, **kwargs):
        if captured is not None:
            captured.append(kwargs["input"])
        return subprocess.CompletedProcess(
            args=command, returncode=returncode, stdout=stdout_text, stderr=""
        )

    return fake_run


def test_execute_sends_the_statement_and_the_parameters(monkeypatch):
    executor = Db2BridgeAdmin(settings())
    captured: list[str] = []
    monkeypatch.setattr(
        "subprocess.run",
        fake_run(json.dumps({"columns": ["A"], "types": ["int"], "rows": [[1]]}), captured=captured),
    )
    columns, rows = executor.execute("SELECT * FROM t WHERE id = ?", [7])
    assert columns == ["A"]
    assert rows == [(1,)]
    request = json.loads(captured[0])
    assert request["sql"] == "SELECT * FROM t WHERE id = ?"
    assert request["params"] == [7]


def test_execute_never_pastes_a_value_into_the_sql(monkeypatch):
    executor = Db2BridgeAdmin(settings())
    captured: list[str] = []
    monkeypatch.setattr(
        "subprocess.run",
        fake_run(json.dumps({"columns": [], "types": [], "rows": []}), captured=captured),
    )
    executor.execute("INSERT INTO t (name) VALUES (?)", ["'; DROP TABLE t; --"])
    request = json.loads(captured[0])
    assert "DROP TABLE" not in request["sql"]
    assert request["params"] == ["'; DROP TABLE t; --"]


def test_insert_rows_builds_one_statement(monkeypatch):
    executor = Db2BridgeAdmin(settings())
    captured: list[str] = []
    monkeypatch.setattr(
        "subprocess.run",
        fake_run(json.dumps({"columns": [], "types": [], "rows": []}), captured=captured),
    )
    executor.insert_rows("t", ("id", "name"), [(1, "a"), (2, "b")])
    request = json.loads(captured[0])
    assert request["sql"] == 'INSERT INTO "T" ("ID", "NAME") VALUES (?, ?), (?, ?)'
    assert request["params"] == [1, "a", 2, "b"]


def test_insert_rows_marker_count_matches_the_parameters(monkeypatch):
    """One set of markers per row keeps the parameter count right."""
    executor = Db2BridgeAdmin(settings())
    captured: list[str] = []
    monkeypatch.setattr(
        "subprocess.run",
        fake_run(json.dumps({"columns": [], "types": [], "rows": []}), captured=captured),
    )
    executor.insert_rows("t", ("id", "name"), [(1, "a"), (2, "b"), (3, "c")])
    request = json.loads(captured[0])
    assert request["sql"].count("?") == len(request["params"])


def test_insert_rows_with_no_rows_does_nothing(monkeypatch):
    executor = Db2BridgeAdmin(settings())
    monkeypatch.setattr(
        "subprocess.run",
        fake_run("should not run"),
    )
    executor.insert_rows("t", ("id",), [])


def test_error_is_reported(monkeypatch):
    executor = Db2BridgeAdmin(settings())
    monkeypatch.setattr(
        "subprocess.run",
        fake_run(json.dumps({"error": "SQL0104N syntax error"}), returncode=0),
    )
    with pytest.raises(RuntimeError, match="SQL0104N"):
        executor.execute("SELECT bad FROM t")


def test_bad_json_is_reported(monkeypatch):
    executor = Db2BridgeAdmin(settings())
    monkeypatch.setattr("subprocess.run", fake_run("not json"))
    with pytest.raises(RuntimeError, match="bad JSON"):
        executor.execute("SELECT 1 FROM t")
