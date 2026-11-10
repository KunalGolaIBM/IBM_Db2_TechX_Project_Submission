"""
Test Category 1: IBM Db2 Connection Test
Verifies connection lifecycle, connection string construction, and graceful failure handling.
"""

import pytest
from config.settings import Db2Settings
from db.connection import Db2Connection, test_connection as check_db2_connection


def test_db2_settings_connection_string():
    """Verify Db2 connection string contains all required parameters."""
    settings = Db2Settings(
        host="test-host",
        port=50000,
        database="TESTDB",
        user="testuser",
        password="secretpassword",
        schema_name="TESTSCHEMA"
    )
    conn_str = settings.connection_string
    assert "DATABASE=TESTDB" in conn_str
    assert "HOSTNAME=test-host" in conn_str
    assert "PORT=50000" in conn_str
    assert "UID=testuser" in conn_str
    assert "PWD=secretpassword" in conn_str


def test_db2_connection_lifecycle_disconnected_state():
    """Verify is_connected is False when not connected."""
    conn = Db2Connection("DATABASE=NONE;HOSTNAME=invalid;PORT=50000;PROTOCOL=TCPIP;UID=x;PWD=y;")
    assert conn.is_connected is False
    server_info = conn.get_server_info()
    assert server_info["status"] == "disconnected"


def test_test_connection_handles_unreachable_server():
    """Verify test_connection returns structured failure status without crashing."""
    result = check_db2_connection()
    assert isinstance(result, dict)
    assert "status" in result
    if result["status"] == "failed":
        assert "message" in result
    elif result["status"] == "connected":
        assert "dbms_name" in result
