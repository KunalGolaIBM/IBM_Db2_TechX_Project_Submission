"""Configuration: environment-driven settings, validation, secret handling."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_defaults_are_offline_safe():
    settings = Settings(_env_file=None)
    assert settings.adapter_mode == "mock"
    assert settings.environment == "development"
    assert settings.db2_host == "127.0.0.1"
    assert settings.ollama_llm_model == "granite4.2:3b"
    assert settings.injection_mode == "block"


def test_environment_variables_override_defaults(monkeypatch):
    monkeypatch.setenv("ADAPTER_MODE", "real")
    monkeypatch.setenv("DB2_PORT", "50001")
    monkeypatch.setenv("SQL_MAX_ROWS", "25")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.local, http://b.local")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.adapter_mode == "real"
    assert settings.db2_port == 50001
    assert settings.sql_max_rows == 25
    assert settings.cors_origins_list == ["http://a.local", "http://b.local"]


def test_invalid_environment_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="staging-chaos")


def test_invalid_adapter_mode_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, adapter_mode="half-mock")


def test_invalid_injection_mode_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, injection_mode="maybe")


def test_invalid_log_level_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="LOUD")


def test_invalid_port_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db2_port=99999999)


def test_password_is_secret_str():
    settings = Settings(_env_file=None, db2_ro_password="hunter2-not-in-git")
    # SecretStr never serializes its value.
    assert "hunter2-not-in-git" not in settings.model_dump_json()
    assert settings.db2_ro_password.get_secret_value() == "hunter2-not-in-git"


def test_missing_env_vars_fall_back_to_safe_defaults(monkeypatch):
    for var in (
        "DB2_RO_PASSWORD",
        "DB2_INSTANCE_PASSWORD",
        "ADAPTER_MODE",
        "OLLAMA_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.db2_ro_password.get_secret_value() == ""
    assert settings.adapter_mode == "mock"
    # Mock mode is the safe default: no real connections attempted.
    assert settings.is_mock is True


# -----------------------------------------------------------------------------------
# P0 configuration bounds (agent/approval settings)
# -----------------------------------------------------------------------------------
def test_agent_max_tool_calls_bounds():
    # below the minimum
    with pytest.raises(ValidationError):
        Settings(_env_file=None, agent_max_tool_calls=0)
    # above the maximum
    with pytest.raises(ValidationError):
        Settings(_env_file=None, agent_max_tool_calls=17)
    # both inclusive bounds are accepted
    assert Settings(_env_file=None, agent_max_tool_calls=1).agent_max_tool_calls == 1
    assert Settings(_env_file=None, agent_max_tool_calls=16).agent_max_tool_calls == 16


def test_approval_ttl_seconds_bounds():
    # below the minimum
    with pytest.raises(ValidationError):
        Settings(_env_file=None, approval_ttl_seconds=0)
    # above the maximum (24h + 1)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, approval_ttl_seconds=86401)
    # both inclusive bounds are accepted
    assert Settings(_env_file=None, approval_ttl_seconds=1).approval_ttl_seconds == 1
    assert Settings(_env_file=None, approval_ttl_seconds=86400).approval_ttl_seconds == 86400


def test_agent_actions_enabled_defaults_to_false(monkeypatch):
    monkeypatch.delenv("AGENT_ACTIONS_ENABLED", raising=False)
    settings = Settings(_env_file=None)
    # Privileged execution must be opt-in: never on by default.
    assert settings.agent_actions_enabled is False


def test_admin_credentials_are_not_exposed_by_serialization():
    admin_pw = "admin-serial-" + "value-not-for-logs"
    settings = Settings(
        _env_file=None,
        db2_admin_user="db2_admin",
        db2_admin_password=admin_pw,
    )

    assert admin_pw not in settings.model_dump_json()
    assert admin_pw not in str(settings.model_dump(mode="json"))
    assert admin_pw not in str(settings.model_dump())
    # ro password stays protected too
    ro = Settings(_env_file=None, db2_ro_password="ro-serial-value")
    assert "ro-serial-value" not in ro.model_dump_json()
