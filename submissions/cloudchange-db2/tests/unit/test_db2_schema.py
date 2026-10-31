"""Unit tests for IBM Db2 Schema Initialization and Idempotency."""

from unittest import mock
import pytest

from backend.app.db2.connection import Db2ConnectionManager, Db2ExecutionError
from backend.app.db2.schema import (
    INDEX_DEFINITIONS,
    TABLE_DEFINITIONS,
    _is_already_exists_error,
    init_db2_schema,
)


def test_is_already_exists_error():
    """Verify error string detection for Db2 idempotent DDL."""
    assert _is_already_exists_error("SQL0601N The name of the object to be created is identical to an existing name")
    assert _is_already_exists_error("SQLCODE -601, Table CC_RUNS already exists")
    assert _is_already_exists_error("SQLCODE -605, Index already exists")
    assert _is_already_exists_error("SQLSTATE 42710")
    assert not _is_already_exists_error("Syntax error in SQL statement")
    assert not _is_already_exists_error("Permission denied")


def test_init_db2_schema_success():
    """Verify all table and index DDL statements are executed."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()

    init_db2_schema(conn=mock_conn, connection_manager=mock_cm, schema_name="TEST_SCHEMA")

    # Table statements + index statements + schema statement
    expected_statement_count = len(TABLE_DEFINITIONS) + len(INDEX_DEFINITIONS) + 1
    assert mock_cm.execute_statement.call_count == expected_statement_count


def test_init_db2_schema_handles_existing_tables():
    """Verify idempotent handling when tables and indexes already exist."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()

    # Raise 'table already exists' for DDL
    mock_cm.execute_statement.side_effect = [
        None,  # SET CURRENT SCHEMA
        Db2ExecutionError("SQL0601N Table CC_RUNS already exists"),  # cc_runs table
        *[None] * (len(TABLE_DEFINITIONS) - 1),  # remaining tables
        Db2ExecutionError("SQL0605N Index idx_cc_runs_status already exists"),  # first index
        *[None] * (len(INDEX_DEFINITIONS) - 1),  # remaining indexes
    ]

    # Should complete cleanly without raising
    init_db2_schema(conn=mock_conn, connection_manager=mock_cm, schema_name="TEST_SCHEMA")


def test_init_db2_schema_raises_on_fatal_error():
    """Verify unexpected database errors are raised."""
    mock_cm = mock.MagicMock(spec=Db2ConnectionManager)
    mock_conn = mock.MagicMock()

    mock_cm.execute_statement.side_effect = [
        None,  # SET CURRENT SCHEMA
        Db2ExecutionError("SQL0901N Internal database error occurred"),
    ]

    with pytest.raises(Db2ExecutionError, match="SQL0901N"):
        init_db2_schema(conn=mock_conn, connection_manager=mock_cm, schema_name="TEST_SCHEMA")
