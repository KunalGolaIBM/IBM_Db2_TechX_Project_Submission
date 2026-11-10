"""Tests for config loader and safety guard."""

import pytest

from parity.config import DatabaseSettings, load_settings
from parity.engine.safety import assert_read_only


def test_load_settings_defaults(monkeypatch):
    monkeypatch.delenv("PARITY_SOURCE_USER", raising=False)
    monkeypatch.delenv("PARITY_SOURCE_PASSWORD", raising=False)
    monkeypatch.delenv("PARITY_SOURCE_DB", raising=False)
    source, db2 = load_settings()
    assert source.host == "localhost"
    assert source.port == 5432
    assert source.user == ""
    assert db2.port == 50000


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("PARITY_SOURCE_USER", "alice")
    monkeypatch.setenv("PARITY_DB2_DB", "parity")
    source, db2 = load_settings()
    assert source.user == "alice"
    assert db2.database == "parity"


def test_incomplete_settings_rejected():
    settings = DatabaseSettings(host="localhost", port=5432, user="", password="", database="")
    with pytest.raises(ValueError, match="missing"):
        settings.require_complete("PostgreSQL")


def test_select_allowed():
    assert_read_only("SELECT 1")
    assert_read_only("  select id from t")


def test_with_select_allowed():
    assert_read_only("WITH x AS (SELECT 1) SELECT * FROM x")


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "CREATE TABLE t (a INT)",
        "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x",
        "",
    ],
)
def test_write_sql_blocked(sql):
    with pytest.raises(ValueError):
        assert_read_only(sql)
