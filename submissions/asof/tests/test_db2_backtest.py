"""Backtest mode through Db2: the shipped sample in replay mode, the exposure report's exact numbers, the procedures'
refusals, the append-only rules, and backtest decisions kept out of the live screens."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_api import FakeAssistant

from asof import backtest, db, ledger, policy, replay, review, schema, seed
from asof.api import create_app
from asof.gate import Gate, GateRequest

pytestmark = pytest.mark.db2

# The ledger's channel check as it was before backtests.
SQL_OLD_CHECK = ("ALTER TABLE ANSWER_LEDGER DROP CONSTRAINT CK_LEDGER_CHANNEL ADD CONSTRAINT CK_LEDGER_CHANNEL "
                 "CHECK (CHANNEL IN ('chat', 'email', 'faq', 'api', 'eval', 'demo', 'agent'))")


def _fresh(admin_conn, embeddings, settings, prefix: str) -> str:
    name = f"{prefix}{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                            analyst_user=settings.asof_analyst_user, review_user=settings.asof_review_user)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    return name


@pytest.fixture(scope="module")
def bt(admin_conn, embeddings, settings):
    name = _fresh(admin_conn, embeddings, settings, "ASOF_B")
    pool = db.ConnectionPool(settings, "app")
    gate = Gate(replay.ReplayLLM(replay.Recording.load()), embeddings, pool.connect, name)
    # One live decision first, so the live screens have something the backtest must not add to.
    live = gate.check(GateRequest("My grandmother just died. Can I get the bereavement fare after I travel?",
                                  backtest.sample_upload().rows[0].draft, date(2026, 3, 10), "AURELIA-CSP", "chat"))
    run_id, status = backtest.run_upload(gate, pool.connect, backtest.sample_upload(), "auto", 1800, name, sample=True)
    with db.connection(settings, "app") as conn:
        rep = backtest.report(conn, run_id, name)
    yield SimpleNamespace(schema=name, gate=gate, connect=pool.connect, run_id=run_id, status=status, report=rep,
                          live=live)
    pool.close()
    schema.drop(admin_conn, name)


def call(conn, name: str, params: tuple):
    return backtest._call(conn, name, params)


def refused(conn, name: str, params: tuple) -> str | None:
    with pytest.raises(db.DatabaseError) as err:
        call(conn, name, params)
    return err.value.sqlstate


def test_the_sample_replays_to_these_exact_numbers(bt):
    rep = bt.report
    run = rep["run"]
    assert (bt.status, run["state"], run["rows"], run["items"], run["sample"]) == ("DONE", "DONE", 20, 20, True)
    assert run["model"].startswith("replay:") and run["source_name"] == "fictional-backtest-sample.csv"
    assert [run[k] for k in ("wrong", "unconfirmed", "ok", "failed", "skipped", "unaccounted")] == [7, 5, 8, 0, 0, 0]
    assert [i["outcome"] for i in rep["items"]] == [
        "WRONG", "OK", "WRONG", "OK", "WRONG", "OK", "WRONG", "WRONG", "OK", "OK",
        "OK", "UNCONFIRMED", "UNCONFIRMED", "UNCONFIRMED", "UNCONFIRMED", "OK", "WRONG", "OK", "WRONG", "UNCONFIRMED"]
    assert rep["contradicted_claims"] == 12
    assert rep["money"] == {"computed_claims": 2, "not_computable_claims": 10, "total_abs_usd": 15.0,
                            "customer_favour_usd": 5.0, "customer_favour_claims": 1,
                            "company_favour_usd": 10.0, "company_favour_claims": 1}
    assert [(c["clause_id"], c["version"], str(c["from"]), str(c["to"]), c["wrong_answers"], c["contradicted_claims"],
             c["abs_usd"]) for c in rep["by_clause"]] == [
        ("BRV-002", "v1", "2026-01-01", "2026-05-01", 2, 5, 0.0),
        ("OVD-001", "v2", "2026-07-01", "9999-12-31", 1, 1, 10.0),
        ("BAG-001", "v2", "2026-06-01", "9999-12-31", 1, 1, 5.0),
        ("CHG-004", "v1", "2026-01-01", "9999-12-31", 1, 2, 0.0),
        ("FRV-001", "v1", "2026-01-01", "2026-08-01", 1, 1, 0.0),
        ("PET-001", "v1", "2026-01-01", "9999-12-31", 1, 2, 0.0)]
    assert [(x["row"], x["abs_usd"]) for x in rep["costliest"]] == [(19, 10.0), (5, 5.0)]
    overdraft, bag = (x["contradicted"][0] for x in rep["costliest"])
    assert (overdraft["rule_key"], overdraft["stated_usd"], overdraft["policy_usd"], overdraft["favours"]) == \
        ("overdraft_fee_usd", 35.0, 25.0, "COMPANY")  # told $35 in August; v2 charges $25 from 1 July
    assert (bag["rule_key"], bag["stated_usd"], bag["policy_usd"], bag["favours"]) == \
        ("first_bag_fee_usd", 35.0, 40.0, "CUSTOMER")  # told $35 in July; v2 charges $40 from 1 June
    assert rep["not_computable"] == [{"reason": backtest.NO_AMOUNT, "claims": 8},
                                     {"reason": backtest.CLAUSE_NO_AMOUNT, "claims": 1},
                                     {"reason": backtest.SAME_AMOUNT, "claims": 1}]


def test_every_row_is_a_hash_chained_ledger_decision_on_channel_backtest(bt, settings):
    with db.connection(settings, "app") as conn:
        assert ledger.verify_chain(conn, bt.schema).status == "OK"
        db.use_schema(conn, bt.schema)
        rows = db.query(conn, "SELECT I.ROW_NO, L.CHANNEL, L.AS_OF_DATE, I.CUSTOMER_DATE, L.VERDICTS_JSON "
                              "FROM BACKTEST_ITEM I JOIN ANSWER_LEDGER L ON L.LEDGER_ID = I.LEDGER_ID "
                              "WHERE I.RUN_ID = ? ORDER BY I.ROW_NO", (bt.run_id,))
    assert len(rows) == 20
    sample = backtest.sample_upload().rows
    for (row_no, channel, as_of, customer_date, verdicts), src in zip(rows, sample, strict=True):
        assert (channel.strip(), as_of, customer_date) == ("backtest", src.customer_date, src.customer_date)
        assert json.loads(verdicts)["backtest"] == {"run_id": bt.run_id, "row": row_no, "source_channel": src.channel}


def test_backtest_decisions_stay_out_of_analytics_the_inbox_and_change_impact(bt, settings):
    with db.connection(settings, "app") as conn:
        stats = policy.analytics(conn, bt.schema)
        queue = review.queue(conn, bt.schema)
        impact = policy.change_impact(conn, "BRV-002", bt.schema)
        db.use_schema(conn, bt.schema)
        live_claims = db.query(conn, "SELECT COUNT(*) FROM CLAIM_CITATION WHERE LEDGER_ID = ? AND PASS_NO = 1",
                               (bt.live.ledger_id,))[0][0]
    assert [(d["decision"], d["count"]) for d in stats["decisions"]] == [("CORRECTED", 1)]  # the one live check
    assert stats["backtest_decisions"] == 20 and stats["replayed_decisions"] == 1
    assert sum(a["claims"] for a in stats["areas"]) == live_claims > 0
    assert sum(stats["rule_checks"][k] for k in ("match", "mismatch", "not_applicable")) == live_claims
    assert queue["counts"]["open"] == 0  # five backtest decisions were held: nobody is waiting for them
    assert {int(r["ref_id"]) for r in impact if r["kind"] == "ANSWER"} == {bt.live.ledger_id}


def test_the_api_lists_runs_serves_the_report_and_runs_an_upload(bt, settings, embeddings):
    app = create_app(settings, gate=bt.gate, assistant=FakeAssistant(), schema=bt.schema,
                     backtest_launch=lambda work: work())
    c = TestClient(app)
    listed = c.get("/api/backtests").json()
    assert listed["sample_run_id"] == bt.run_id and listed["runs"][0]["run_id"] == bt.run_id
    assert c.get(f"/api/backtests/{bt.run_id}").json()["money"]["total_abs_usd"] == 15.0
    lines = backtest.SAMPLE_CSV.read_text(encoding="utf-8").splitlines(keepends=True)
    two = "".join([lines[0], lines[5], lines[6]]).encode("utf-8")  # the July bag fee: $35 (stale), then $40
    r = c.post("/api/backtests?name=july.csv", content=two, headers={"content-type": "text/csv"})
    assert r.status_code == 202
    rep = c.get(f"/api/backtests/{r.json()['run_id']}").json()
    assert (rep["run"]["state"], rep["run"]["wrong"], rep["run"]["ok"], rep["run"]["sample"]) == ("DONE", 1, 1, False)
    assert rep["money"]["total_abs_usd"] == 5.0 and rep["items"][1]["final_answer"].startswith("The first checked bag")


def test_the_procedures_refuse_what_does_not_belong(bt, settings):
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, bt.schema)
        start = ("t.csv", "a" * 64, 2, "AURELIA-CSP", "m", 0, 600, 660, "", 0)
        assert refused(conn, "START_BACKTEST", ("t.csv", "a" * 64, 2, "OTHER-AIRLINE", "m", 0, 600, 660, "", 0)) == "75071"
        assert refused(conn, "START_BACKTEST", ("t.csv", "a" * 64, 2, "auto", "m", 0, 0, 660, "", 0)) == "75079"
        assert refused(conn, "START_BACKTEST", ("t.csv", "a" * 64, 501, "auto", "m", 0, 600, 660, "", 0)) == "23513"
        assert refused(conn, "START_BACKTEST", ("t.csv", "not-hex" + "a" * 57, 2, "auto", "m", 0, 600, 660, "", 0)) \
            == "23513"
        run = int(call(conn, "START_BACKTEST", start)[-1])
        other = bt.report["items"][0]["ledger_id"]  # the sample run's row 1
        item = (run, 1, date(2026, 3, 10), "chat", "AURELIA-CSP")
        assert refused(conn, "ADD_BACKTEST_ITEM", (run, 3, date(2026, 3, 10), "chat", "", 0, "RUN_DEADLINE", "", "")) \
            == "75073"
        assert refused(conn, "ADD_BACKTEST_ITEM", (*item, other, "", "", " " * 12)) == "75074"
        assert refused(conn, "ADD_BACKTEST_ITEM", (run, 1, date(2026, 3, 10), "chat", "", 0, "WHATEVER", "", " " * 12)) \
            == "75079"
        assert call(conn, "ADD_BACKTEST_ITEM", (run, 1, date(2026, 3, 10), "chat", "", 0, "RUN_DEADLINE", "x",
                                                " " * 12))[-1].strip() == "SKIPPED"
        assert refused(conn, "FINISH_BACKTEST", (run, "DONE", "")) == "75078"  # row 2 has no outcome
        assert refused(conn, "FINISH_BACKTEST", (run, "MAYBE", "")) == "75079"
        call(conn, "ADD_BACKTEST_ITEM", (run, 2, date(2026, 3, 10), "email", "", 0, "RUN_STOPPED", "x", " " * 12))
        call(conn, "FINISH_BACKTEST", (run, "STOPPED", "a test"))
        assert refused(conn, "FINISH_BACKTEST", (run, "DONE", "")) == "75072"
        assert refused(conn, "ADD_BACKTEST_ITEM", (run, 2, date(2026, 3, 10), "chat", "", 0, "RUN_DEADLINE", "", "")) \
            == "75072"
        assert refused(conn, "ADD_BACKTEST_COST", (bt.run_id, 5, 1, "first_bag_fee_usd", Decimal("1"), "n" * 12,
                                                   Decimal(0))) == "75075"  # the sample run is finished


def test_db2_reads_the_policy_amount_itself_and_refuses_a_bad_key(bt, settings):
    """A running run with one wrong row (the July bag fee), then every way ADD_BACKTEST_COST can be misused."""
    sample = backtest.sample_upload()
    row = replace(sample.rows[4], row_no=1)
    runner = backtest.Backtest(bt.gate, bt.connect, bt.schema)
    run = runner.start(backtest.Upload("one.csv", sample.sha256, [row]), "AURELIA-CSP", 600)
    result, doc = runner.check_row(run, row, "AURELIA-CSP", None)
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, bt.schema)
        out = call(conn, "ADD_BACKTEST_ITEM", (run, 1, date(2026, 7, 15), "chat", doc, result.ledger_id, "", "",
                                               " " * 12))
        assert out[-1].strip() == "WRONG"
        cost = (run, 1, 1)
        assert refused(conn, "ADD_BACKTEST_COST", (run, 1, 7, "first_bag_fee_usd", Decimal(35), "x" * 12, Decimal(0))) \
            == "75076"
        for key in ("first_bag_fee_usd') OR 1=1 --", "pet_fee_usd", "max_no_fee_overdraft_usd", "first_bag_fee",
                    "First_Bag_Fee_USD"):
            assert refused(conn, "ADD_BACKTEST_COST", (*cost, key, Decimal(35), "x" * 12, Decimal(0))) == "75077", key
        assert refused(conn, "ADD_BACKTEST_COST", (*cost, "first_bag_fee_usd", Decimal(-1), "x" * 12, Decimal(0))) \
            == "75077"
        assert refused(conn, "ADD_BACKTEST_COST", (*cost, "", Decimal(0), "too short", Decimal(0))) == "75077"
        out = call(conn, "ADD_BACKTEST_COST", (*cost, "first_bag_fee_usd", Decimal("35.00"), "", Decimal(0)))
        assert Decimal(out[-1]) == Decimal("40.00")  # BAG-001 v2's RULE_JSON, read by JSON_VALUE inside the procedure
        assert refused(conn, "ADD_BACKTEST_COST", (*cost, "first_bag_fee_usd", Decimal(35), "", Decimal(0))) == "23505"
        rows = db.query(conn, "SELECT STATUS, POLICY_USD, DIFF_USD, FAVOURS, NOTE FROM BACKTEST_COST WHERE RUN_ID = ?",
                        (run,))
        assert [(s.strip(), p, d, f.strip(), n) for s, p, d, f, n in rows] == [
            ("COMPUTED", Decimal("40.00"), Decimal("-5.00"), "CUSTOMER", "one occurrence")]
        call(conn, "FINISH_BACKTEST", (run, "DONE", ""))


def test_nothing_writes_to_the_backtest_tables_but_the_procedures(bt, settings, admin_conn):
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, bt.schema)
        for sql in ("UPDATE BACKTEST_ITEM SET OUTCOME = 'OK'", "DELETE FROM BACKTEST_COST",
                    "UPDATE BACKTEST_RUN SET STATUS = 'DONE'",
                    "INSERT INTO BACKTEST_RUN (SOURCE_NAME, SOURCE_SHA256, ROW_COUNT, DOC_ID, MODEL_INFO, DEADLINE_AT, "
                    "STALE_AFTER_S) VALUES ('x', 'x', 1, 'auto', 'm', CURRENT TIMESTAMP, 60)"):
            with pytest.raises(db.DatabaseError) as err:
                db.execute(conn, sql)
            conn.rollback()
            assert err.value.sqlstate == "42501", sql
    db.use_schema(admin_conn, bt.schema)
    for sql, params in (("UPDATE BACKTEST_ITEM SET OUTCOME = 'OK' WHERE RUN_ID = ?", (bt.run_id,)),
                        ("DELETE FROM BACKTEST_COST WHERE RUN_ID = ?", (bt.run_id,)),
                        ("DELETE FROM BACKTEST_RUN WHERE RUN_ID = ?", (bt.run_id,)),
                        ("UPDATE BACKTEST_RUN SET NOTE = 'edited' WHERE RUN_ID = ?", (bt.run_id,))):
        with pytest.raises(db.DatabaseError) as err:  # even the owner: the triggers say no
            db.execute(admin_conn, sql, params)
        admin_conn.rollback()
        assert err.value.sqlstate == "75001", sql


def test_a_run_that_stopped_making_progress_reads_as_interrupted(bt, settings, admin_conn):
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, bt.schema)
        run = int(call(conn, "START_BACKTEST", ("t.csv", "b" * 64, 3, "auto", "m", 0, 600, 60, "", 0))[-1])
        state = "SELECT STATE FROM V_BACKTEST_RUNS WHERE RUN_ID = ?"
        assert db.query(conn, state, (run,))[0][0].strip() == "RUNNING"
        db.use_schema(admin_conn, bt.schema)  # as if its process died two hours ago
        db.execute(admin_conn, "UPDATE BACKTEST_RUN SET LAST_PROGRESS_AT = CURRENT TIMESTAMP - 2 HOURS WHERE RUN_ID = ?",
                   (run,))
        admin_conn.commit()
        assert db.query(conn, state, (run,))[0][0].strip() == "INTERRUPTED"
        call(conn, "FINISH_BACKTEST", (run, "FAILED", "the process stopped"))  # FAILED may leave rows unaccounted for
        found = backtest.report(conn, run, bt.schema)
    assert found is not None and (found["run"]["state"], found["run"]["unaccounted"]) == ("FAILED", 3)


def test_the_specialist_inbox_refuses_a_held_backtest_decision(bt, settings):
    held = next(i["ledger_id"] for i in bt.report["items"] if i["outcome"] == "UNCONFIRMED")
    with db.connection(settings, "app") as conn:
        with pytest.raises(review.ReviewError) as err:
            review.held_entry(conn, held, bt.schema)
    assert err.value.status == 409 and "backtest" in str(err.value)
    with db.connection(settings, "review") as rev:  # and Db2 itself, should anything call it directly
        db.use_schema(rev, bt.schema)
        params = (held, str(uuid.uuid4()), "AURELIA-CSP", "a reply", "a reply", "ALL_SUPPORTED", "", "", "m", "p", 1,
                  "{}", 0, " " * 64, " " * 40)
        cur = rev.cursor()
        with pytest.raises(Exception) as err:
            cur.callproc("RESOLVE_ESCALATION", params)
        rev.rollback()
        assert db.wrap_error(err.value, "refused").sqlstate == "75070"


def test_a_ledger_made_before_backtests_accepts_them_after_setup_and_a_reset_drops_runs(admin_conn, settings):
    name = f"ASOF_M{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_documents(admin_conn, name)
        seed.seed_chain_head(admin_conn, name)
        admin_conn.commit()
        db.use_schema(admin_conn, name)
        db.execute(admin_conn, SQL_OLD_CHECK)
        admin_conn.commit()
        entry = ledger.LedgerEntry(str(uuid.uuid4()), "backtest", "AURELIA-CSP", date(2026, 3, 10), "q", "d", "f",
                                   "ESCALATED", "NOT_COVERED", "m", "p", 1, {"claims": []})  # held: no release rules
        with pytest.raises(db.DatabaseError) as err:
            ledger.append(admin_conn, entry, name)
        assert err.value.sqlstate == "23513"
        schema.install(admin_conn, name)  # what setup runs: 11_backtest.sql widens the check
        assert ledger.append(admin_conn, entry, name).ledger_id == 1
        call(admin_conn, "START_BACKTEST", ("t.csv", "c" * 64, 1, "auto", "m", 0, 600, 60, "", 0))
        assert schema.reset_ledger(admin_conn, name) == 1
        db.use_schema(admin_conn, name)
        assert db.query(admin_conn, "SELECT COUNT(*) FROM BACKTEST_RUN")[0][0] == 0
        seed.seed_chain_head(admin_conn, name)  # what setup does after the reset: a fresh chain
        admin_conn.commit()
        assert ledger.append(admin_conn, replace(entry, request_id=str(uuid.uuid4())), name).ledger_id == 1
    finally:
        schema.drop(admin_conn, name)
