import pytest

from hotelops.sqlguard import UnsafeSqlError, check_ast, validate_select


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


# --- AST layer (SQLGlot) -------------------------------------------------------------------------

DB2_QUERIES_AGENTS_WRITE = [
    "SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE",
    "SELECT COUNT(*) FROM RESERVATIONS WHERE CHECK_IN = CURRENT DATE + 1 DAY AND STATUS = 'CONFIRMED'",
    "SELECT * FROM V_DAILY_KPIS WHERE STAY_DATE BETWEEN CURRENT DATE - 7 DAYS AND CURRENT DATE",
    "SELECT CREATED_AT FROM GUEST_REVIEWS WHERE CREATED_AT >= CURRENT TIMESTAMP - 30 DAYS",
    "SELECT RATE FROM RATE_PLAN FOR SYSTEM_TIME AS OF '2026-11-01-00.00.00' WHERE ROOM_TYPE_ID = 6",
    "SELECT * FROM PROMOTIONS FOR BUSINESS_TIME AS OF '2026-11-21'",
    "SELECT DAYS(CHECK_OUT) - DAYS(CHECK_IN) AS NIGHTS FROM RESERVATIONS",
    "SELECT G.FULL_NAME, R.CHECK_IN FROM GUESTS G JOIN RESERVATIONS R ON R.GUEST_ID = G.GUEST_ID "
    "WHERE G.LOYALTY_TIER = 'PLATINUM' AND R.CHECK_IN BETWEEN CURRENT DATE AND CURRENT DATE + 3 DAYS",
    "SELECT VARCHAR_FORMAT(STAY_DATE, 'YYYY-MM') AS M, SUM(ROOM_REVENUE) FROM V_DAILY_KPIS "
    "GROUP BY VARCHAR_FORMAT(STAY_DATE, 'YYYY-MM')",
    "WITH T AS (SELECT ROOM_NO, COUNT(*) AS N FROM GUEST_REVIEWS GROUP BY ROOM_NO) "
    "SELECT * FROM T ORDER BY N DESC FETCH FIRST 3 ROWS ONLY",
    "SELECT * FROM HOTELOPS.ROOMS",
    "SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1",
]


@pytest.mark.parametrize("sql", DB2_QUERIES_AGENTS_WRITE)
def test_ast_accepts_real_db2_agent_queries(sql):
    assert validate_select(sql)


def test_guard_parses_with_ibm_db2_dialect():
    from hotelops.sqlguard import DB2_DIALECT
    assert type(DB2_DIALECT).__module__.startswith("db2_sqlglot"), type(DB2_DIALECT)


@pytest.mark.parametrize("sql", [
    "SELECT RATE FROM RATE_PLAN FOR SYSTEM_TIME FROM '2026-11-01' TO '2026-11-05'",
    "SELECT * FROM ROOMS ORDER BY ROOM_NO OFFSET 5 ROWS FETCH NEXT 5 ROWS ONLY",
    "SELECT REVIEW_ID FROM REVIEW_CHUNKS ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR('[0.1,0.2]', 2, FLOAT32), "
    "COSINE) FETCH FIRST 5 ROWS ONLY",
    "SELECT * FROM RESERVATIONS WHERE CHECK_IN <= CURRENT DATE + ? DAYS",
    "SELECT * FROM GUEST_REVIEWS WHERE CREATED_AT >= CURRENT DATE - 1 MONTH",
    "SELECT * FROM GUEST_REVIEWS WHERE CREATED_AT > CURRENT TIMESTAMP - 2 HOURS",
    "SELECT TIMESTAMPDIFF(4, CHAR(CURRENT TIMESTAMP - CREATED_AT)) FROM GUEST_REVIEWS",
    "VALUES CURRENT DATE",
])
def test_ast_accepts_more_db2_syntax(sql):
    assert validate_select(sql)


@pytest.mark.parametrize("sql, why", [
    ("SELECT * FROM SYSCAT.TABLES", "SYSCAT"),
    ("SELECT * FROM SYSIBMADM.MON_LOCKWAITS", "SYSIBMADM"),
    ("SELECT * FROM OTHERSCHEMA.PAYROLL", "OTHERSCHEMA"),
    ("SELECT * FROM ROOMS WHERE ROOM_NO IN (SELECT TABNAME FROM SYSCAT.TABLES)", "SYSCAT"),
    ("WITH X AS (SELECT * FROM SYSIBMADM.ENV_INST_INFO) SELECT * FROM X", "SYSIBMADM"),
])
def test_ast_rejects_tables_outside_the_app_schema(sql, why):
    with pytest.raises(UnsafeSqlError, match=why):
        validate_select(sql)


def test_ast_fails_closed_on_unparseable_sql():
    with pytest.raises(UnsafeSqlError, match="could not be parsed"):
        check_ast("SELECT FROM WHERE (((")


def test_ast_rejects_write_hidden_where_keywords_are_not_screened():
    # The lexical screen alone is bypassed here (it is called directly); the tree still has the DELETE.
    with pytest.raises(UnsafeSqlError):
        check_ast("WITH X AS (SELECT 1 AS A FROM SYSIBM.SYSDUMMY1) DELETE FROM GUESTS")
    with pytest.raises(UnsafeSqlError):
        check_ast("UPDATE RATE_PLAN SET RATE = 1")
