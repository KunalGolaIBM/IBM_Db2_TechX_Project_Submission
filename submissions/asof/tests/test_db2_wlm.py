"""Db2 workload management (07_wlm.sql): Db2 itself, not AsOf's Python, stops an analyst's heavy query. Each test
connects as an analyst user directly and runs SQL that never went through askledger.validate."""

from __future__ import annotations

import time

import pytest
from fakes import ScriptedLLM

from asof import db, wlm
from asof.askledger import LedgerAsker
from asof.config import ConfigError
from asof.schemas import LedgerSql

pytestmark = pytest.mark.db2

# The optimizer's estimates for cross joins of the audit views swing with the statistics Db2 holds (docs/wlm.md), so the
# cost test uses the catalog, whose statistics are real: Db2 estimates this at about 3.7 * 10^11 timerons.
EXPENSIVE = ("SELECT A.COLNAME FROM SYSCAT.COLUMNS A, SYSCAT.COLUMNS B, SYSCAT.COLUMNS C "
             "ORDER BY A.COLNAME, B.COLNAME, C.COLNAME")
# Valid for Ask the ledger. Db2 refuses it on cost or stops it on time, depending on its estimate.
CROSS_JOIN = ("SELECT COUNT(*) AS N FROM V_POLICY_TIMELINE a, V_POLICY_TIMELINE b, V_POLICY_TIMELINE c, "
              "V_POLICY_TIMELINE d, V_POLICY_TIMELINE e, V_POLICY_TIMELINE f")
MANY_ROWS = "SELECT A.CLAUSE_ID FROM V_POLICY_TIMELINE A, V_POLICY_TIMELINE B, V_POLICY_TIMELINE C"
# A low estimate (Db2 cannot know how deep the recursion goes) and minutes of work: only the time limit can stop it.
LONG_RUNNING = ("WITH R(N) AS (SELECT 1 FROM SYSIBM.SYSDUMMY1 UNION ALL SELECT N + 1 FROM R WHERE N < 2000000000) "
                "SELECT COUNT(*) FROM R")
SQL_WORKLOADS = ("SELECT DISTINCT SESSION_AUTH_ID, WORKLOAD_NAME "
                 "FROM TABLE(WLM_GET_SERVICE_CLASS_WORKLOAD_OCCURRENCES(NULL, NULL, -2)) WHERE SESSION_AUTH_ID IN (?, ?, ?)")


def _connect(settings, role, name):
    try:
        conn = db.connect(settings, role)
    except (ConfigError, db.DatabaseError) as exc:
        pytest.skip(f"{role} cannot connect (run python -m asof.setup first): {exc}")
    db.use_schema(conn, name)
    return conn


def _stopped_by(conn, sql) -> tuple[str, int]:
    """Run `sql` to the last row and return (threshold, reason code) of the SQL4712N Db2 stopped it with."""
    with pytest.raises(db.DatabaseError) as err:
        cur = conn.cursor()
        try:
            cur.execute(sql)
            while cur.fetchmany(1000):
                pass
        except Exception as exc:  # noqa: BLE001 - ibm_db raises plain Exception subclasses
            raise db.wrap_error(exc, "Query failed") from None
        finally:
            cur.close()
    conn.rollback()
    assert (err.value.sqlstate, err.value.sqlcode) == (wlm.THRESHOLD_STATE, -4712), str(err.value)
    m = wlm._STOPPED.search(str(err.value))
    assert m, str(err.value)
    return m.group(1), int(m.group(2))


@pytest.mark.parametrize("role", ["analyst", "analyst_airline"])
def test_db2_refuses_an_expensive_query_before_it_runs(settings, test_schema, role):
    conn = _connect(settings, role, test_schema)
    try:
        started = time.monotonic()
        assert _stopped_by(conn, EXPENSIVE) == (wlm.COST.threshold, wlm.COST.reason_code)
        assert time.monotonic() - started < 5  # refused on the estimate, not after running
        assert db.query(conn, "SELECT COUNT(*) FROM V_POLICY_TIMELINE")[0][0] > 0  # and the session goes on
    finally:
        conn.close()


def test_db2_stops_a_query_that_returns_too_many_rows(settings, test_schema):
    conn = _connect(settings, "analyst", test_schema)
    try:
        assert db.query(conn, "SELECT COUNT(*) FROM V_POLICY_TIMELINE")[0][0] ** 3 > wlm.ROWS.value
        assert _stopped_by(conn, MANY_ROWS) == (wlm.ROWS.threshold, wlm.ROWS.reason_code)
    finally:
        conn.close()


def test_db2_stops_a_query_that_runs_too_long(settings, test_schema):
    conn = _connect(settings, "analyst", test_schema)
    try:
        started = time.monotonic()
        assert _stopped_by(conn, LONG_RUNNING) == (wlm.TIME.threshold, wlm.TIME.reason_code)
        assert wlm.TIME.value <= time.monotonic() - started < wlm.TIME.value + 30
    finally:
        conn.close()


def test_analysts_land_in_the_workload_and_the_runtime_user_does_not(settings, admin_conn, test_schema):
    conns = [_connect(settings, role, test_schema) for role in ("analyst", "analyst_bank", "app")]
    try:
        for c in conns:
            db.query(c, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
        users = (settings.asof_analyst_user.upper(), settings.asof_bank_analyst_user.upper(), settings.asof_app_user.upper())
        landed = {u.strip(): w.strip() for u, w in db.query(admin_conn, SQL_WORKLOADS, users)}
        assert landed == {users[0]: wlm.WORKLOAD, users[1]: wlm.WORKLOAD, users[2]: "SYSDEFAULTUSERWORKLOAD"}
    finally:
        for c in conns:
            c.close()


def test_the_live_thresholds_are_the_ones_wlm_py_describes(admin_conn, test_schema):
    assert wlm.installed(admin_conn) == {limit.threshold: (limit.predicate, limit.value, "S", "Y") for limit in wlm.LIMITS}


def test_ask_the_ledger_shows_db2s_refusal_plainly(settings, test_schema):
    """The app's own statement timeout is raised past Db2's 10-second limit, so whatever stops this query is Db2's
    workload management, and the page says so in plain words."""
    llm = ScriptedLLM(sql=[LedgerSql(sql=CROSS_JOIN, explanation="x"), LedgerSql(sql=CROSS_JOIN, explanation="x")])
    r = LedgerAsker(llm, settings, test_schema, timeout_s=60).ask("count everything against everything")
    assert (r.status, r.rows, r.sql) == ("STOPPED", [], None)
    assert all("SQL4712N" in a["db2_error"] and a["db2_threshold"].startswith("Db2 ") for a in r.attempts)
    assert r.reason == r.attempts[-1]["db2_threshold"] and "analyst queries" in r.reason
