"""Ask the ledger against Db2: the analyst user, the column masks, and the chain end to end."""

from __future__ import annotations

import uuid

import pytest
from fakes import ScriptedLLM
from test_db2_ledger import entry

from asof import db, ledger, schema, seed
from asof.askledger import LedgerAsker, Refused, validate
from asof.config import ConfigError
from asof.schemas import LedgerAnswer, LedgerSql

pytestmark = pytest.mark.db2


@pytest.fixture(scope="module")
def audited(admin_conn, embeddings, settings):
    """A scratch schema with three decisions written by the runtime user."""
    name = f"ASOF_Q{uuid.uuid4().hex[:6].upper()}"
    schema.install(admin_conn, name)
    seed.seed_policy(admin_conn, embeddings, name)
    seed.seed_chain_head(admin_conn, name)
    seed.seed_published_answers(admin_conn, name)
    seed.seed_faq(admin_conn, embeddings, name)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                        analyst_user=settings.asof_analyst_user)
    app = db.connect(settings, "app")
    try:
        ledger.append(app, entry(), name)
        ledger.append(app, entry(decision="PASS", reason_code="ALL_SUPPORTED", final_answer="Yes, within 90 days."), name)
        ledger.append(app, entry(final_answer="Holding reply for a specialist."), name)
    finally:
        app.close()
    yield name
    schema.drop(admin_conn, name)


@pytest.fixture
def analyst(settings, audited):
    try:
        conn = db.connect(settings, "analyst")
    except (ConfigError, db.DatabaseError) as exc:
        pytest.skip(f"analyst user cannot connect (run python -m asof.setup first): {exc}")
    db.use_schema(conn, audited)
    yield conn
    conn.rollback()
    conn.close()


def test_the_analyst_sees_decisions_but_the_text_is_masked_by_db2(analyst, settings, audited):
    rows = db.query(analyst, "SELECT LEDGER_ID, DECISION, CLAIMS, QUESTION_REDACTED, FINAL_ANSWER "
                             "FROM V_AUDIT_DECISIONS ORDER BY LEDGER_ID")
    assert [(r[0], r[1].strip(), r[2], r[3], r[4]) for r in rows] == [
        (1, "ESCALATED", 2, "[masked]", "[masked]"), (2, "PASS", 2, "[masked]", "[masked]"),
        (3, "ESCALATED", 2, "[masked]", "[masked]")]
    app = db.connect(settings, "app")  # the runtime user (ASOF_TEXT_READER) reads the same rows unmasked
    try:
        db.use_schema(app, audited)
        assert db.query(app, "SELECT FINAL_ANSWER FROM ANSWER_LEDGER WHERE LEDGER_ID = 2") == [("Yes, within 90 days.",)]
        assert ledger.verify_chain(app, audited).status == "OK"
    finally:
        app.close()


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM ANSWER_LEDGER",
    "SELECT COUNT(*) FROM CLAIM_CITATION",
    "SELECT COUNT(*) FROM POLICY_CLAUSE",
    "SELECT COUNT(*) FROM ANSWER_SUGGESTION",
    "UPDATE V_AUDIT_CLAIMS SET VERDICT = 'SUPPORTED'",
    "DELETE FROM V_AUDIT_DECISIONS",
    "CREATE TABLE ANALYST_WAS_HERE (X INT)",
])
def test_the_analyst_can_read_the_audit_views_and_nothing_else(analyst, sql):
    with pytest.raises(db.DatabaseError) as err:
        db.execute(analyst, sql)
    assert err.value.sqlstate in ("42501", "42502", "42807")  # no privilege / view not updatable


def test_the_analyst_cannot_call_the_ledger_procedures(analyst):
    cur = analyst.cursor()
    try:
        with pytest.raises(Exception, match="SQL0551N|42501"):
            cur.callproc("VERIFY_CHAIN", ("", 0, 0, ""))
    finally:
        cur.close()


def test_db2_masks_values_not_predicates_which_is_why_the_gate_refuses_them(analyst):
    leak = "SELECT COUNT(*) FROM V_AUDIT_DECISIONS WHERE FINAL_ANSWER LIKE 'Holding%'"
    assert db.query(analyst, leak) == [(2,)]  # real text, counted through the mask: a documented RCAC property
    with pytest.raises(Refused, match="masked"):
        validate(leak)  # so generated SQL never gets to ask


def ask(settings, audited, *replies, timeout_s=10):
    llm = ScriptedLLM(sql=[r for r in replies if isinstance(r, LedgerSql)],
                      answer=[r for r in replies if isinstance(r, LedgerAnswer)])
    return LedgerAsker(llm, settings, audited, timeout_s=timeout_s), llm


def test_the_chain_reflects_the_views_through_sqlalchemy_and_answers_as_the_analyst(settings, audited, analyst):
    asker, llm = ask(settings, audited,
                     LedgerSql(sql="SELECT DECISION, COUNT(*) AS N, MAX(FINAL_ANSWER) FROM V_AUDIT_DECISIONS "
                                   "GROUP BY DECISION", explanation="x"),
                     LedgerSql(sql="SELECT LEDGER_ID, DECISION, FINAL_ANSWER FROM V_AUDIT_DECISIONS "
                                   "WHERE DECISION = 'ESCALATED' ORDER BY LEDGER_ID", explanation="escalations"),
                     LedgerAnswer(answer="Two decisions were escalated: ledger rows 1 and 3. Their text is masked."))
    views = asker.views()
    assert "v_audit_decisions" in views and "v_audit_claims" in views and "answer_ledger" not in views.lower()
    assert "[masked]" in views and f'"{audited}".' not in views  # samples read as the analyst; names unqualified

    r = asker.ask("Which answers were escalated?")
    assert r.status == "ANSWERED" and "masked" in r.attempts[0]["refused"]  # MAX() over masked text: repaired
    assert r.columns == ["LEDGER_ID", "DECISION", "FINAL_ANSWER"]
    assert r.rows == [[1, "ESCALATED", "[masked]"], [3, "ESCALATED", "[masked]"]]
    assert r.answer.startswith("Two decisions") and r.runs_as.startswith(settings.asof_analyst_user)


def test_db2_cancels_a_runaway_query(settings, audited):
    heavy = ("SELECT COUNT(*) AS N FROM V_POLICY_TIMELINE a, V_POLICY_TIMELINE b, V_POLICY_TIMELINE c, "
             "V_POLICY_TIMELINE d, V_POLICY_TIMELINE e, V_POLICY_TIMELINE f")
    asker, _ = ask(settings, audited, LedgerSql(sql=heavy, explanation="x"), LedgerSql(sql=heavy, explanation="x"),
                   timeout_s=1)
    r = asker.ask("count everything against everything")
    assert r.status in ("FAILED", "STOPPED") and r.rows == [] and len(r.attempts) == 2
    # Db2 ends it either way: the app's statement timeout ("processing was cancelled due to an interrupt"), or one of
    # the analyst workload's thresholds (07_wlm.sql). Which one depends on the optimizer's estimate (docs/wlm.md).
    assert all("SQL0952N" in a["db2_error"] or "TH_ASOF_ANALYST_" in a["db2_error"] for a in r.attempts), r.attempts
