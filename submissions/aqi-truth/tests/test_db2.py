"""Run against a real Db2 loaded with the Sep-Dec 2025 data (or the sample in data/sample)."""
import datetime as dt, os
import pytest
import ibm_db_dbi
from conftest import needs_db2

pytestmark = needs_db2

def one(conn, sql, params=()):
    cur = conn.cursor(); cur.execute(sql, params); return cur.fetchone()

def test_sub_index_matches_cpcb_breakpoints(conn):
    # CPCB PM2.5: 0-30 -> 0-50, 31-60 -> 51-100, 61-90 -> 101-200
    assert one(conn, "VALUES AQ.SUB_INDEX('pm25', 30)")[0] == 50
    assert one(conn, "VALUES AQ.SUB_INDEX('pm25', 60)")[0] == 100
    assert one(conn, "VALUES AQ.SUB_INDEX('pm25', 0)")[0] == 0

def test_golden_path_refusal_chandni_chowk_23_oct(conn):
    """Monitor sent only implausible zeros after 14:00: CPCB rules give no AQI, a plain average still gives one."""
    cur = conn.cursor()
    out = cur.callproc("AQ.COMPUTE_AQI_AUDITED", (11603, dt.date(2025, 10, 23), 0))
    run_id = out[2]
    status, aqi, naive = one(conn, "SELECT STATUS, AQI, NAIVE_AQI FROM AQ.VERDICT WHERE RUN_ID = ?", (run_id,))
    assert status == "NOT_COMPUTABLE" and aqi is None and naive is not None
    failed = one(conn, "SELECT COUNT(*) FROM AQ.EVIDENCE WHERE RUN_ID = ? AND PASSED = 0", (run_id,))[0]
    assert failed >= 1
    conn.rollback()      # leave the live audit as it was

@pytest.mark.parametrize("stmt", ["UPDATE AQ.EVIDENCE SET PASSED = 1 WHERE PASSED = 0",
                                  "DELETE FROM AQ.EVIDENCE",
                                  "UPDATE AQ.VERDICT SET AQI = 50"])
def test_ledger_is_append_only(conn, stmt):
    cur = conn.cursor()
    with pytest.raises(Exception) as e:
        cur.execute(stmt)
    conn.rollback()
    assert "75001" in str(e.value)

def test_reader_can_only_see_the_two_views(reader_conn):
    cur = reader_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM AQ.V_DAY"); assert cur.fetchone()[0] > 0
    for t in ("AQ.READING", "AQ.VERDICT", "AQ.EVIDENCE", "AQ.ASK_LOG"):
        with pytest.raises(Exception) as e:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
        assert "SQL0551N" in str(e.value) or "42501" in str(e.value)

def test_reading_keeps_history_when_a_value_is_revised(conn):
    """System-period temporal table: an overwritten reading stays queryable FOR SYSTEM_TIME AS OF."""
    cur = conn.cursor()
    sid, param, ts, val = one(conn, "SELECT STATION_ID, PARAM, TS, VALUE FROM AQ.READING FETCH FIRST 1 ROW ONLY")
    before = one(conn, "VALUES CURRENT TIMESTAMP")[0]
    cur.execute("UPDATE AQ.READING SET VALUE = VALUE + 1 WHERE STATION_ID=? AND PARAM=? AND TS=?", (sid, param, ts))
    old = one(conn, "SELECT VALUE FROM AQ.READING FOR SYSTEM_TIME AS OF ? WHERE STATION_ID=? AND PARAM=? AND TS=?",
              (before, sid, param, ts))
    conn.rollback()
    assert float(old[0]) == float(val)

def test_explanation_guard_rejects_invented_numbers(conn, monkeypatch):
    import explain
    run_id = one(conn, "SELECT MAX(RUN_ID) FROM AQ.VERDICT WHERE STATION_ID = 11603 AND DAY = '2025-10-23'")[0]
    monkeypatch.setattr(explain, "nearest_rules", lambda c, t, k=3: [("CPCB-24H-16", "rule text")])
    monkeypatch.setattr(explain, "generate", lambda *a, **k: "The AQI was 999 and people should stay indoors.")
    monkeypatch.setattr(conn, "commit", lambda: None)     # keep the test's explanation row out of the live table
    out = explain.explain(conn, run_id)
    conn.rollback()
    assert out["model"].startswith("template") and "999" not in out["text"]

def test_question_log_is_append_only(conn):
    cur = conn.cursor()     # a row first, so the delete has something to hit even on an empty log
    cur.execute("INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES ('test', 'test', 'ANSWERED', 'GUARD')")
    with pytest.raises(Exception) as e:
        cur.execute("DELETE FROM AQ.ASK_LOG")
    conn.rollback()
    assert "75001" in str(e.value)

def test_verdicts_cannot_be_deleted_even_by_the_owner(conn):
    with pytest.raises(Exception) as e:
        conn.cursor().execute("DELETE FROM AQ.VERDICT WHERE RUN_ID = (SELECT MIN(RUN_ID) FROM AQ.VERDICT)")
    conn.rollback()
    assert "75001" in str(e.value)

@pytest.mark.parametrize("stmt", ["TRUNCATE TABLE AQ.EVIDENCE IMMEDIATE", "TRUNCATE TABLE AQ.RECEIPT IMMEDIATE",
                                  "DELETE FROM AQ.ASK_LOG", "UPDATE AQ.EXPLANATION SET GROUNDED = 1"])
def test_app_id_cannot_truncate_or_rewrite(app_conn, stmt):
    """Triggers do not fire on TRUNCATE; the app's ID simply holds no privilege that allows it."""
    with pytest.raises(Exception) as e:
        app_conn.cursor().execute(stmt)
    app_conn.rollback()
    assert "42501" in str(e.value) or "75001" in str(e.value)

def test_app_id_can_append_to_question_log(app_conn):
    app_conn.cursor().execute("INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES ('test', 'test', 'ANSWERED', 'GUARD')")
    app_conn.rollback()

def test_row_permission_gives_different_rows_to_different_ids(conn, app_conn):
    """RCAC: the same SELECT, run by the owner (AQAUDITOR role) and by the app, returns different rows."""
    q = "SELECT COUNT(*) FROM AQ.VERDICT WHERE STATION_ID = 8118"
    assert one(conn, q)[0] > 0 and one(app_conn, q)[0] == 0

def test_question_box_query_times_out():
    import ask
    old = ask.TIMEOUT_S; ask.TIMEOUT_S = 2
    try:
        # Three views (the checker's limit) joined on inequality: a near cross product of ~10^9 rows even on the CI sample.
        r = ask.run("SELECT COUNT(*) FROM AQ.V_CHECK A JOIN AQ.V_CHECK B ON A.PARAM <> B.PARAM JOIN AQ.V_CHECK C ON B.PARAM <> C.PARAM")
    finally:
        ask.TIMEOUT_S = old
    assert r["outcome"] == "DB2_ERROR" and "cancelled" in r["why"]

def test_last_hour_of_the_day_is_built(conn):
    """The hour 23:00-24:00 (ending at midnight) belongs to the day and must be in the hourly layer."""
    assert one(conn, "SELECT COUNT(*) FROM AQ.HOURLY WHERE HR = '2025-11-01 00:00:00'")[0] > 0

def test_every_current_verdict_has_a_receipt_and_the_chain_is_intact(conn):
    assert one(conn, "SELECT COUNT(*) FROM AQ.V_DAY D WHERE NOT EXISTS (SELECT 1 FROM AQ.RECEIPT R WHERE R.RUN_ID = D.RUN_ID)")[0] == 0
    n, broken = one(conn, "SELECT RECEIPTS, BROKEN FROM AQ.V_RECEIPT_CHAIN")
    assert n > 0 and broken == 0

def test_receipt_verifies_and_a_tampered_reading_is_caught(app_conn):
    """Overwriting one input reading makes the receipt fail (old value comes back from history); rolling back restores MATCH."""
    assert one(app_conn, "SELECT RESULT FROM TABLE(AQ.VERIFY_RECEIPT(11603, '2025-10-23')) X")[0] == "MATCH"
    out = app_conn.cursor().callproc("AQ.TAMPER_TEST", (11603, dt.date(2025, 10, 23), "", "", "", ""))
    touched, during, detail, after = out[2:]
    assert during == "DATA_CHANGED" and "from history" in detail and after == "MATCH"

def test_receipts_are_append_only(conn):
    with pytest.raises(Exception) as e:
        conn.cursor().execute("UPDATE AQ.RECEIPT SET AQI = 1 WHERE RECEIPT_ID = (SELECT MIN(RECEIPT_ID) FROM AQ.RECEIPT)")
    conn.rollback()
    assert "75001" in str(e.value)
