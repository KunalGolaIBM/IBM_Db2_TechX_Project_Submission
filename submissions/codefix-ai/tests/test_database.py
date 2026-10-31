"""
Unit tests for CodeFix AI IBM Db2 Database Module (database.py)
Tests parameterized SQL execution, connection checks, isolated mocks,
and optional live connectivity tests.
"""

from unittest.mock import patch, MagicMock
import pytest

import database
from config import Config


def test_db2_unconfigured_setup_mode():
    """When credentials are blank, database functions should report setup mode without crashing."""
    with patch.object(Config, "is_db2_configured", return_value=False):
        is_conn, msg = database.check_db2_connection()
        assert is_conn is False
        assert "setup mode" in msg.lower() or "not configured" in msg.lower()

        saved, err = database.save_history_record({"id": "test_1", "user_prompt": "hello"})
        assert saved is False
        assert "not configured" in err.lower()

        records = database.get_history_records()
        assert records == []

        rec = database.get_record_by_id("test_1")
        assert rec is None

        deleted = database.delete_record_by_id("test_1")
        assert deleted is False


def test_mocked_save_history_record():
    """Test saving a history record using mocked ibm_db driver."""
    mock_conn = MagicMock()
    mock_stmt = MagicMock()

    with patch.object(Config, "is_db2_configured", return_value=True):
        with patch("database.get_connection", return_value=mock_conn):
            with patch("ibm_db.prepare", return_value=mock_stmt) as mock_prepare:
                with patch("ibm_db.execute", return_value=True) as mock_exec:
                    with patch("ibm_db.close", return_value=True):
                        record = {
                            "id": "rec_123",
                            "session_id": "sess_abc",
                            "language": "python",
                            "mode": "write",
                            "user_prompt": "Create calculator",
                            "original_code": "",
                            "error_message": "",
                            "generated_code": "def calc(): pass",
                            "explanation": "Simple calculator",
                            "model_name": "qwen2.5-coder:3b"
                        }

                        success, err = database.save_history_record(record)
                        assert success is True
                        assert err is None

                        # Verify parameterized SQL was used with 10 parameter markers '?'
                        prep_sql = mock_prepare.call_args[0][1]
                        assert "INSERT INTO CODEFIX_HISTORY" in prep_sql
                        assert "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" in prep_sql
                        assert mock_exec.called


def test_mocked_get_history_records():
    """Test retrieving history records using mocked ibm_db fetch."""
    mock_conn = MagicMock()
    mock_stmt = MagicMock()

    sample_row = {
        "ID": "rec_001",
        "SESSION_ID": "sess_001",
        "LANGUAGE": "python",
        "MODE": "write",
        "USER_PROMPT": "Generate a binary search function",
        "ORIGINAL_CODE": "",
        "ERROR_MESSAGE": "",
        "GENERATED_CODE": "def bsearch(): pass",
        "EXPLANATION": "Binary search algorithm walkthrough",
        "MODEL_NAME": "qwen2.5-coder:3b",
        "CREATED_AT": "2026-10-29 12:00:00"
    }

    fetch_returns = [sample_row, None]

    with patch.object(Config, "is_db2_configured", return_value=True):
        with patch("database.get_connection", return_value=mock_conn):
            with patch("ibm_db.prepare", return_value=mock_stmt):
                with patch("ibm_db.execute", return_value=True):
                    with patch("ibm_db.fetch_assoc", side_effect=fetch_returns):
                        with patch("ibm_db.free_result", return_value=True):
                            with patch("ibm_db.close", return_value=True):
                                records = database.get_history_records(session_id="sess_001")
                                assert len(records) == 1
                                item = records[0]
                                assert item["id"] == "rec_001"
                                assert item["language"] == "python"
                                assert item["user_prompt"] == "Generate a binary search function"


def test_mocked_get_record_by_id():
    """Test retrieving a single record by its ID using parameterized SQL."""
    mock_conn = MagicMock()
    mock_stmt = MagicMock()

    sample_row = {
        "ID": "rec_specific",
        "SESSION_ID": "sess_xyz",
        "LANGUAGE": "javascript",
        "MODE": "debug",
        "USER_PROMPT": "Fix TypeError",
        "ORIGINAL_CODE": "foo()",
        "ERROR_MESSAGE": "TypeError: foo is not a function",
        "GENERATED_CODE": "function foo() {}",
        "EXPLANATION": "Defined function properly",
        "MODEL_NAME": "qwen2.5-coder:3b",
        "CREATED_AT": "2026-10-29 12:30:00"
    }

    with patch.object(Config, "is_db2_configured", return_value=True):
        with patch("database.get_connection", return_value=mock_conn):
            with patch("ibm_db.prepare", return_value=mock_stmt) as mock_prep:
                with patch("ibm_db.execute", return_value=True):
                    with patch("ibm_db.fetch_assoc", return_value=sample_row):
                        with patch("ibm_db.free_result", return_value=True):
                            with patch("ibm_db.close", return_value=True):
                                record = database.get_record_by_id("rec_specific")
                                assert record is not None
                                assert record["id"] == "rec_specific"
                                assert record["mode"] == "debug"

                                # Verify parameterized query
                                prep_sql = mock_prep.call_args[0][1]
                                assert "WHERE ID = ?" in prep_sql


def test_mocked_delete_record():
    """Test deleting a record by its ID."""
    mock_conn = MagicMock()
    mock_stmt = MagicMock()

    with patch.object(Config, "is_db2_configured", return_value=True):
        with patch("database.get_connection", return_value=mock_conn):
            with patch("ibm_db.prepare", return_value=mock_stmt) as mock_prep:
                with patch("ibm_db.execute", return_value=True):
                    with patch("ibm_db.close", return_value=True):
                        deleted = database.delete_record_by_id("rec_to_delete")
                        assert deleted is True

                        prep_sql = mock_prep.call_args[0][1]
                        assert "DELETE FROM CODEFIX_HISTORY WHERE ID = ?" in prep_sql


def test_mocked_init_db():
    """Test database schema creation and table check."""
    mock_conn = MagicMock()

    with patch.object(Config, "is_db2_configured", return_value=True):
        with patch("database.get_connection", return_value=mock_conn):
            with patch("ibm_db.exec_immediate", return_value=True):
                with patch("ibm_db.free_result", return_value=True):
                    with patch("ibm_db.close", return_value=True):
                        success, msg = database.init_db()
                        assert success is True
                        assert "schema" in msg.lower() or "table" in msg.lower() or "exists" in msg.lower()


@pytest.mark.skipif(not Config.is_db2_configured(), reason="Real IBM Db2 credentials not configured in .env")
def test_live_db2_connectivity_optional():
    """
    Live integration test against an actual IBM Db2 instance.
    Runs only when valid DB2_HOSTNAME, DB2_UID, and DB2_PWD are provided in .env.
    """
    is_connected, msg = database.check_db2_connection()
    assert is_connected is True, f"Live Db2 connection failed: {msg}"

    # Verify table initialization
    init_ok, init_msg = database.init_db()
    assert init_ok is True, f"Live Db2 table init failed: {init_msg}"
