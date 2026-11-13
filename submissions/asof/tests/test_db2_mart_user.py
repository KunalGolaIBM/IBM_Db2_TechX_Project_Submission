"""Db2 integration: dbt's own user reads the four tables the marts need and builds only in its mart schema."""

from __future__ import annotations

import pytest
from test_db2_ledger import entry

from asof import db, ledger, schema
from asof.config import ConfigError

pytestmark = pytest.mark.db2


@pytest.fixture
def mart_conn(settings, test_schema):
    try:
        conn = db.connect(settings, "mart")
    except (ConfigError, db.DatabaseError) as exc:
        pytest.skip(f"mart user cannot connect (run python -m asof.setup first): {exc}")
    yield conn
    conn.rollback()
    conn.close()


def test_the_mart_user_reads_decisions_but_not_the_customer_text(app_conn, mart_conn, test_schema):
    ledger.append(app_conn, entry(question_redacted="What is the pet fee?"), test_schema)
    db.use_schema(mart_conn, test_schema)
    assert db.query(mart_conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0] >= 1
    texts = {r[0] for r in db.query(mart_conn, "SELECT QUESTION_REDACTED FROM ANSWER_LEDGER")}
    assert texts == {"[masked]"}


@pytest.mark.parametrize("sql", [
    "DELETE FROM ANSWER_LEDGER",
    "UPDATE CLAIM_CITATION SET VERDICT = 'SUPPORTED'",
    "UPDATE POLICY_CLAUSE SET CLAUSE_TEXT = 'x'",
    "SELECT COUNT(*) FROM API_USER",
    "CREATE TABLE NOT_HERE (X INT)",
])
def test_the_mart_user_cannot_touch_anything_else(mart_conn, test_schema, sql):
    db.use_schema(mart_conn, test_schema)
    with pytest.raises(db.DatabaseError) as err:
        db.execute(mart_conn, sql)
    mart_conn.rollback()
    assert err.value.sqlstate in ("42501", "42502")


def test_the_mart_user_builds_tables_only_in_its_own_schema(mart_conn, test_schema):
    mart = schema.mart_schema(test_schema)
    db.use_schema(mart_conn, mart)
    db.execute(mart_conn, "CREATE TABLE PROBE_MART (X INT)")
    db.execute(mart_conn, "DROP TABLE PROBE_MART")
    mart_conn.commit()
