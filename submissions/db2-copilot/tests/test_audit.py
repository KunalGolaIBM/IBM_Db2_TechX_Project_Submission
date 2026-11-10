"""
Unit tests for Db2 QUERY_AUDIT table logging.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import get_connection, execute_query
from src.copilot import log_audit
import ibm_db


def test_audit_logging():
    test_q = "TEST_QUESTION_AUTOMATED_CHECK"
    test_sql = "SELECT * FROM CUSTOMERS FETCH FIRST 1 ROWS ONLY"
    test_stat = "EXECUTED"
    test_v = "TEST_VERDICT"

    log_audit(test_q, test_sql, test_stat, test_v)

    conn = get_connection()
    try:
        rows = execute_query(
            conn,
            f"SELECT audit_id, question, sql_status FROM QUERY_AUDIT WHERE question = '{test_q}' ORDER BY audit_id DESC FETCH FIRST 1 ROWS ONLY"
        )
        assert len(rows) > 0, "Audit log record should exist in Db2"
        assert rows[0]["question"] == test_q
        assert rows[0]["sql_status"] == test_stat
    finally:
        # Cleanup test log row
        ibm_db.exec_immediate(conn, f"DELETE FROM QUERY_AUDIT WHERE question = '{test_q}'")
        ibm_db.close(conn)


if __name__ == "__main__":
    print("Running Audit Logging Unit Tests...")
    test_audit_logging()
    print("✅ Audit logging unit tests passed successfully!")

