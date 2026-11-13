"""The public demo's daily cap on live checks, in Db2 (10_demo_spend.sql): CLAIM_DEMO_CHECK admits atomically and
refuses at the cap with SQLSTATE 75097, sessions racing at the cap cannot both pass, and the runtime user changes
DEMO_SPEND only through the two procedures."""
from __future__ import annotations

import threading
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_api import FakeAssistant, FakeGate
from test_demo_live import NEW, LiveAssistant, LiveGate, ip

from asof import db, demolive
from asof.api import create_app
from asof.config import Settings

pytestmark = pytest.mark.db2


@pytest.fixture
def spend(admin_conn, test_schema, settings):
    """An empty DEMO_SPEND in the test schema, and a counter working as the runtime user."""
    def clear():
        db.use_schema(admin_conn, test_schema)
        db.execute(admin_conn, "DELETE FROM DEMO_SPEND")
        admin_conn.commit()

    clear()
    yield demolive.SpendCounter(lambda: db.connect(settings, "app"), test_schema)
    clear()


def db2_today(admin_conn) -> date:
    return db.query(admin_conn, "SELECT DATE(CURRENT TIMESTAMP - CURRENT TIMEZONE) FROM SYSIBM.SYSDUMMY1")[0][0]


def test_claims_count_up_to_the_cap_then_db2_refuses(spend, admin_conn):
    assert [spend.claim(3)[1] for _ in range(3)] == [1, 2, 3]
    with pytest.raises(db.DatabaseError) as err:
        spend.claim(3)
    assert err.value.sqlstate == demolive.CAP_REACHED
    row = spend.today()
    assert row is not None and row["day"] == db2_today(admin_conn) and row["checks"] == 3
    assert spend.claim(4)[1] == 4  # a higher cap admits more the same day


def test_a_lower_cap_refuses_and_the_day_never_counts_past_its_cap(spend, admin_conn, test_schema):
    for _ in range(3):
        spend.claim(5)
    with pytest.raises(db.DatabaseError) as err:
        spend.claim(2)
    assert err.value.sqlstate == demolive.CAP_REACHED
    db.use_schema(admin_conn, test_schema)
    used, cap = db.query(admin_conn, "SELECT CHECKS_USED, DAILY_CAP FROM DEMO_SPEND")[0]
    assert (used, cap) == (3, 5)
    with pytest.raises(db.DatabaseError) as err:  # CK_DEMO_SPEND_UNDER_CAP, even for the owner
        db.execute(admin_conn, "UPDATE DEMO_SPEND SET CHECKS_USED = 6")
    admin_conn.rollback()
    assert err.value.sqlstate == "23513"


@pytest.mark.parametrize("cap", [0, -1, 100001])
def test_a_cap_out_of_range_is_refused(spend, cap):
    with pytest.raises(db.DatabaseError) as err:
        spend.claim(cap)
    assert err.value.sqlstate == "75098"


def test_sessions_racing_at_the_cap_admit_exactly_the_cap(spend, settings):
    """Twelve sessions, each with its own connection, call CLAIM_DEMO_CHECK at the same moment with 5 left."""
    cap, n = 5, 12
    conns = [db.connect(settings, "app") for _ in range(n)]
    counters = [demolive.SpendCounter(lambda c=c: _Keep(c), spend.schema) for c in conns]
    barrier, results, lock = threading.Barrier(n), [], threading.Lock()

    def race(counter):
        barrier.wait()
        try:
            out = ("ok", counter.claim(cap)[1])
        except db.DatabaseError as exc:
            out = ("refused", exc.sqlstate)
        with lock:
            results.append(out)

    threads = [threading.Thread(target=race, args=(c,)) for c in counters]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    for c in conns:
        c.close()
    ok = sorted(v for k, v in results if k == "ok")
    assert ok == [1, 2, 3, 4, 5]
    assert [v for k, v in results if k == "refused"] == [demolive.CAP_REACHED] * (n - cap)
    assert spend.today()["checks"] == cap


def test_a_second_session_waits_for_the_first_and_then_sees_its_claim(spend, settings):
    """The deterministic form of the race: one check left, session A claims it and has not committed yet."""
    spend.claim(2)
    a, b = db.connect(settings, "app"), db.connect(settings, "app")
    try:
        db.use_schema(a, spend.schema)
        cur = a.cursor()
        cur.callproc("CLAIM_DEMO_CHECK", (2, date(1970, 1, 1), 0))  # not committed: A holds the row lock
        cur.close()
        outcome: list = []

        def claim_b():
            try:
                outcome.append(demolive.SpendCounter(lambda: _Keep(b), spend.schema).claim(2))
            except db.DatabaseError as exc:
                outcome.append(exc.sqlstate)

        t = threading.Thread(target=claim_b)
        t.start()
        time.sleep(1.5)
        assert t.is_alive() and outcome == []  # B queues on A's lock instead of reading the old count
        a.commit()
        t.join(30)
        assert outcome == [demolive.CAP_REACHED]
    finally:
        a.close()
        b.close()
    assert spend.today()["checks"] == 2


def test_usage_is_added_to_the_day_it_was_admitted_on(spend):
    day, _ = spend.claim(10)
    spend.record(day, 4, 3000, 400)
    spend.record(day, 2, 1000, 100)
    row = spend.today()
    assert (row["llm_calls"], row["input_tokens"], row["output_tokens"]) == (6, 4000, 500)


@pytest.mark.parametrize("usage", [(-1, 0, 0), (101, 0, 0), (1, -5, 0), (1, 0, 2_000_000)])
def test_impossible_usage_is_refused(spend, usage):
    day, _ = spend.claim(10)
    with pytest.raises(db.DatabaseError) as err:
        spend.record(day, *usage)
    assert err.value.sqlstate == "75098"


def test_usage_for_a_day_with_no_admitted_check_is_refused(spend):
    with pytest.raises(db.DatabaseError) as err:
        spend.record(date(2026, 1, 1), 1, 1, 1)
    assert err.value.sqlstate == "75098"


def test_the_runtime_user_changes_demo_spend_only_through_the_procedures(spend, settings):
    spend.claim(10)
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, spend.schema)
        for sql in ("UPDATE DEMO_SPEND SET CHECKS_USED = 0", "DELETE FROM DEMO_SPEND",
                    "INSERT INTO DEMO_SPEND (SPEND_DAY) VALUES (CURRENT DATE + 1 DAY)"):
            with pytest.raises(db.DatabaseError) as err:
                db.execute(conn, sql)
            conn.rollback()
            assert err.value.sqlstate == "42501", sql
    assert spend.today()["checks"] == 1


def test_only_the_runtime_user_holds_execute_and_nobody_holds_writes(admin_conn, test_schema, settings):
    rows = db.query(admin_conn, "SELECT R.ROUTINENAME, A.GRANTEE FROM SYSCAT.ROUTINEAUTH A JOIN SYSCAT.ROUTINES R "
                                "ON R.ROUTINESCHEMA = A.SCHEMA AND R.SPECIFICNAME = A.SPECIFICNAME "
                                "WHERE A.SCHEMA = ? AND A.EXECUTEAUTH IN ('Y', 'G') "
                                "AND R.ROUTINENAME IN ('CLAIM_DEMO_CHECK', 'RECORD_DEMO_SPEND')", (test_schema,))
    grantees = {(r.strip(), g.strip()) for r, g in rows}
    owner = settings.db2_admin_user.upper()
    assert {g for _, g in grantees} - {owner} == {settings.asof_app_user.upper()}
    assert {r for r, _ in grantees} == {"CLAIM_DEMO_CHECK", "RECORD_DEMO_SPEND"}
    writers = db.query(admin_conn, "SELECT GRANTEE FROM SYSCAT.TABAUTH WHERE TABSCHEMA = ? AND TABNAME = 'DEMO_SPEND' "
                                   "AND (INSERTAUTH <> 'N' OR UPDATEAUTH <> 'N' OR DELETEAUTH <> 'N') AND GRANTEE <> ?",
                       (test_schema, owner))
    assert writers == []


def test_the_api_stops_live_checks_at_the_db2_cap(spend, test_schema, settings, monkeypatch):
    """The whole path: the API admits live checks through Db2's counter until the cap, then refuses with the reason."""
    demo = Settings(asof_public_demo=True, llm_provider="replay", asof_demo_live=True, openrouter_api_key=None)
    seen: list = []
    from test_demo_live import LiveClient

    live = demolive.LiveChecks(model="openrouter:test/model", cap=2, per_minute=10, per_day=10, available=True,
                               client=LiveClient, spend=spend, gate=lambda m: LiveGate(m, seen),
                               assistant=lambda m: LiveAssistant(m, []), recorded=demolive.RecordedInputs([]))
    c = TestClient(create_app(demo, gate=FakeGate(), assistant=FakeAssistant(), schema=test_schema, live=live),
                   client=("127.0.0.1", 51000), raise_server_exceptions=False)
    codes = [c.post("/api/gate", json={**NEW, "draft_answer": f"Yes, {i} cats."}, headers=ip(f"203.0.113.{i}")).status_code
             for i in range(3)]
    assert codes == [200, 200, 503] and len(seen) == 2
    row = spend.today()
    assert (row["checks"], row["llm_calls"], row["input_tokens"], row["output_tokens"]) == (2, 2, 240, 60)
    h = c.get("/healthz").json()
    assert h["live_checks"] == "paused" and "limit of 2 live checks" in h["public_demo_notice"]


class _Keep:
    """A connection whose close() is a no-op, so a test can pass the same session to several calls."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass
