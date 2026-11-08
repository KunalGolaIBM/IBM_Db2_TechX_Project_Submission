import pytest

from src.config import Settings


def test_settings_read_environment_at_instance_creation(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "DB2")
    monkeypatch.setenv("DB2_PASSWORD", "secret")
    settings = Settings()
    assert settings.db_backend == "db2"
    settings.validate()


def test_invalid_backend_is_rejected():
    with pytest.raises(ValueError, match="DB_BACKEND"):
        Settings(db_backend="mysql").validate()


def test_db2_requires_credentials():
    with pytest.raises(ValueError, match="DB2_PASSWORD"):
        Settings(db_backend="db2", db2_password="").validate()


def test_db2_connection_string_has_expected_fields():
    settings = Settings(db_backend="db2", db2_password="test", db2_host="db.example")
    value = settings.db2_connection_string
    assert "DATABASE=testdb" in value
    assert "HOSTNAME=db.example" in value
    assert "UID=db2inst1" in value
    assert "PWD=test" in value
