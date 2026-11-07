"""TLS to Db2: the connection string, its validation, and a real TLS connection when one is available.

The Db2 tests need TLS turned on in the local container (scripts/enable_db2_tls.sh, port 50001) and skip
otherwise. CI turns it on against IBM's stock image and runs them."""

from __future__ import annotations

import socket

import pytest
from pydantic import ValidationError

from asof import db, ledger
from asof.config import PROJECT_ROOT, ConfigError, Settings

CERT = PROJECT_ROOT / "var" / "tls" / "db2-server.arm"
TLS_PORT = 50001


def test_plain_tcp_by_default():
    out = db.dsn(Settings(db2_host="localhost"))
    assert "SECURITY" not in out and "SSLServerCertificate" not in out


def test_tls_without_a_pinned_certificate_uses_the_drivers_trust():
    assert db.dsn(Settings(db2_ssl=True)).endswith("SECURITY=SSL;")


def test_a_pinned_certificate_is_resolved_and_must_exist(tmp_path):
    cert = tmp_path / "server.arm"
    cert.write_text("-----BEGIN CERTIFICATE-----\n")
    assert db.dsn(Settings(db2_ssl=True, db2_ssl_server_cert=str(cert))).endswith(f"SECURITY=SSL;SSLServerCertificate={cert};")
    with pytest.raises(ConfigError, match="no certificate file"):
        db.dsn(Settings(db2_ssl=True, db2_ssl_server_cert=str(tmp_path / "missing.arm")))


@pytest.mark.parametrize("path", ["cert.arm;SECURITY=NONE", "a=b.arm", "x{y}.arm"])
def test_a_certificate_path_cannot_add_keywords_to_the_connection_string(path):
    with pytest.raises(ValidationError):
        Settings(db2_ssl=True, db2_ssl_server_cert=path)


def test_a_certificate_without_tls_is_a_configuration_error():
    with pytest.raises(ValidationError, match="DB2_SSL"):
        Settings(db2_ssl_server_cert="var/tls/db2-server.arm")


def test_a_remote_db2_over_plain_tcp_is_warned_about(monkeypatch, caplog):
    monkeypatch.setattr(db, "_warned_plain_tcp", False)
    monkeypatch.setattr(db.ibm_db_dbi, "connect", lambda *a: (_ for _ in ()).throw(RuntimeError("stop here")))
    with pytest.raises(db.DatabaseError):
        db.connect(Settings(db2_host="db2.example.com", asof_app_password="x" * 20), "app")
    assert "over plain TCP" in caplog.text


def _tls_listening() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", TLS_PORT), timeout=2):
            return True
    except OSError:
        return False


tls_db2 = pytest.mark.skipif(not (CERT.is_file() and _tls_listening()),
                             reason="TLS not enabled on the local Db2 (scripts/enable_db2_tls.sh)")


@pytest.mark.db2
@tls_db2
def test_the_runtime_user_works_over_tls(settings, test_schema):
    tls = settings.model_copy(update={"db2_ssl": True, "db2_port": TLS_PORT, "db2_ssl_server_cert": str(CERT),
                                      "db2_host": "localhost"})
    with db.connection(tls, "app") as conn:
        assert db.query(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1") == [(1,)]
        assert ledger.verify_chain(conn, test_schema).status == "OK"


@pytest.mark.db2
@tls_db2
@pytest.mark.parametrize("update", [
    {"db2_ssl": True, "db2_ssl_server_cert": None},   # TLS, but the self-signed certificate is not trusted
    {"db2_ssl": False, "db2_ssl_server_cert": None},  # plain TCP to the TLS port
])
def test_the_tls_port_refuses_untrusted_or_plain_connections(settings, update):
    bad = settings.model_copy(update={"db2_port": TLS_PORT, "db2_host": "localhost", **update})
    with pytest.raises(db.DatabaseError):
        db.connect(bad, "app").close()


def test_a_fresh_env_copied_from_the_example_loads(monkeypatch):
    """.env.example is what judges copy: every key in it, empty or not, must validate."""
    from asof.config import PROJECT_ROOT

    s = Settings(_env_file=PROJECT_ROOT / ".env.example")
    assert s.db2_ssl is False and s.db2_ssl_cert_path is None and s.anchor_key is None
