"""Tests for the bridge retry and error message."""

import json
import subprocess

import pytest

from parity.config import DatabaseSettings
from parity.engine.db2_bridge import Db2BridgeExecutor


def settings():
    return DatabaseSettings(
        host="host.docker.internal", port=50000, user="u", password="p", database="d"
    )


def failing_run(message="docker daemon is busy"):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            args=command, returncode=125, stdout="", stderr=message
        )

    return fake_run


def test_bridge_error_keeps_the_reason(monkeypatch):
    executor = Db2BridgeExecutor(settings())
    monkeypatch.setattr(executor, "_run", lambda sql, timeout: (_ for _ in ()).throw(
        RuntimeError("bridge failed (exit 125): docker daemon is busy")
    ))
    with pytest.raises(RuntimeError, match="docker daemon is busy"):
        executor.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")


def test_bridge_retries_a_container_start_failure(monkeypatch):
    executor = Db2BridgeExecutor(settings())
    calls = []

    def fake_run(sql, timeout):
        calls.append(sql)
        if len(calls) == 1:
            raise RuntimeError("bridge failed (exit 125): cannot start container")
        return json.dumps({"columns": ["A"], "types": ["int"], "rows": [[1]]})

    monkeypatch.setattr(executor, "_run", fake_run)
    monkeypatch.setattr("parity.engine.db2_bridge.time.sleep", lambda seconds: None)
    result = executor.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
    assert result.columns == ("A",)
    assert len(calls) == 2


def test_bridge_gives_up_after_attempts(monkeypatch):
    executor = Db2BridgeExecutor(settings())
    calls = []

    def fake_run(sql, timeout):
        calls.append(sql)
        raise RuntimeError("bridge failed (exit 125): cannot start container")

    monkeypatch.setattr(executor, "_run", fake_run)
    monkeypatch.setattr("parity.engine.db2_bridge.time.sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="cannot start container"):
        executor.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
    assert len(calls) == 2


def test_bridge_does_not_retry_a_sql_error(monkeypatch):
    """A SQL error comes back in the payload, so it is not a start failure."""
    executor = Db2BridgeExecutor(settings())
    calls = []

    def fake_run(sql, timeout):
        calls.append(sql)
        return json.dumps({"error": "SQL0104N syntax error"})

    monkeypatch.setattr(executor, "_run", fake_run)
    with pytest.raises(RuntimeError, match="SQL0104N"):
        executor.execute("SELECT bad FROM SYSIBM.SYSDUMMY1")
    assert len(calls) == 1
