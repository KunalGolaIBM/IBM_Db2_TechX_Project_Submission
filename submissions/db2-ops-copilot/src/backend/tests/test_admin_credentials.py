"""Privileged admin execution path: credential separation and guard order.

Offline tests for ``app.database.dsn`` (``connect_args`` / ``admin_connect_args``
/ ``sanitize``), ``Db2DatabaseAdapter.execute_admin_statement`` and
``MockDatabaseAdapter.execute_admin_statement``.

No real Db2 and no native driver: ``ibm_db_dbi``/``ibm_db`` are always replaced
with fakes before any import can happen, and every guard is asserted to fire
BEFORE a connection is attempted (``ctl.calls == []``).
"""

from __future__ import annotations

import sys
import types
import uuid

import pytest
from fastapi.testclient import TestClient

from app.adapters.db.db2_db import Db2DatabaseAdapter
from app.adapters.db.mock_db import MockDatabaseAdapter
from app.core.config import Settings, get_settings
from app.core.errors import AppError, AdapterUnavailableError, DbSqlError
from app.database.dsn import admin_connect_args, build_dsn, connect_args, sanitize
from app.main import create_app
from db2_fakes import FakeConnection

# ===================================================================================
# Recording fake driver — captures every (dsn, user, password) connect call
# ===================================================================================
def install_recording_dbi(monkeypatch, script=None):
    """Install a fake ``ibm_db_dbi`` that records connect arguments."""
    ctl = types.SimpleNamespace(
        script=list(script or []),
        calls=[],  # list[(dsn, user, password)]
        connections=[],
        connect_error=None,
    )

    def connect(dsn, user, password):
        ctl.calls.append((dsn, user, password))
        if ctl.connect_error:
            raise ctl.connect_error
        conn = FakeConnection(ctl.script)
        ctl.connections.append(conn)
        return conn

    module = types.ModuleType("ibm_db_dbi")
    module.connect = connect
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", module)
    monkeypatch.setitem(sys.modules, "ibm_db", types.ModuleType("ibm_db"))
    return ctl


def admin_settings(**overrides) -> Settings:
    base = dict(
        _env_file=None,
        adapter_mode="real",
        db2_ro_password="ro-" + uuid.uuid4().hex,
        db2_admin_user="db2_admin",
        db2_admin_password="admin-" + uuid.uuid4().hex,
        agent_actions_enabled=True,
        sql_max_rows=3,
    )
    base.update(overrides)
    return Settings(**base)


_STMT = "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE APP.DEMO_SERVERS WITH DISTRIBUTION')"


# ===================================================================================
# 1–2. connect_args / admin_connect_args separation
# ===================================================================================
def test_connect_args_returns_read_only_credentials_only():
    settings = admin_settings(db2_ro_user="db2ro")

    dsn, user, password = connect_args(settings)

    assert user == "db2ro"
    assert password == settings.db2_ro_password.get_secret_value()
    assert password != settings.db2_admin_password.get_secret_value()
    assert settings.db2_admin_user not in (user, password)
    # The DSN itself never carries credentials of either account.
    assert dsn == build_dsn(settings)
    assert password not in dsn
    assert settings.db2_admin_password.get_secret_value() not in dsn
    assert "uid=" not in dsn.lower() and "pwd=" not in dsn.lower()


def test_admin_connect_args_returns_privileged_credentials_only():
    settings = admin_settings(db2_ro_user="db2ro")

    dsn, user, password = admin_connect_args(settings)

    assert user == "db2_admin"
    assert password == settings.db2_admin_password.get_secret_value()
    assert password != settings.db2_ro_password.get_secret_value()
    assert settings.db2_ro_user not in (user, password)
    assert settings.db2_ro_password.get_secret_value() not in dsn
    # both accounts share the same credential-free DSN
    assert dsn == build_dsn(settings)


# ===================================================================================
# 3. The read-only path never receives admin credentials
# ===================================================================================
def test_readonly_connection_path_never_receives_admin_credentials(monkeypatch):
    ctl = install_recording_dbi(
        monkeypatch,
        script=[("SELECT", {"columns": ["TABNAME"], "rows": [("DEMO_SERVERS",)]})],
    )
    settings = admin_settings()
    adapter = Db2DatabaseAdapter(settings)

    result = adapter.execute_readonly("SELECT TABNAME FROM APP.TABLES")

    assert result.rows
    assert ctl.calls, "the read-only path must connect"
    for dsn, user, password in ctl.calls:
        assert user == settings.db2_ro_user
        assert password == settings.db2_ro_password.get_secret_value()
        assert user != settings.db2_admin_user
        assert password != settings.db2_admin_password.get_secret_value()
    # the admin password never appears anywhere in the connect arguments
    assert all(settings.db2_admin_password.get_secret_value() not in a
               for call in ctl.calls for a in call)


# ===================================================================================
# 4. sanitize() strips both passwords
# ===================================================================================
def test_sanitize_removes_read_only_and_admin_passwords():
    settings = admin_settings()
    ro = settings.db2_ro_password.get_secret_value()
    admin = settings.db2_admin_password.get_secret_value()

    message = (
        f"connection refused for uid=db2ro password={ro} "
        f"and maintenance account password={admin}"
    )
    cleaned = sanitize(message, settings)

    assert ro not in cleaned
    assert admin not in cleaned
    assert cleaned.count("***") >= 2
    # empty secrets must not cause spurious replacements
    no_secrets = Settings(_env_file=None, db2_ro_password="", db2_admin_password="")
    assert sanitize("password=   nothing here", no_secrets).startswith("password=")
    # bounded output
    assert len(sanitize("x" * 5000, no_secrets)) <= 300


# ===================================================================================
# 5–6. Guard order: disabled / unconfigured never connect
# ===================================================================================
def test_admin_execution_refuses_when_actions_disabled(monkeypatch):
    ctl = install_recording_dbi(monkeypatch)
    settings = admin_settings(agent_actions_enabled=False)
    adapter = Db2DatabaseAdapter(settings)

    with pytest.raises(AdapterUnavailableError) as excinfo:
        adapter.execute_admin_statement(_STMT)

    assert excinfo.value.detail == {"code": "ACTIONS_DISABLED"}
    assert ctl.calls == []  # refused before any connect / driver import


def test_admin_execution_refuses_without_admin_credentials(monkeypatch):
    ctl = install_recording_dbi(monkeypatch)
    settings = admin_settings(db2_admin_user="", db2_admin_password="")
    adapter = Db2DatabaseAdapter(settings)

    with pytest.raises(AdapterUnavailableError) as excinfo:
        adapter.execute_admin_statement(_STMT)

    assert excinfo.value.detail == {"code": "ADMIN_NOT_CONFIGURED"}
    assert ctl.calls == []

    # half-configured (user without password) is also refused
    half = admin_settings(db2_admin_user="db2_admin", db2_admin_password="")
    with pytest.raises(AdapterUnavailableError) as excinfo2:
        Db2DatabaseAdapter(half).execute_admin_statement(_STMT)
    assert excinfo2.value.detail == {"code": "ADMIN_NOT_CONFIGURED"}
    assert ctl.calls == []


# ===================================================================================
# 7. Exactly one statement
# ===================================================================================
def test_multiple_sql_statements_are_rejected(monkeypatch):
    ctl = install_recording_dbi(monkeypatch)
    settings = admin_settings()
    adapter = Db2DatabaseAdapter(settings)

    with pytest.raises(DbSqlError):
        adapter.execute_admin_statement(_STMT + "; DROP TABLE APP.DEMO_SERVERS")
    with pytest.raises(DbSqlError):
        adapter.execute_admin_statement("   ")

    assert ctl.calls == []  # refused before connecting


# ===================================================================================
# 8. Privileged connect args are used only after every safeguard passes
# ===================================================================================
def test_admin_execution_uses_privileged_connect_args_after_safeguards(monkeypatch):
    ctl = install_recording_dbi(monkeypatch)
    settings = admin_settings()
    adapter = Db2DatabaseAdapter(settings)

    result = adapter.execute_admin_statement(_STMT)

    assert result.status == "EXECUTED"
    assert result.simulated is False

    # exactly one connect, with the ADMIN account — never the read-only one
    assert len(ctl.calls) == 1
    dsn, user, password = ctl.calls[0]
    assert user == settings.db2_admin_user
    assert password == settings.db2_admin_password.get_secret_value()
    assert user != settings.db2_ro_user
    assert password != settings.db2_ro_password.get_secret_value()
    assert dsn == build_dsn(settings)
    assert password not in dsn

    # committed and closed
    conn = ctl.connections[0]
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert conn.closed is True
    assert _STMT in conn.statements()


def test_failed_admin_execution_rolls_back_closes_and_never_leaks(monkeypatch):
    ro_secret = None
    settings = admin_settings()
    ro_secret = settings.db2_ro_password.get_secret_value()
    admin_secret = settings.db2_admin_password.get_secret_value()
    ctl = install_recording_dbi(
        monkeypatch,
        script=[("RUNSTATS", RuntimeError(f"SQLERRD password={ro_secret}"))],
    )
    adapter = Db2DatabaseAdapter(settings)

    with pytest.raises(AppError) as excinfo:
        adapter.execute_admin_statement(_STMT)

    blob = str(excinfo.value)
    assert ro_secret not in blob
    assert admin_secret not in blob

    conn = ctl.connections[0]
    assert conn.rollbacks == 1
    assert conn.commits == 0
    assert conn.closed is True


def test_admin_execution_on_closed_adapter_refuses(monkeypatch):
    ctl = install_recording_dbi(monkeypatch)
    settings = admin_settings()
    adapter = Db2DatabaseAdapter(settings)
    adapter.close()

    with pytest.raises(AdapterUnavailableError):
        adapter.execute_admin_statement(_STMT)
    assert ctl.calls == []


# ===================================================================================
# 9. Mock adapter: same contract, but simulated only
# ===================================================================================
def test_mock_adapter_admin_execution_is_simulation_only():
    settings = Settings(_env_file=None)  # mock mode, no admin credentials at all
    adapter = MockDatabaseAdapter(settings)

    result = adapter.execute_admin_statement(_STMT)

    assert result.status == "SIMULATED"
    assert result.simulated is True
    assert "not executed" in result.detail
    # the statement is recorded for review, and nothing else happens
    assert adapter.simulated_admin_statements == [_STMT]

    # repeated calls just accumulate the record
    adapter.execute_admin_statement("SELECT 1 FROM SYSIBM.SYSDUMMY1")
    assert adapter.simulated_admin_statements == [_STMT, "SELECT 1 FROM SYSIBM.SYSDUMMY1"]

    # a closed mock adapter refuses rather than silently simulating
    adapter.close()
    with pytest.raises(RuntimeError):
        adapter.execute_admin_statement(_STMT)


# ===================================================================================
# 10. Secrets stay SecretStr and never reach serialization / public config
# ===================================================================================
def test_admin_password_is_secret_str_and_never_serialized():
    admin_pw = "admin-" + uuid.uuid4().hex
    settings = Settings(
        _env_file=None,
        db2_admin_user="db2_admin",
        db2_admin_password=admin_pw,
    )

    assert settings.db2_admin_password.__class__.__name__ == "SecretStr"
    assert settings.db2_admin_password.get_secret_value() == admin_pw
    assert admin_pw not in settings.model_dump_json()
    assert admin_pw not in str(settings.model_dump(mode="json"))
    assert admin_pw not in str(settings.model_dump())
    # the SecretStr object (not the raw string) survives a JSON dump round trip
    dumped = settings.model_dump(mode="json")
    assert dumped["db2_admin_password"] != admin_pw


def test_config_endpoint_never_leaks_admin_secrets(monkeypatch):
    admin_pw = "admin-" + uuid.uuid4().hex
    monkeypatch.setenv("DB2_ADMIN_USER", "db2_admin")
    monkeypatch.setenv("DB2_ADMIN_PASSWORD", admin_pw)
    get_settings.cache_clear()
    application = None
    try:
        application = create_app()
        with TestClient(application, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/config")
        assert response.status_code == 200

        body = response.json()
        assert admin_pw not in response.text
        assert "db2_admin" not in response.text
        assert "admin_password" not in response.text
        # the response still exposes the non-secret view it is meant to expose
        assert body["database"]["read_only_user"]
        # the schema has no password field at all
        assert "password" not in response.text.lower()
    finally:
        if application is not None:
            try:
                application.state.registry.close_all()
            except Exception:  # noqa: BLE001 — teardown best-effort
                pass
        get_settings.cache_clear()
