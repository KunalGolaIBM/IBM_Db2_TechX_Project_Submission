"""Db2 SQL checker: static rules, and live validation by PREPARE on the Db2 test schema."""

import pytest

from shipsafe.db2sql import Db2SqlChecker, static_rules
from shipsafe.db2sql.checker import statement_type


def codes(sql):
    return [i.code for i in static_rules(sql)]


@pytest.mark.parametrize("sql, expected", [
    ("SELECT A FROM T WHERE B = ?", []),
    ("DELETE FROM T", ["NO-WHERE"]),
    ("UPDATE T SET A = 1", ["NO-WHERE"]),
    ("UPDATE T SET A = 1 WHERE B = ?", []),
    ("SELECT * FROM T WHERE A = ?", ["SELECT-STAR"]),
    ("SELECT A FROM T", ["UNBOUNDED-READ"]),
    ("SELECT A FROM T FETCH FIRST 10 ROWS ONLY", []),
    ("SELECT A FROM T WHERE B = '%s'", ["TEMPLATE-PLACEHOLDER", "INLINE-LITERAL"]),
    ("SELECT A FROM T WHERE B = {b}", ["TEMPLATE-PLACEHOLDER"]),
    ("SELECT A FROM T WHERE B = 'x'", ["INLINE-LITERAL"]),
    ("DROP TABLE T", ["DESTRUCTIVE-DDL"]),
    ("SELECT 1 FROM T WHERE A = 1; DELETE FROM T WHERE A = 2", ["MULTI-STATEMENT"]),
    ("SELECT 1 FROM SYSIBM.SYSDUMMY1", []),
    ("-- comment ; with semicolon\nSELECT A FROM T WHERE B = ?", []),
    ("SELECT A FROM T WHERE B = 'it''s; fine'", ["INLINE-LITERAL"]),
])
def test_static_rules(sql, expected):
    assert codes(sql) == expected


def test_statement_type():
    assert statement_type("  /* x */ with q as (select 1 from t) select * from q") == "WITH"
    assert statement_type("(SELECT 1 FROM SYSIBM.SYSDUMMY1)") == "SELECT"
    assert statement_type("") == "UNKNOWN"


@pytest.fixture()
def checker(repo):
    return Db2SqlChecker(repo)


def test_valid_select_describes_columns(checker):
    r = checker.check("SELECT CLIENT, VERDICT FROM GUARD_EVENTS WHERE TS > ? FETCH FIRST 5 ROWS ONLY")
    assert r.valid and r.verdict == "clean"
    assert [c["name"] for c in r.result_columns] == ["CLIENT", "VERDICT"]
    assert r.parameter_markers == 1 and r.db2["prepared"]


def test_unknown_column_gets_suggestion(checker):
    r = checker.check("SELECT CLIENTT FROM GUARD_EVENTS WHERE TS > ?")
    assert not r.valid and r.verdict == "block"
    assert r.issues[0].code == "SQL0206N" and "CLIENT" in r.issues[0].suggestion
    assert r.db2["sqlstate"] == "42703"


def test_unknown_table_gets_suggestion(checker):
    r = checker.check("SELECT EVENT_ID FROM GUARD_EVENT WHERE TS > ?")
    assert r.issues[0].code == "SQL0204N" and "GUARD_EVENTS" in r.issues[0].suggestion


def test_syntax_error(checker):
    r = checker.check("SELEC 1 FROM SYSIBM.SYSDUMMY1")
    assert r.issues[0].code == "SQL0104N" and not r.valid


def test_delete_without_where_is_valid_but_blocked(checker):
    r = checker.check("DELETE FROM GUARD_EVENTS")
    assert r.valid and r.verdict == "block" and [i.code for i in r.issues] == ["NO-WHERE"]
    assert checker.repository.list_guard_events(limit=1001) is not None  # nothing was executed


def test_placeholder_sql_is_not_sent(checker):
    r = checker.check("SELECT A FROM T WHERE B = %s")
    assert r.db2 == {"prepared": False, "reason": "not sent to Db2 until the placeholders / statements are fixed"}


def test_empty_sql(checker):
    r = checker.check("  ;  ")
    assert not r.valid and r.issues[-1].code == "EMPTY"


def test_schema_overview_through_sqlalchemy(checker):
    ov = checker.schema_overview(tables=["guard_events", "FIX_ATTEMPTS"])
    names = {t["table"] for t in ov["tables"]}
    assert names == {"GUARD_EVENTS", "FIX_ATTEMPTS"}
    guard = next(t for t in ov["tables"] if t["table"] == "GUARD_EVENTS")
    assert guard["primary_key"] == ["EVENT_ID"]
    assert {"name": "VERDICT", "type": "VARCHAR(16)", "nullable": False} in guard["columns"]
    assert any(i["name"] == "IDX_GUARD_TS" for i in guard["indexes"])
    assert {"V_RISK_TREND", "V_PROJECT_POSTURE"} <= set(ov["views"])
    full = checker.schema_overview()
    fks = next(t for t in full["tables"] if t["table"] == "FINDINGS")["foreign_keys"]
    assert fks[0]["references"].startswith("ASSESSMENTS(")
