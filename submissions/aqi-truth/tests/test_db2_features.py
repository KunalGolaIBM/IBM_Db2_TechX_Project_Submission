"""The newer Db2 pieces, tested the way scripts/db2_evidence.py proves them: column mask, MQT query rewrite,
partition elimination, least-privilege refusals and the receipt tamper test. Runs against the sample in data/sample."""
import pytest
from conftest import needs_db2

pytestmark = needs_db2
AT = chr(64)        # the at sign, spelled out like in sql/09_mqt_mask.sql
PROBE = f"Email me at someone{AT}example.com or call 9876543210: is ITO severe?"

def one(conn, sql, params=()):
    cur = conn.cursor(); cur.execute(sql, params); return cur.fetchone()

def asked(conn, qnorm):
    """Log the probe question in this transaction and read it back through the mask."""
    cur = conn.cursor()
    cur.execute("INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES (?, ?, 'REFUSED', 'GUARD')", (PROBE, qnorm))
    cur.execute("SELECT QUESTION FROM AQ.ASK_LOG WHERE QNORM = ? ORDER BY ID DESC FETCH FIRST 1 ROW ONLY", (qnorm,))
    return cur.fetchone()

# Column mask on AQ.ASK_LOG.QUESTION

def test_column_mask_redacts_contact_details_for_the_app_id(app_conn):
    try:
        q = asked(app_conn, "pytest-mask-app")[0]
    finally:
        app_conn.rollback()
    assert q == "Email me at [e-mail removed] or call [number removed]: is ITO severe?"

def test_column_mask_shows_the_auditor_the_stored_text(conn):
    """The owner holds the AQAUDITOR role: same table, same SELECT, unmasked text. The mask changes output only."""
    try:
        q = asked(conn, "pytest-mask-owner")[0]
    finally:
        conn.rollback()
    assert q == PROBE

def test_column_access_control_is_active(conn):
    control = one(conn, "SELECT CONTROL FROM SYSCAT.TABLES WHERE TABSCHEMA = 'AQ' AND TABNAME = 'ASK_LOG'")[0]
    enabled = one(conn, "SELECT ENABLE FROM SYSCAT.CONTROLS WHERE CONTROLSCHEMA = 'AQ' AND CONTROLNAME = 'ASK_QUESTION_MASK'")[0]
    assert control.strip() == "C" and enabled == "Y"

# Materialized query table AQ.MQT_READING_DAY

STATION_DAY_COUNT = "SELECT STATION_ID, DATE(TS) AS DAY, COUNT(*) FROM AQ.READING GROUP BY STATION_ID, DATE(TS)"

@pytest.fixture
def explain(conn):
    """EXPLAIN a statement and return the AQ tables its access plan reads (not just the objects it considered)."""
    cur = conn.cursor()
    try:
        cur.execute("CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN', 'C', NULL, CURRENT SCHEMA)"); conn.commit()
    except Exception:
        conn.rollback()     # explain tables already exist
    def plan(sql, refresh_age="0"):
        cur.execute(f"SET CURRENT REFRESH AGE {refresh_age}")
        cur.execute("DELETE FROM EXPLAIN_INSTANCE"); cur.execute("EXPLAIN PLAN FOR " + sql)
        cur.execute("SELECT DISTINCT RTRIM(OBJECT_NAME) FROM EXPLAIN_STREAM WHERE OBJECT_SCHEMA = 'AQ' AND OBJECT_NAME IS NOT NULL")
        tabs = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT ARGUMENT_TYPE, RTRIM(ARGUMENT_VALUE) FROM EXPLAIN_ARGUMENT WHERE ARGUMENT_TYPE IN ('DPNUMPRT')")
        args = dict((k.strip(), v) for k, v in cur.fetchall())
        return tabs, args
    yield plan
    cur.execute("SET CURRENT REFRESH AGE 0"); conn.rollback()

def test_optimizer_answers_a_base_table_query_from_the_mqt(explain):
    tabs, _ = explain(STATION_DAY_COUNT, refresh_age="ANY")
    assert tabs == {"MQT_READING_DAY"}

def test_without_refresh_age_any_the_base_table_is_read(explain):
    """REFRESH DEFERRED: the MQT may lag the base table, so Db2 only uses it when the session allows stale data."""
    tabs, _ = explain(STATION_DAY_COUNT, refresh_age="0")
    assert tabs == {"READING"}

def test_mqt_matches_the_base_table_for_a_station_day(conn):
    cur = conn.cursor()
    cur.execute("SELECT PARAM, COUNT(*), COUNT(VALUE) FROM AQ.READING WHERE STATION_ID = 11603 AND DATE(TS) = '2025-10-23' GROUP BY PARAM ORDER BY 1")
    base = [(p.strip(), n, v) for p, n, v in cur.fetchall()]
    cur.execute("SELECT PARAM, N_ROWS, N_VALUES FROM AQ.MQT_READING_DAY WHERE STATION_ID = 11603 AND DAY = '2025-10-23' ORDER BY 1")
    mqt = [(p.strip(), n, v) for p, n, v in cur.fetchall()]
    assert base and mqt == base

# Range partitioning

def test_one_day_query_reads_one_monthly_partition(explain):
    tabs, args = explain("SELECT AVG(VALUE) FROM AQ.READING WHERE TS >= '2025-10-21 00:00:00' AND TS < '2025-10-22 00:00:00'")
    assert tabs == {"READING"} and args.get("DPNUMPRT") == "1"

# Least privilege beyond SELECT: the refusals come from Db2 (SQLSTATE 42501), not from the app

@pytest.mark.parametrize("stmt", ["INSERT INTO AQ.ASK_LOG (QUESTION, QNORM, OUTCOME, SOURCE) VALUES ('x', 'x', 'ANSWERED', 'GUARD')",
                                  "DELETE FROM AQ.VERDICT"])
def test_reader_id_cannot_write(reader_conn, stmt):
    with pytest.raises(Exception) as e:
        reader_conn.cursor().execute(stmt)
    reader_conn.rollback()
    assert "42501" in str(e.value)

def test_app_id_cannot_forge_a_verdict(app_conn):
    """Verdicts are written only by the audit procedures; the app's ID cannot insert one."""
    with pytest.raises(Exception) as e:
        app_conn.cursor().execute("INSERT INTO AQ.VERDICT (STATION_ID, DAY) VALUES (11603, '2025-10-23')")
    app_conn.rollback()
    assert "42501" in str(e.value)

# Receipts

def test_tamper_test_leaves_no_trace(conn, app_conn):
    """AQ.TAMPER_TEST edits a reading inside a savepoint and rolls it back: no history row and no reading change survive."""
    import datetime as dt
    hist = one(conn, "SELECT COUNT(*) FROM AQ.READING_HIST")[0]
    total = one(conn, "SELECT SUM(VALUE) FROM AQ.READING WHERE STATION_ID = 11603 AND DATE(TS) = '2025-10-23'")[0]
    out = app_conn.cursor().callproc("AQ.TAMPER_TEST", (11603, dt.date(2025, 10, 23), "", "", "", ""))
    app_conn.commit()
    assert out[3] == "DATA_CHANGED" and out[5] == "MATCH"
    conn.rollback()     # new snapshot for the owner's reads
    assert one(conn, "SELECT COUNT(*) FROM AQ.READING_HIST")[0] == hist
    assert one(conn, "SELECT SUM(VALUE) FROM AQ.READING WHERE STATION_ID = 11603 AND DATE(TS) = '2025-10-23'")[0] == total
