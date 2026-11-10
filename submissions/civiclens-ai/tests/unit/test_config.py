import pytest
from pydantic import ValidationError

from civiclens.config import Settings


def test_connection_string_requires_password(monkeypatch):
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    s = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="DB2_PASSWORD"):
        s.db2_connection_string()


def test_connection_string_plain_and_ssl():
    s = Settings(_env_file=None, db2_password="pw", db2_host="db.example", db2_port=50001)
    cs = s.db2_connection_string()
    assert "HOSTNAME=db.example;" in cs and "PORT=50001;" in cs and "SECURITY=SSL" not in cs
    ssl = Settings(_env_file=None, db2_password="pw", db2_security="SSL")
    assert "SECURITY=SSL;" in ssl.db2_connection_string()


def test_redacted_target_never_contains_password():
    s = Settings(_env_file=None, db2_password="super-secret")
    assert "super-secret" not in s.redacted_target()
    assert "super-secret" not in repr(s)


@pytest.mark.parametrize("bad", ["CIVIC;DROP", "1ABC", "a b", "X" * 40, 'Q"'])
def test_schema_identifier_validation(bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db2_schema=bad)


def test_schema_is_uppercased():
    assert Settings(_env_file=None, db2_schema="civic_demo").db2_schema == "CIVIC_DEMO"


def test_connection_string_rejects_injection_in_host():
    s = Settings(_env_file=None, db2_password="pw", db2_host="h;PWD=x")
    with pytest.raises(ValueError):
        s.db2_connection_string()
