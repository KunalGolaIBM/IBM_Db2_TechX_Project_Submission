"""Db2 workload management without a database: the SQL and wlm.py agree, and a threshold stop reads plainly."""

from __future__ import annotations

import re

import pytest
from fakes import ScriptedLLM
from test_askledger import COUNT_SQL, Recorder, sql

from asof import db, schema, wlm
from asof.schemas import LedgerAnswer


def _wlm_statements():
    return {st.name: st for st in schema.load_statements("ASOF") if st.source == "07_wlm.sql"}


def test_the_sql_and_wlm_py_hold_the_same_limits():
    sts = _wlm_statements()
    assert [st.kind for st in sts.values()] == ["role", "workload", "threshold", "threshold", "threshold"]
    assert "SESSION_USER ROLE ('ASOF_ANALYST')" in sts[wlm.WORKLOAD].sql
    conditions = {"ESTSQLCOST": "ESTIMATEDSQLCOST", "ROWSRET": "SQLROWSRETURNED", "TOTALTIME": "ACTIVITYTOTALTIME"}
    for limit in wlm.LIMITS:
        text = re.sub(r"\s+", " ", sts[limit.threshold].sql)
        unit = " SECONDS" if limit is wlm.TIME else ""
        assert f"FOR WORKLOAD {wlm.WORKLOAD} ACTIVITIES" in text, limit.threshold
        assert f"WHEN {conditions[limit.predicate]} > {limit.value}{unit} STOP EXECUTION" in text, limit.threshold
    assert wlm.TIME.value % 10 == 0  # Db2 takes this limit in multiples of 10 seconds (SQL0644N otherwise)


def test_the_workload_is_usable_only_by_the_analyst_role():
    grants = [st.sql for st in schema.load_statements("ASOF", grants=True) if "WORKLOAD" in st.sql]
    assert grants == ["GRANT USAGE ON WORKLOAD WL_ASOF_ANALYST TO ROLE ASOF_ANALYST"] and wlm.WORKLOAD == "WL_ASOF_ANALYST"


def _err(threshold: str, code: int) -> db.DatabaseError:
    return db.DatabaseError(f'Query failed: SQL4712N  The activity or request was stopped because the threshold '
                            f'"{threshold}" has been exceeded. Reason code: "{code}".', "5U026", -4712)


@pytest.mark.parametrize("limit, words", [(wlm.COST, "1,000,000 timerons"), (wlm.ROWS, "10,000 rows"),
                                          (wlm.TIME, "10 seconds")])
def test_each_threshold_reads_as_a_plain_refusal(limit, words):
    message = wlm.stopped(_err(limit.threshold, limit.reason_code))
    assert message.startswith("Db2 ") and words in message and limit.threshold in message


def test_other_errors_are_not_threshold_stops():
    assert wlm.stopped(db.DatabaseError("Query failed: SQL0952N  Processing was cancelled due to an interrupt.",
                                        "57014", -952)) is None
    assert "reason code 4" in wlm.stopped(_err("TH_OTHER", 4))


def test_ask_the_ledger_shows_a_threshold_stop_as_stopped_and_lets_the_model_try_once_more():
    stop = _err(wlm.COST.threshold, wlm.COST.reason_code)
    rec = Recorder(ScriptedLLM(sql=[sql(COUNT_SQL), sql(COUNT_SQL)]), results=[stop, stop])
    r = rec.ask("count everything against everything")
    assert (r.status, r.rows, len(rec.ran)) == ("STOPPED", [], 2)
    assert "timerons" in r.reason and all("timerons" in a["db2_threshold"] for a in r.attempts)
    rec = Recorder(ScriptedLLM(sql=[sql(COUNT_SQL), sql(COUNT_SQL)], answer=[LedgerAnswer(answer="ok")]),
                   results=[stop, (["DECISION", "N"], [["PASS", 1]], False)])
    assert rec.ask("decisions?").status == "ANSWERED"  # a cheaper second query runs
