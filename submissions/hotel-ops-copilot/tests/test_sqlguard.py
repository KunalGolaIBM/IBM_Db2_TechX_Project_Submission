import pytest

from hotelops.sqlguard import UnsafeSqlError, validate_select


def test_select_gets_row_limit():
    out = validate_select("SELECT * FROM V_DAILY_KPIS", row_limit=50)
    assert out.endswith("FETCH FIRST 50 ROWS ONLY")


def test_existing_limit_is_kept():
    sql = "SELECT * FROM ROOMS FETCH FIRST 5 ROWS ONLY"
    assert validate_select(sql) == sql


def test_with_and_trailing_semicolon_allowed():
    out = validate_select("WITH X AS (SELECT 1 AS A FROM SYSIBM.SYSDUMMY1) SELECT * FROM X;")
    assert out.startswith("WITH X")


def test_time_travel_and_updated_by_column_allowed():
    sql = ("SELECT RATE, UPDATED_BY FROM RATE_PLAN FOR SYSTEM_TIME AS OF '2026-11-01-00.00.00' "
           "WHERE ROOM_TYPE_ID = 6")
    assert "FOR SYSTEM_TIME" in validate_select(sql)


def test_keywords_inside_string_literals_are_fine():
    assert validate_select("SELECT * FROM GUEST_REVIEWS WHERE REVIEW_TEXT LIKE '%delete%'")


@pytest.mark.parametrize("sql", [
    "UPDATE RATE_PLAN SET RATE = 1",
    "DELETE FROM GUESTS",
    "DROP TABLE GUESTS",
    "SELECT 1 FROM SYSIBM.SYSDUMMY1; DROP TABLE GUESTS",
    "CALL SP_APPLY_ACTION(1, 'x', ?, ?)",
    "WITH X AS (SELECT 1 FROM SYSIBM.SYSDUMMY1) DELETE FROM GUESTS",
    "SELECT * FROM FINAL TABLE (INSERT INTO ROOMS VALUES ('999', 1, 9, 'IN_SERVICE'))",
    "GRANT DBADM ON DATABASE TO USER OPSAGENT",
    "",
])
def test_unsafe_statements_rejected(sql):
    with pytest.raises(UnsafeSqlError):
        validate_select(sql)


def test_comment_cannot_hide_second_statement():
    with pytest.raises(UnsafeSqlError):
        validate_select("SELECT 1 FROM SYSIBM.SYSDUMMY1 /* hi */ ; DELETE FROM GUESTS -- x")
