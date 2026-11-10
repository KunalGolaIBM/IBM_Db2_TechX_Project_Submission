"""
Tests for database connection and basic operations.
"""
import pytest

from app.db import conn, query

pytestmark = pytest.mark.integration


def test_connection():
    """Test that we can connect to Db2."""
    c = conn()
    assert c is not None
    c.close()


def test_simple_query():
    """Test a simple query."""
    result = query("SELECT 1 FROM SYSIBM.SYSDUMMY1")
    assert result is not None
    assert len(result) == 1
    assert result[0][0] == 1


def test_parameterized_query():
    """Test parameterized queries work correctly."""
    result = query(
        "SELECT CAST(? AS INTEGER) + CAST(? AS INTEGER) FROM SYSIBM.SYSDUMMY1",
        (5, 7),
    )
    assert result is not None
    assert result[0][0] == 12


def test_catalog_access():
    """Test that we can access the Db2 catalog."""
    result = query("""
        SELECT TABNAME FROM SYSCAT.TABLES 
        WHERE TABSCHEMA = 'DB2INST1' AND TABNAME = 'PATIENT'
        FETCH FIRST 1 ROW ONLY
    """)
    assert result is not None
