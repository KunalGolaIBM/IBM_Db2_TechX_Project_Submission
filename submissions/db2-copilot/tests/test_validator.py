"""
Unit tests for SQL Security Validator in Db2 Copilot.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.sql_validator import validate_sql


def test_allowed_select():
    valid, err, sql = validate_sql("SELECT * FROM CUSTOMERS WHERE customer_id = 1")
    assert valid, f"Expected valid SELECT, got error: {err}"


def test_join_query():
    valid, err, sql = validate_sql(
        "SELECT o.order_id, c.name FROM ORDERS o JOIN CUSTOMERS c ON o.customer_id = c.customer_id"
    )
    assert valid, f"Expected valid JOIN, got error: {err}"


def test_reject_delete():
    valid, err, sql = validate_sql("DELETE FROM ORDERS WHERE order_id = 101")
    assert not valid, "Validator should reject DELETE query"
    assert "Only read-only SELECT queries are allowed" in err


def test_reject_drop():
    valid, err, sql = validate_sql("DROP TABLE CUSTOMERS")
    assert not valid, "Validator should reject DROP query"


def test_reject_multi_statement():
    valid, err, sql = validate_sql("SELECT * FROM ORDERS; DROP TABLE CUSTOMERS;")
    assert not valid, "Validator should reject multi-statement query"
    assert "Multiple SQL statements" in err


def test_reject_unauthorized_table():
    valid, err, sql = validate_sql("SELECT * FROM SYSCAT.TABLES")
    assert not valid, "Validator should reject system catalog tables"


def test_reject_comments():
    valid, err, sql = validate_sql("SELECT * FROM ORDERS -- malicious comment")
    assert not valid, "Validator should reject SQL comments"


if __name__ == "__main__":
    print("Running Validator Unit Tests...")
    test_allowed_select()
    test_join_query()
    test_reject_delete()
    test_reject_drop()
    test_reject_multi_statement()
    test_reject_unauthorized_table()
    test_reject_comments()
    print("✅ All 7 Validator unit tests passed successfully!")

