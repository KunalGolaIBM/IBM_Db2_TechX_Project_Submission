from locklens.config import Settings
from locklens.errors import ConfigError

import pytest

GOOD = {"DB2_PASSWORD": "s3cret!", "DB2_HOST": "localhost", "DB2_PORT": "50000",
        "DB2_DATABASE": "testdb", "DB2_USER": "db2inst1"}


def test_valid_settings_and_defaults():
    s = Settings.from_env(GOOD)
    assert s.db_port == 50000 and s.poll_seconds == 5 and s.wait_warn_seconds == 10
    assert s.schema == "LOCKLENS" and s.llm_enabled is False and s.auto_refresh is False


def test_password_is_never_in_repr_or_redacted_view():
    s = Settings.from_env(GOOD)
    assert "s3cret!" not in repr(s)
    assert "s3cret!" not in str(s.redacted())
    assert s.redacted()["db_password"] == "set"


def test_missing_password_is_reported():
    env = {k: v for k, v in GOOD.items() if k != "DB2_PASSWORD"}
    with pytest.raises(ConfigError) as err:
        Settings.from_env(env)
    assert any("DB2_PASSWORD" in p for p in err.value.problems)


def test_invalid_port_and_host_and_schema_rejected_together():
    env = dict(GOOD, DB2_PORT="99999", DB2_HOST="bad host;x", LOCKLENS_SCHEMA="x; DROP TABLE y")
    with pytest.raises(ConfigError) as err:
        Settings.from_env(env)
    text = " ".join(err.value.problems)
    assert "DB2_PORT" in text and "DB2_HOST" in text and "LOCKLENS_SCHEMA" in text


def test_non_numeric_and_threshold_order_validated():
    with pytest.raises(ConfigError) as err:
        Settings.from_env(dict(GOOD, LOCKLENS_POLL_SECONDS="fast"))
    assert any("LOCKLENS_POLL_SECONDS" in p for p in err.value.problems)
    with pytest.raises(ConfigError):
        Settings.from_env(dict(GOOD, LOCKLENS_WAIT_WARN_SECONDS="30", LOCKLENS_WAIT_CRITICAL_SECONDS="20"))


def test_runtime_overrides_are_validated():
    s = Settings.from_env(GOOD)
    assert s.with_runtime_overrides(poll_seconds=9).poll_seconds == 9
    with pytest.raises(ConfigError):
        s.with_runtime_overrides(poll_seconds=0)


def test_schema_is_uppercased_and_bool_parsing():
    s = Settings.from_env(dict(GOOD, LOCKLENS_SCHEMA="mylens", LOCKLENS_AUTO_REFRESH="true",
                               LOCKLENS_LLM_ENABLED="no", DB2_SECURITY="ssl"))
    assert s.schema == "MYLENS" and s.auto_refresh is True and s.llm_enabled is False and s.db_ssl is True
