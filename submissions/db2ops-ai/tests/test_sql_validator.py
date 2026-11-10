import pytest
from src.ai.sql_validator import UnsafeQuery, validate_sql


def test_select_is_accepted():
    assert "SELECT" in validate_sql("SELECT CUSTOMER_NAME FROM CUSTOMERS")


@pytest.mark.parametrize("sql", [
    "DELETE FROM CUSTOMERS", "UPDATE CUSTOMERS SET CITY='Delhi'", "DROP TABLE CUSTOMERS",
    "SELECT 1 FROM CUSTOMERS; DELETE FROM CUSTOMERS", "SELECT * FROM SYSCAT.TABLES",
    "SELECT * FROM OTHER_SCHEMA.CUSTOMERS", "SELECT CUSTOMER_ID INTO X FROM CUSTOMERS",
])
def test_unsafe_queries_are_rejected(sql):
    with pytest.raises(UnsafeQuery):
        validate_sql(sql)


def test_invalid_sql_is_rejected():
    with pytest.raises(UnsafeQuery):
        validate_sql("SELECT FROM WHERE")


def test_safe_aggregate_query():
    assert "SUM" in validate_sql("SELECT SUM(TOTAL_AMOUNT) FROM ORDERS")
