"""Unit tests for IBM Db2 Connection Management and Transactions."""

from unittest import mock
import pytest

from backend.app.db2.config import Db2Config
from backend.app.db2.connection import (
    Db2ConnectionError,
    Db2ConnectionManager,
    Db2ExecutionError,
)


@pytest.fixture
def mock_ibm_db():
    """Create a mock ibm_db driver."""
    m = mock.MagicMock()
    m.SQL_AUTOCOMMIT_OFF = 0
    m.SQL_AUTOCOMMIT_ON = 1
    return m


def test_db2_connection_manager_connect(mock_ibm_db):
    """Verify that connect calls ibm_db.connect with proper connection string."""
    mock_conn = mock.MagicMock()
    mock_ibm_db.connect.return_value = mock_conn

    config = Db2Config(
        host="localhost",
        port=50000,
        database="BLUDB",
        user="db2inst1",
        password="password",
    )
    cm = Db2ConnectionManager(config)

    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        conn = cm.connect()
        assert conn == mock_conn
        mock_ibm_db.connect.assert_called_once()
        args = mock_ibm_db.connect.call_args[0]
        assert "DATABASE=BLUDB;" in args[0]
        assert "HOSTNAME=localhost;" in args[0]


def test_db2_connection_manager_connect_failure(mock_ibm_db):
    """Verify connection error raising on driver failure."""
    mock_ibm_db.connect.return_value = False
    mock_ibm_db.conn_errormsg.return_value = "Connection refused by host"

    cm = Db2ConnectionManager()
    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        with pytest.raises(Db2ConnectionError, match="Connection refused by host"):
            cm.connect()


def test_db2_execute_statement_success(mock_ibm_db):
    """Verify prepare and execute parameter binding."""
    mock_conn = mock.MagicMock()
    mock_stmt = mock.MagicMock()
    mock_ibm_db.prepare.return_value = mock_stmt
    mock_ibm_db.execute.return_value = True

    cm = Db2ConnectionManager()
    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        stmt = cm.execute_statement(mock_conn, "SELECT * FROM cc_runs WHERE run_id = ?", ("run-123",))
        assert stmt == mock_stmt
        mock_ibm_db.prepare.assert_called_once_with(mock_conn, "SELECT * FROM cc_runs WHERE run_id = ?")
        mock_ibm_db.execute.assert_called_once_with(mock_stmt, ("run-123",))


def test_db2_execute_statement_prepare_failure(mock_ibm_db):
    """Verify error raised when prepare fails."""
    mock_conn = mock.MagicMock()
    mock_ibm_db.prepare.return_value = False
    mock_ibm_db.conn_errormsg.return_value = "Table CC_RUNS does not exist"

    cm = Db2ConnectionManager()
    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        with pytest.raises(Db2ExecutionError, match="Db2 prepare failed"):
            cm.execute_statement(mock_conn, "SELECT * FROM cc_runs")


def test_db2_fetch_all_and_one_assoc(mock_ibm_db):
    """Verify dictionary fetching with lowercase key normalization."""
    mock_stmt = mock.MagicMock()
    # Mock two rows then False
    mock_ibm_db.fetch_assoc.side_effect = [
        {"RUN_ID": "123", "STATUS": "PREDICTED"},
        {"RUN_ID": "456", "STATUS": "VERIFIED"},
        False,
    ]

    cm = Db2ConnectionManager()
    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        rows = cm.fetch_all_assoc(mock_stmt)
        assert len(rows) == 2
        assert rows[0] == {"run_id": "123", "status": "PREDICTED"}
        assert rows[1] == {"run_id": "456", "status": "VERIFIED"}


def test_db2_transaction_commit_on_success(mock_ibm_db):
    """Verify commit and autocommit behavior on successful transaction."""
    mock_conn = mock.MagicMock()
    mock_ibm_db.connect.return_value = mock_conn

    cm = Db2ConnectionManager()
    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        with cm.transaction() as conn:
            assert conn == mock_conn

        mock_ibm_db.autocommit.assert_any_call(mock_conn, mock_ibm_db.SQL_AUTOCOMMIT_OFF)
        mock_ibm_db.commit.assert_called_once_with(mock_conn)
        mock_ibm_db.rollback.assert_not_called()
        mock_ibm_db.close.assert_called_once_with(mock_conn)


def test_db2_transaction_rollback_on_error(mock_ibm_db):
    """Verify rollback on exception within transaction block."""
    mock_conn = mock.MagicMock()
    mock_ibm_db.connect.return_value = mock_conn

    cm = Db2ConnectionManager()
    with mock.patch("backend.app.db2.connection.ibm_db", mock_ibm_db):
        with pytest.raises(RuntimeError, match="Simulated failure"):
            with cm.transaction():
                raise RuntimeError("Simulated failure")

        mock_ibm_db.commit.assert_not_called()
        mock_ibm_db.rollback.assert_called_once_with(mock_conn)
        mock_ibm_db.close.assert_called_once_with(mock_conn)
