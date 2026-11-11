import re
from app.database.session import db_session

def test_sql_adaptation_for_sqlite():
    # Test Db2 FETCH FIRST n ROWS ONLY conversion
    db2_sql = "SELECT * FROM CLOUDLOOP.OPPORTUNITIES WHERE KIND = ? OFFSET 10 ROWS FETCH FIRST 20 ROWS ONLY"
    adapted = db_session._adapt_sql_for_sqlite(db2_sql)

    assert "CLOUDLOOP." not in adapted
    assert "LIMIT 20 OFFSET 10" in adapted

def test_sql_fetch_first_without_offset():
    db2_sql = "SELECT * FROM CLOUDLOOP.OPPORTUNITIES FETCH FIRST 10 ROWS ONLY"
    adapted = db_session._adapt_sql_for_sqlite(db2_sql)
    assert "LIMIT 10" in adapted

def test_v_active_opportunities_date_replacement():
    db2_sql = "SELECT * FROM CLOUDLOOP.V_ACTIVE_OPPORTUNITIES WHERE DEADLINE >= CURRENT DATE"
    adapted = db_session._adapt_sql_for_sqlite(db2_sql)
    assert "date('now')" in adapted
