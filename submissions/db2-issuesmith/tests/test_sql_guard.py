import pytest

from issuesmith.sql_agent import UnsafeSQL, validate_sql


def test_accepts_select_on_schema_and_adds_limit():
    q = validate_sql("SELECT CATEGORY, INCIDENTS FROM ISSUESMITH.V_CATEGORY_STATS;", "ISSUESMITH")
    assert q.endswith("FETCH FIRST 200 ROWS ONLY")


def test_accepts_cte():
    validate_sql("WITH t AS (SELECT * FROM ISSUESMITH.INCIDENTS) SELECT COUNT(*) FROM t", "ISSUESMITH")


@pytest.mark.parametrize("sql", [
    "DELETE FROM ISSUESMITH.INCIDENTS",
    "SELECT * FROM ISSUESMITH.INCIDENTS; DROP TABLE ISSUESMITH.INCIDENTS",
    "SELECT * FROM SYSCAT.TABLES",
    "SELECT * FROM ISSUESMITH.INCIDENTS -- hi",
    "UPDATE ISSUESMITH.INCIDENTS SET STATUS='POSTED'",
])
def test_rejects_unsafe(sql):
    with pytest.raises(UnsafeSQL):
        validate_sql(sql, "ISSUESMITH")
