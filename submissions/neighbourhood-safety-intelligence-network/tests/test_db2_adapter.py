"""Native ibm_db access, connection handling and configuration. Real IBM Db2, no mocks."""
import importlib
import os

import pytest

from backend.app.core import config as config_module
from backend.app.database.db2_adapter import Db2Adapter


def test_health_probe_reads_server_details():
    info = Db2Adapter().test_connection()
    assert info["connected"] is True
    assert info["server_version"].startswith("DB2/") and info["current_schema"]


def test_wrong_password_is_reported_not_raised():
    adapter = Db2Adapter()
    adapter.password = "definitely-wrong-password"
    info = adapter.test_connection()
    assert info["connected"] is False and "SQL30082N" in info["error"]


def test_missing_host_is_reported():
    adapter = Db2Adapter()
    adapter.host = ""
    assert Db2Adapter.test_connection(adapter)["connected"] is False


def test_prepared_select_and_transactional_write():
    db2 = Db2Adapter()
    rows = db2.execute_query("SELECT COUNT(*) AS N FROM users WHERE role = ?", ("resident",))
    assert rows[0]["N"] >= 3
    inserted = db2.execute_non_query(
        'INSERT INTO audit_events (action, resource_type, resource_id, "timestamp") VALUES (?, ?, ?, CURRENT TIMESTAMP)',
        ("adapter_test", "test", "native-ibm-db"))
    assert inserted == 1
    assert db2.execute_non_query("DELETE FROM audit_events WHERE action = ?", ("adapter_test",)) == 1


def test_failed_write_rolls_back():
    db2 = Db2Adapter()
    with pytest.raises(Exception):
        db2.execute_non_query("INSERT INTO audit_events (action) VALUES (?)", (None,))  # NOT NULL violation
    assert db2.execute_query("SELECT COUNT(*) AS N FROM audit_events WHERE action IS NULL")[0]["N"] == 0


def test_sqlalchemy_url_escapes_credentials_and_adds_options():
    db2 = Db2Adapter()
    db2.password, db2.security, db2.schema = "p@ss:w/rd?", "SSL", "DB2INST1"
    url = db2.sqlalchemy_url()
    assert url.password == "p@ss:w/rd?" and url.query["Security"] == "SSL" and url.query["CurrentSchema"] == "DB2INST1"
    assert "SECURITY=SSL" in db2.build_connection_string() and "CURRENTSCHEMA=DB2INST1" in db2.build_connection_string()


def _reload_settings(env: dict):
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update({k: v for k, v in env.items() if v is not None})
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
    try:
        return importlib.reload(config_module).settings
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(config_module)


def test_vs_code_extension_variable_names_are_accepted():
    s = _reload_settings({"DB2_DATABASE": None, "DB2_NAME": "TESTDB", "DB2_USER": None, "DB2_USERNAME": "db2inst1",
                          "DB2_SECURITY": None, "DB2_SSL": "true"})
    assert (s.DB2_DATABASE, s.DB2_USER, s.DB2_SECURITY) == ("TESTDB", "db2inst1", "SSL")


def test_production_refuses_development_secrets():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _reload_settings({"APP_ENV": "production", "JWT_SECRET": None})
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _reload_settings({"APP_ENV": "production", "JWT_SECRET": "x" * 40, "CORS_ORIGINS": "*"})
