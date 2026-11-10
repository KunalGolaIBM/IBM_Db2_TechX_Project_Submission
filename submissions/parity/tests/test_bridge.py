"""Tests for the Db2 bridge executor using mocks."""

import json
import subprocess

import pytest

from parity.bridge_client import encode_value
from parity.config import DatabaseSettings
from parity.engine.db2_bridge import Db2BridgeExecutor


def full_settings():
    return DatabaseSettings(host="host.docker.internal", port=50000, user="u", password="p", database="d")


def fake_run_factory(stdout_text, returncode=0):
    def fake_run(command, **kwargs):
        assert kwargs["input"] == "SELECT 1"
        return subprocess.CompletedProcess(
            args=command, returncode=returncode, stdout=stdout_text, stderr=""
        )

    return fake_run


def test_encode_value():
    assert encode_value(None) is None
    assert encode_value(5) == 5
    assert encode_value("x") == "x"
    assert encode_value(object()) is not None


def test_bridge_executor_parses_result(monkeypatch):
    payload = json.dumps({"columns": ["ID"], "rows": [[1], [2]]})
    monkeypatch.setattr(subprocess, "run", fake_run_factory(payload))
    result = Db2BridgeExecutor(full_settings()).execute("SELECT 1")
    assert result.columns == ("ID",)
    assert result.rows == ((1,), (2,))


def test_bridge_executor_blocks_write():
    with pytest.raises(ValueError, match="only SELECT"):
        Db2BridgeExecutor(full_settings()).execute("DELETE FROM t")


def test_bridge_executor_error_payload(monkeypatch):
    payload = json.dumps({"error": "boom"})
    monkeypatch.setattr(subprocess, "run", fake_run_factory(payload))
    with pytest.raises(RuntimeError, match="bridge error"):
        Db2BridgeExecutor(full_settings()).execute("SELECT 1")


def test_bridge_executor_bad_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run_factory("", returncode=2))
    with pytest.raises(RuntimeError, match="bridge failed"):
        Db2BridgeExecutor(full_settings()).execute("SELECT 1")


def test_bridge_executor_bad_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run_factory("not json"))
    with pytest.raises(RuntimeError, match="bad JSON"):
        Db2BridgeExecutor(full_settings()).execute("SELECT 1")


def test_bridge_executor_row_limit(monkeypatch):
    payload = json.dumps({"columns": ["ID"], "rows": [[1], [2], [3]]})
    monkeypatch.setattr(subprocess, "run", fake_run_factory(payload))
    with pytest.raises(ValueError, match="row limit"):
        Db2BridgeExecutor(full_settings(), row_limit=2).execute("SELECT 1")
