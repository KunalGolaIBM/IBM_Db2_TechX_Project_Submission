"""Db2 integration: the ledger's monthly range partitions and the materialized query tables behind the analytics
views. The views must give exactly what the GROUP BY over the base tables they replaced gave."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from test_db2_ledger import entry

from asof import db, ledger, schema, seed

pytestmark = pytest.mark.db2

# The view definitions before the MQTs, kept here as the reference the new views are checked against.
OLD_DECISION_STATS = (
    "SELECT CHANNEL, DECISION, REASON_CODE, COUNT(*) AS DECISIONS, INTEGER(AVG(LATENCY_MS)) AS AVG_LATENCY_MS, "
    "MIN(CREATED_AT) AS FIRST_AT, MAX(CREATED_AT) AS LAST_AT FROM ANSWER_LEDGER GROUP BY CHANNEL, DECISION, REASON_CODE "
    "ORDER BY CHANNEL, DECISION, REASON_CODE")
OLD_CLAIM_OUTCOMES = (
    "SELECT AREA, SUM(CASE WHEN VERDICT = 'SUPPORTED' THEN 1 ELSE 0 END), "
    "SUM(CASE WHEN VERDICT = 'CONTRADICTED' THEN 1 ELSE 0 END), SUM(CASE WHEN VERDICT = 'NOT_COVERED' THEN 1 ELSE 0 END), "
    "COUNT(*) FROM CLAIM_CITATION WHERE PASS_NO = 1 GROUP BY AREA ORDER BY AREA")
NEW_DECISION_STATS = "SELECT * FROM V_DECISION_STATS ORDER BY CHANNEL, DECISION, REASON_CODE"
NEW_CLAIM_OUTCOMES = "SELECT * FROM V_CLAIM_OUTCOMES_BY_AREA ORDER BY AREA"
SQL_PARTITION_OF = ("SELECT P.DATAPARTITIONNAME FROM ANSWER_LEDGER L JOIN SYSCAT.DATAPARTITIONS P "
                    "ON P.TABSCHEMA = CURRENT SCHEMA AND P.TABNAME = 'ANSWER_LEDGER' "
                    "AND P.SEQNO = DATAPARTITIONNUM(L.CREATED_AT) WHERE L.LEDGER_ID = ?")
SQL_DIRECT_INSERT = (
    "INSERT INTO ANSWER_LEDGER (LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED, "
    "DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION, LATENCY_MS, VERDICTS_JSON, "
    "PREV_HASH, ROW_HASH) VALUES (?, ?, ?, 'api', 'AURELIA-CSP', '2026-03-10', 'q', 'd', 'f', 'PASS', 'ALL_SUPPORTED', "
    "'m', 'p', 1, '{}', ?, ?)")


@pytest.fixture
def scratch(admin_conn, embeddings, settings):
    name = f"ASOF_P{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_documents(admin_conn, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    yield name
    schema.drop(admin_conn, name)


def _append_mix(settings, name: str) -> None:
    mix = [("api", "PASS", "ALL_SUPPORTED", 40), ("api", "PASS", "ALL_SUPPORTED", 61), ("chat", "ESCALATED", "NOT_COVERED", 7),
           ("chat", "CORRECTED", "CORRECTED_FROM_CLAUSES", 1999), ("eval", "ESCALATED", "ERROR_FAIL_CLOSED", 3),
           ("chat", "ESCALATED", "NOT_COVERED", 8)]
    with db.connection(settings, "app") as conn:
        for channel, decision, reason, latency in mix:
            ledger.append(conn, entry(channel=channel, decision=decision, reason_code=reason, latency_ms=latency), name)


def test_views_over_the_mqts_match_the_group_by_they_replaced(settings, admin_conn, scratch):
    _append_mix(settings, scratch)
    db.use_schema(admin_conn, scratch)
    assert db.query(admin_conn, NEW_DECISION_STATS) == db.query(admin_conn, OLD_DECISION_STATS)
    assert db.query(admin_conn, NEW_CLAIM_OUTCOMES) == db.query(admin_conn, OLD_CLAIM_OUTCOMES)
    stats = db.query(admin_conn, NEW_DECISION_STATS)
    assert len(stats) == 4 and sum(r[3] for r in stats) == 6
    assert ("api", "PASS", "ALL_SUPPORTED", 2, 50) == tuple(stats[0][:5])  # (40 + 61) / 2, truncated like AVG
    assert ("chat", "ESCALATED", "NOT_COVERED", 2, 7) == tuple(stats[2][:5])  # (7 + 8) / 2


def test_the_mqts_are_current_after_every_append(settings, admin_conn, scratch):
    db.use_schema(admin_conn, scratch)
    assert db.query(admin_conn, "SELECT COUNT(*) FROM MQT_DECISION_STATS")[0][0] == 0
    with db.connection(settings, "app") as conn:
        ledger.append(conn, entry(), scratch)
        db.use_schema(conn, scratch)
        assert db.query(conn, "SELECT DECISIONS FROM V_DECISION_STATS") == [(1,)]  # the runtime user, through the view
    admin_conn.commit()
    assert db.query(admin_conn, "SELECT SUM(CLAIMS) FROM MQT_CLAIM_OUTCOMES")[0][0] == 2


def test_rows_land_in_their_month_and_never_outside_a_partition(admin_conn, scratch):
    db.use_schema(admin_conn, scratch)
    cases = [(datetime(2025, 6, 1), "P_BEFORE_2026"), (datetime(2026, 3, 15, 12), None), (datetime(2027, 12, 31, 23, 59), None),
             (datetime(2031, 1, 1), "P_FROM_2028")]
    seen = []
    for n, (at, expected) in enumerate(cases, start=1):
        db.execute(admin_conn, SQL_DIRECT_INSERT, (n, str(uuid.uuid4()), at, "0" * 64, f"{n:064d}"))
        part = db.query(admin_conn, SQL_PARTITION_OF, (n,))[0][0].strip()
        seen.append(part)
        if expected:
            assert part == expected
    admin_conn.rollback()  # direct inserts are for this test only; nothing is committed
    assert len(set(seen)) == 4  # March 2026 and December 2027 have monthly partitions of their own
    parts = db.query(admin_conn, "SELECT COUNT(*) FROM SYSCAT.DATAPARTITIONS WHERE TABSCHEMA = ? AND TABNAME = 'ANSWER_LEDGER'",
                     (scratch,))[0][0]
    assert parts == 26  # 24 months of 2026 and 2027, plus the two open-ended partitions
    partitioned = {r[0].strip() for r in db.query(admin_conn, "SELECT DISTINCT INDNAME FROM SYSCAT.INDEXPARTITIONS "
                                                  "WHERE INDSCHEMA = ? AND TABNAME = 'ANSWER_LEDGER'", (scratch,))}
    assert partitioned == {"IX_LEDGER_CREATED", "IX_LEDGER_GROUP_CREATED"}  # the rest are global, IX_LEDGER_DECISION too


def test_db2_refuses_to_detach_a_ledger_partition(settings, admin_conn, scratch):
    """DETACH PARTITION would remove rows without the DELETE trigger. Db2 refuses it while CLAIM_CITATION's foreign
    key references the ledger (SQL0270N reason 92), so even the owner must first drop that constraint."""
    with db.connection(settings, "app") as conn:
        ledger.append(conn, entry(), scratch)
    db.use_schema(admin_conn, scratch)
    part = db.query(admin_conn, SQL_PARTITION_OF, (1,))[0][0].strip()
    assert part.startswith("PART")  # this month's partition
    with pytest.raises(db.DatabaseError) as refused:
        db.execute(admin_conn, f"ALTER TABLE {db.ident(scratch)}.ANSWER_LEDGER DETACH PARTITION {db.ident(part)} "
                               f"INTO {db.ident(scratch)}.DETACHED_ROWS")
    admin_conn.rollback()
    assert refused.value.sqlstate == "42997" and 'Reason code = "92"' in str(refused.value)
    assert db.query(admin_conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0] == 1


def test_a_pending_mqt_is_refreshed_so_appends_never_fail(settings, admin_conn, scratch):
    db.execute(admin_conn, f"SET INTEGRITY FOR {db.ident(scratch)}.MQT_DECISION_STATS OFF")
    admin_conn.commit()
    with db.connection(settings, "app") as conn, pytest.raises(db.DatabaseError):
        ledger.append(conn, entry(), scratch)  # Db2 refuses the insert while the MQT is pending: SQL0668N
    assert schema.refresh_pending_mqts(admin_conn, scratch) == ["MQT_DECISION_STATS"]
    with db.connection(settings, "app") as conn:
        assert ledger.append(conn, entry(), scratch).ledger_id == 1
        assert ledger.verify_chain(conn, scratch).status == "OK"
