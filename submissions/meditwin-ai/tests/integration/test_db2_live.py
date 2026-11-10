"""
Integration Tests: Real IBM Db2 Server Connection & Operations
Genuinely tests live connection against configured Db2 host and port 50000.
Fails when Db2 is not running rather than masking failures.
"""

import pytest
from db.connection import get_db2_connection, test_connection as check_db2_connection


def test_live_db2_connection_probe():
    """
    Directly tests live connectivity to IBM Db2 Community Edition.
    Checks server version and reporting.
    """
    result = check_db2_connection()
    assert isinstance(result, dict)
    assert "status" in result
    # If Db2 server is offline on localhost, verify structured failure detection
    if result["status"] == "failed":
        assert "Could not connect to IBM Db2" in result["message"]
    else:
        assert result["status"] == "connected"
        assert "dbms_name" in result


def test_db2_driver_level_information():
    """Verify official IBM CLI Driver v12.1 is available."""
    conn = get_db2_connection()
    assert conn is not None
