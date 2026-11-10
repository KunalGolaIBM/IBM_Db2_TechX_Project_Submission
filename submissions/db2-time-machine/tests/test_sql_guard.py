import pytest

from time_machine.sql_guard import UnsafeSQL, validate_readonly
from time_machine.temporal_sql import (ALLOWED_TABLES, NOW_SQL, ORDER_ITEMS, TEMPORAL_TABLES_SQL, delete_log_sql,
                                       metric_as_of_sql, snapshot_sql, versions_sql)
from datetime import datetime

T1, T2 = datetime(2026, 11, 9, 8, 30), datetime(2026, 11, 9, 11, 0)


@pytest.mark.parametrize("sql", [
    "DELETE FROM ORDER_ITEMS", "UPDATE ORDER_ITEMS SET UNIT_PRICE = 1", "DROP TABLE ORDER_ITEMS",
    "SELECT 1 FROM ORDER_ITEMS; DELETE FROM ORDER_ITEMS", "INSERT INTO AUDIT_LOG VALUES (1)",
    "SELECT * FROM SECRET_TABLE", "CALL SYSPROC.WLM_SET_CLIENT_INFO('x', NULL, NULL, NULL, NULL)",
    "WITH x AS (SELECT 1 FROM ORDER_ITEMS) DELETE FROM ORDER_ITEMS", "", "   ",
    "SELECT * FROM ORDER_ITEMS WHERE 1=1 -- hidden\n; DROP TABLE X",
])
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSQL):
        validate_readonly(sql, ALLOWED_TABLES)


def test_keywords_inside_string_literals_are_harmless():
    out = validate_readonly("SELECT 1 FROM ORDER_ITEMS WHERE CHANGED_BY = 'DELETE'", ALLOWED_TABLES)
    assert "FETCH FIRST" in out


def test_row_limit_is_applied_once():
    out = validate_readonly("SELECT * FROM ORDER_ITEMS", ALLOWED_TABLES, max_rows=7)
    assert out.endswith("FETCH FIRST 7 ROWS ONLY")
    again = validate_readonly(out, ALLOWED_TABLES, max_rows=7)
    assert again.count("FETCH FIRST") == 1


def test_all_generated_queries_pass_the_guard():
    queries = [metric_as_of_sql(ORDER_ITEMS, 1, T1), metric_as_of_sql(ORDER_ITEMS, None, T2),
               versions_sql(ORDER_ITEMS, 1, T1, T2), delete_log_sql(T1, T2), snapshot_sql(1), snapshot_sql(None),
               NOW_SQL, TEMPORAL_TABLES_SQL]
    for sql in queries:
        validate_readonly(sql, ALLOWED_TABLES)


def test_temporal_sql_shape():
    sql = versions_sql(ORDER_ITEMS, 3, T1, T2)
    assert "FOR SYSTEM_TIME FROM TIMESTAMP('2026-11-09 08:30:00.000000') TO TIMESTAMP('2026-11-09 11:00:00.000000')" in sql
    assert "WHERE PRODUCT_ID = 3" in sql
    assert "FOR SYSTEM_TIME AS OF TIMESTAMP('2026-11-09 08:30:00.000000')" in metric_as_of_sql(ORDER_ITEMS, 3, T1)


def test_product_id_cannot_inject_sql():
    with pytest.raises(ValueError):
        metric_as_of_sql(ORDER_ITEMS, "1; DROP TABLE X", T1)
    with pytest.raises(TypeError):
        metric_as_of_sql(ORDER_ITEMS, 1, "2026-01-01'); DROP TABLE X; --")
