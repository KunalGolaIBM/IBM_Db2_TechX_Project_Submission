import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
import db, guard


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    monkeypatch.setattr(db, "prepare_ok", lambda s: True)


@pytest.mark.parametrize("sql", [
    "DELETE FROM BANKING.CUSTOMERS", "DROP TABLE BANKING.LOANS", "UPDATE BANKING.LOANS SET STATUS='X'",
    "SELECT 1 FROM BANKING.BRANCHES; DELETE FROM BANKING.LOANS", "SELECT * FROM SYSIBM.SYSTABLES",
    "SELECT 1 FROM BANKING.BRANCHES -- hi", "SELECT * FROM OTHER.SECRETS", "",
])
def test_blocked(sql):
    assert guard.validate(sql, "admin")[0] is False


def test_pii_policy():
    assert not guard.validate("SELECT EMAIL AS E FROM BANKING.CUSTOMERS", "analyst")[0]
    assert not guard.validate("SELECT * FROM BANKING.CUSTOMERS", "analyst")[0]
    assert guard.validate("SELECT COUNT(*) FROM BANKING.CUSTOMERS", "analyst")[0]
    assert guard.validate("SELECT EMAIL FROM BANKING.CUSTOMERS", "admin")[0]


def test_row_cap_added():
    ok, sql = guard.validate("SELECT BRANCH_ID FROM BANKING.BRANCHES", "analyst")
    assert ok and "FETCH FIRST 200 ROWS ONLY" in sql


def test_cte_and_join_allowed():
    sql = "WITH t AS (SELECT BRANCH_ID FROM BANKING.LOANS) SELECT B.NAME FROM t JOIN BANKING.BRANCHES B ON B.BRANCH_ID=t.BRANCH_ID"
    assert guard.validate(sql, "analyst")[0]
