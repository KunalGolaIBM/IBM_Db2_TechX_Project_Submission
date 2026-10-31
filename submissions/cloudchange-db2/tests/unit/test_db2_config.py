"""Unit tests for IBM Db2 Configuration."""

import os
from unittest import mock
from backend.app.db2.config import Db2Config


def test_db2_config_defaults():
    """Verify default values when no environment variables are set."""
    with mock.patch.dict(os.environ, {}, clear=True):
        config = Db2Config.from_env()
        assert config.host == "localhost"
        assert config.port == 50000
        assert config.database == "BLUDB"
        assert config.user == "db2inst1"
        assert config.password == ""
        assert config.security == ""
        assert config.schema_name == "CLOUDCHANGE"
        assert not config.is_configured()


def test_db2_config_from_env_vars():
    """Verify custom environment variables parsing."""
    env = {
        "DB2_HOST": "db2.enterprise.internal",
        "DB2_PORT": "50001",
        "DB2_DATABASE": "AUDITDB",
        "DB2_USER": "cloud_admin",
        "DB2_PASSWORD": "secure_password_123",
        "DB2_SECURITY": "SSL",
        "DB2_SCHEMA": "PROD_CLOUDCHANGE",
        "DB2_SSL_SERVER_CERT": "/etc/ssl/db2.arm",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        config = Db2Config.from_env()
        assert config.host == "db2.enterprise.internal"
        assert config.port == 50001
        assert config.database == "AUDITDB"
        assert config.user == "cloud_admin"
        assert config.password == "secure_password_123"
        assert config.security == "SSL"
        assert config.schema_name == "PROD_CLOUDCHANGE"
        assert config.ssl_server_cert == "/etc/ssl/db2.arm"
        assert config.is_configured()


def test_db2_connection_string_construction():
    """Verify standard ibm_db connection string formatting."""
    config = Db2Config(
        host="127.0.0.1",
        port=50000,
        database="TESTDB",
        user="testuser",
        password="testpassword",
    )
    conn_str = config.get_connection_string()
    assert "DATABASE=TESTDB;" in conn_str
    assert "HOSTNAME=127.0.0.1;" in conn_str
    assert "PORT=50000;" in conn_str
    assert "PROTOCOL=TCPIP;" in conn_str
    assert "UID=testuser;" in conn_str
    assert "PWD=testpassword;" in conn_str
    assert "SECURITY=SSL;" not in conn_str


def test_db2_ssl_connection_string_construction():
    """Verify SSL ibm_db connection string formatting."""
    config = Db2Config(
        host="db2.cloud.ibm.com",
        port=50001,
        database="BLUDB",
        user="admin",
        password="secret",
        security="SSL",
        ssl_server_cert="/certs/db2.crt",
    )
    conn_str = config.get_connection_string()
    assert "SECURITY=SSL;" in conn_str
    assert "SSLServerCertificate=/certs/db2.crt;" in conn_str
