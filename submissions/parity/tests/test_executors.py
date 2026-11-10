"""Tests for executors using mocks. No live database needed."""

import sys
import types

import pytest

from parity.config import DatabaseSettings
from parity.engine.db2 import Db2Executor, _connection_string
from parity.engine.postgres import PostgresExecutor


def full_settings():
    return DatabaseSettings(host="localhost", port=1234, user="u", password="p", database="d")


def test_db2_connection_string():
    text = _connection_string(full_settings())
    assert "DATABASE=d" in text
    assert "HOSTNAME=localhost" in text
    assert "PORT=1234" in text


def test_executors_reject_bad_row_limit():
    with pytest.raises(ValueError):
        PostgresExecutor(full_settings(), row_limit=0)
    with pytest.raises(ValueError):
        Db2Executor(full_settings(), row_limit=0)


def test_executors_reject_incomplete_settings():
    bad = DatabaseSettings()
    with pytest.raises(ValueError):
        PostgresExecutor(bad)
    with pytest.raises(ValueError):
        Db2Executor(bad)


def test_postgres_executor_blocks_write(monkeypatch):
    calls = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            calls.append(sql)

        @property
        def description(self):
            return []

        def fetchmany(self, n):
            return []

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return FakeCursor()

    fake = types.ModuleType("psycopg")
    fake.connect = lambda *a, **k: FakeConn()
    monkeypatch.setitem(sys.modules, "psycopg", fake)
    executor = PostgresExecutor(full_settings())
    with pytest.raises(ValueError, match="only SELECT"):
        executor.execute("DELETE FROM t")
    assert calls == []


def test_postgres_executor_returns_result(monkeypatch):
    class Col:
        name = "id"

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            self.sql = sql

        @property
        def description(self):
            return [Col()]

        def fetchmany(self, n):
            return [(1,), (2,)]

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return FakeCursor()

    fake = types.ModuleType("psycopg")
    fake.connect = lambda *a, **k: FakeConn()
    monkeypatch.setitem(sys.modules, "psycopg", fake)
    result = PostgresExecutor(full_settings()).execute("SELECT id FROM t")
    assert result.columns == ("id",)
    assert result.rows == ((1,), (2,))
