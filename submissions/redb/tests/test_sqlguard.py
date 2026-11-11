import pytest

from redb.sqlguard import UnsafeSQL, check_readonly, is_safe


@pytest.mark.parametrize("sql", [
    "SELECT * FROM RETAIL.ORDERS",
    "with x as (select 1 as a from sysibm.sysdummy1) select a from x",
    "SELECT COUNT(*) FROM T WHERE NOTE = 'please DELETE me; now'",
    "(SELECT 1 FROM SYSIBM.SYSDUMMY1)",
    "SELECT CREATED_AT, UPDATED_BY FROM T",          # keywords only as part of identifiers
    "SELECT 1 FROM SYSIBM.SYSDUMMY1;",               # one trailing semicolon is tolerated
])
def test_allowed(sql):
    assert is_safe(sql)


@pytest.mark.parametrize("sql", [
    "", "   ",
    "DELETE FROM RETAIL.ORDERS",
    "SELECT 1 FROM SYSIBM.SYSDUMMY1; DROP TABLE RETAIL.ORDERS",
    "SELECT * FROM T WHERE X IN (SELECT Y FROM OLD TABLE (DELETE FROM T))",
    "WITH D AS (SELECT 1 FROM SYSIBM.SYSDUMMY1) INSERT INTO T SELECT * FROM D",
    "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE T')",
    "VALUES 1",
    "select * from t /* ok */; grant dbadm on database to user evil",
    "SELECT * FROM T WHERE 1=1 -- \n; DROP TABLE T",
    "UPDATE T SET A = 1",
])
def test_denied(sql):
    with pytest.raises(UnsafeSQL):
        check_readonly(sql)


def test_strips_comments_and_trailing_semicolon():
    assert check_readonly("/* hint */ SELECT 1 FROM SYSIBM.SYSDUMMY1 ;") == "SELECT 1 FROM SYSIBM.SYSDUMMY1"
