"""Domain row permissions in Db2 (06_domain_permissions.sql): a domain-scoped user sees only its own domain's
decisions, through every audit view and on direct SQL against the tables, while the users that run the system still
see, append and verify every row."""

from __future__ import annotations

import json
import uuid

import pytest
from fakes import ScriptedLLM
from test_db2_ledger import entry
from test_db2_review import _call, _verdicts

from asof import db, ledger, rowaccess, schema, seed
from asof.askledger import LedgerAsker
from asof.config import ConfigError
from asof.schemas import LedgerAnswer, LedgerSql

pytestmark = pytest.mark.db2

AIR, BANK = "AURELIA-CSP", "FERNHOLLOW-FEES"
TABLES = ("ANSWER_LEDGER", "CLAIM_CITATION", "ESCALATION_REVIEW", "CORRECTION_NOTICE", "ANSWER_SUGGESTION",
          "MQT_DECISION_STATS", "MQT_CLAIM_OUTCOMES", "MQT_DOMAIN_DECISION_STATS", "MQT_DOMAIN_CLAIM_OUTCOMES")
# Each table's rows, as (row key, policy document): how the owner, who sees everything, tells the domains apart.
OWNER_VIEW = {
    "ANSWER_LEDGER": "SELECT LEDGER_ID, DOC_ID FROM ANSWER_LEDGER",
    "CLAIM_CITATION": "SELECT C.LEDGER_ID * 100 + C.PASS_NO * 10 + C.CLAIM_NO, L.DOC_ID FROM CLAIM_CITATION C "
                      "JOIN ANSWER_LEDGER L ON L.LEDGER_ID = C.LEDGER_ID",
    "ESCALATION_REVIEW": "SELECT R.ESCALATED_LEDGER_ID, L.DOC_ID FROM ESCALATION_REVIEW R "
                         "JOIN ANSWER_LEDGER L ON L.LEDGER_ID = R.ESCALATED_LEDGER_ID",
    "CORRECTION_NOTICE": "SELECT N.NOTICE_ID, L.DOC_ID FROM CORRECTION_NOTICE N "
                         "JOIN ANSWER_LEDGER L ON L.LEDGER_ID = N.LEDGER_ID",
    "ANSWER_SUGGESTION": "SELECT S.SUGGESTION_ID, P.DOC_ID FROM ANSWER_SUGGESTION S "
                         "JOIN PUBLISHED_ANSWER P ON P.ANSWER_ID = S.ANSWER_ID",
}
SCOPED_VIEW = {
    "ANSWER_LEDGER": "SELECT LEDGER_ID FROM ANSWER_LEDGER",
    "CLAIM_CITATION": "SELECT LEDGER_ID * 100 + PASS_NO * 10 + CLAIM_NO FROM CLAIM_CITATION",
    "ESCALATION_REVIEW": "SELECT ESCALATED_LEDGER_ID FROM ESCALATION_REVIEW",
    "CORRECTION_NOTICE": "SELECT NOTICE_ID FROM CORRECTION_NOTICE",
    "ANSWER_SUGGESTION": "SELECT SUGGESTION_ID FROM ANSWER_SUGGESTION",
}
SQL_NOTICE = ("INSERT INTO CORRECTION_NOTICE (LEDGER_ID, CLAUSE_ID, CITED_VERSION, CURRENT_VERSION, AS_OF_DATE, "
              "CORRECTION_TEXT, NOTICE_TEXT, CHECK_DECISION, AGENT_TRACE) "
              "VALUES (?, 'BRV-002', 'v1', 'v2', '2026-03-10', 'c', 'n', 'ESCALATED', '{}')")
SQL_SUGGESTION = ("INSERT INTO ANSWER_SUGGESTION (ANSWER_ID, CLAUSE_ID, STALE_FROM, BASED_ON_VERSION, SUGGESTED_TEXT, "
                  "CHECK_DECISION, AGENT_TRACE) VALUES (?, ?, '2026-06-01', 'v2', 's', 'ESCALATED', '{}')")
SQL_REVIEW = "INSERT INTO ESCALATION_REVIEW (ESCALATED_LEDGER_ID, REVIEW_LEDGER_ID, OUTCOME) VALUES (?, ?, 'SPECIALIST_CHECKED')"


def _ids(rows) -> set[int]:
    return {int(r[0]) for r in rows}


# A bank release Db2's release rules accept on 2026-03-10: the claim cites the bank's own clause in force that day
# (OVD-001 v1) and quotes it. The shared entry() helper's release cites an airline clause, which a bank row may not.
BANK_RELEASE = {"version": 1, "claims": [
    {"pass": 1, "claim_no": 1, "text": "the overdraft fee is $35 an item", "area": "overdraft", "verdict": "SUPPORTED",
     "llm_verdict": "SUPPORTED", "rule_check": "NOT_APPLICABLE", "clause_id": "OVD-001", "clause_version": "v1",
     "clause_bus_start": "2026-01-01", "clause_sys_start": None, "distance": 0.2,
     "quoted_span": "An overdraft fee of $35 is charged for each item we pay"}]}

@pytest.fixture(scope="module")
def domains(admin_conn, embeddings, settings):
    """A scratch schema with two decisions per domain (written by the runtime user), and one specialist answer,
    correction notice and drafted help-centre fix per domain (written by the owner)."""
    name = f"ASOF_D{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                            analyst_user=settings.asof_analyst_user, mart_user=settings.asof_mart_user,
                            review_user=settings.asof_review_user, domain_users=rowaccess.domain_users(settings))
        app = db.connect(settings, "app")
        try:
            ids = {doc: [ledger.append(app, entry(doc_id=doc), name).ledger_id,
                         ledger.append(app, entry(doc_id=doc, decision="PASS", reason_code="ALL_SUPPORTED",
                                                  **({"verdicts": BANK_RELEASE} if doc == BANK else {})), name).ledger_id]
                   for doc in (AIR, BANK)}
        finally:
            app.close()
        db.use_schema(admin_conn, name)
        for doc, answer, clause in ((AIR, "PA-BRV-001", "BRV-002"), (BANK, "PA-OVD-001", "OVD-001")):
            held, later = ids[doc]
            db.execute(admin_conn, SQL_REVIEW, (held, later))
            db.execute(admin_conn, SQL_NOTICE, (later,))
            db.execute(admin_conn, SQL_SUGGESTION, (answer, clause))
        admin_conn.commit()
    except Exception:
        admin_conn.rollback()
        schema.drop(admin_conn, name)
        raise
    yield name
    schema.drop(admin_conn, name)


def _connect(settings, role, name):
    try:
        conn = db.connect(settings, role)
    except (ConfigError, db.DatabaseError) as exc:
        pytest.skip(f"{role} cannot connect (run python -m asof.setup first): {exc}")
    db.use_schema(conn, name)
    return conn


def _by_doc(admin_conn, name, table) -> dict[str, set[int]]:
    db.use_schema(admin_conn, name)
    out: dict[str, set[int]] = {AIR: set(), BANK: set()}
    for key, doc in db.query(admin_conn, OWNER_VIEW[table]):
        out[doc.strip()].add(int(key))
    return out


@pytest.mark.parametrize("role, doc", [("analyst_airline", AIR), ("analyst_bank", BANK)])
def test_a_domain_analyst_sees_only_its_domain_through_every_audit_view(settings, admin_conn, domains, role, doc):
    truth = _by_doc(admin_conn, domains, "ANSWER_LEDGER")
    cites = _by_doc(admin_conn, domains, "CLAIM_CITATION")
    # entry()'s held rows carry a rule override; its releases (valid under Db2's release rules) carry none
    overrides = {int(r[0]) for r in db.query(admin_conn, "SELECT o.LEDGER_ID FROM V_RULE_OVERRIDES o JOIN ANSWER_LEDGER l "
                                                       "ON l.LEDGER_ID = o.LEDGER_ID WHERE l.DOC_ID = ?", (doc,))}
    assert overrides and overrides < truth[doc]
    conn = _connect(settings, role, domains)
    try:
        decisions = db.query(conn, "SELECT LEDGER_ID, DOC_ID, FINAL_ANSWER FROM V_AUDIT_DECISIONS")
        assert _ids(decisions) == truth[doc] and {r[1].strip() for r in decisions} == {doc}
        assert {r[2] for r in decisions} == {"[masked]"}  # the column masks still apply on top
        assert _ids(db.query(conn, "SELECT LEDGER_ID * 100 + PASS_NO * 10 + CLAIM_NO FROM V_AUDIT_CLAIMS")) == cites[doc]
        assert _ids(db.query(conn, "SELECT LEDGER_ID FROM V_RULE_OVERRIDES")) == overrides  # the held rows: a rule override
        assert db.query(conn, "SELECT SUM(DECISIONS) FROM V_DECISION_STATS")[0][0] == len(truth[doc])
        assert db.query(conn, "SELECT SUM(CLAIMS) FROM V_CLAIM_OUTCOMES_BY_AREA")[0][0] == len(cites[doc])
        assert db.query(conn, "SELECT DOC_ID FROM V_DOMAIN_SCOPE") == [(doc,)]
        # policy is not per decision: every analyst reads both documents' timelines
        assert {r[0].strip() for r in db.query(conn, "SELECT DISTINCT DOC_ID FROM V_POLICY_TIMELINE")} == {AIR, BANK}
    finally:
        conn.close()


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM V_AUDIT_DECISIONS WHERE DOC_ID = 'FERNHOLLOW-FEES'",
    "SELECT COUNT(*) FROM V_AUDIT_DECISIONS WHERE LEDGER_ID IN (3, 4)",
    "SELECT COUNT(*) FROM V_AUDIT_CLAIMS WHERE LEDGER_ID IN (3, 4)",
    "SELECT COUNT(*) FROM V_REVIEW_QUEUE",  # not granted to the analyst at all
])
def test_another_domains_rows_are_invisible_even_when_named(settings, admin_conn, domains, sql):
    assert {3, 4} <= _by_doc(admin_conn, domains, "ANSWER_LEDGER")[BANK]
    conn = _connect(settings, "analyst_airline", domains)
    try:
        if "V_REVIEW_QUEUE" in sql:
            with pytest.raises(db.DatabaseError) as err:
                db.query(conn, sql)
            assert err.value.sqlstate == "42501"
        else:
            assert db.query(conn, sql) == [(0,)]
    finally:
        conn.close()


def test_row_permissions_hold_on_the_tables_themselves_even_with_select_granted(settings, admin_conn, domains):
    """The analyst normally reads only views. Granted SELECT on the tables (in this scratch schema only), it still gets
    only its own domain's rows: the permission is on the table, not in the view."""
    db.use_schema(admin_conn, domains)
    for table in TABLES:
        db.execute(admin_conn, f"GRANT SELECT ON TABLE {db.ident(domains)}.{db.ident(table)} "
                               f"TO USER {db.ident(settings.asof_airline_analyst_user)}")
    admin_conn.commit()
    conn = _connect(settings, "analyst_airline", domains)
    try:
        for table, sql in SCOPED_VIEW.items():
            truth = _by_doc(admin_conn, domains, table)
            assert truth[AIR] and truth[BANK], table  # the fixture wrote rows for both domains
            assert _ids(db.query(conn, sql)) == truth[AIR], table
        assert db.query(conn, "SELECT COUNT(*) FROM ANSWER_LEDGER WHERE DOC_ID = 'FERNHOLLOW-FEES'") == [(0,)]
        assert db.query(conn, "SELECT COUNT(*) FROM CLAIM_CITATION WHERE LEDGER_ID IN (3, 4)") == [(0,)]
        # the MQTs that count every domain together show it nothing; the per-document ones only its own
        assert db.query(conn, "SELECT COUNT(*) FROM MQT_DECISION_STATS") == [(0,)]
        assert db.query(conn, "SELECT COUNT(*) FROM MQT_CLAIM_OUTCOMES") == [(0,)]
        assert {r[0].strip() for r in db.query(conn, "SELECT DISTINCT DOC_ID FROM MQT_DOMAIN_DECISION_STATS")} == {AIR}
        assert {r[0].strip() for r in db.query(conn, "SELECT DISTINCT DOC_ID FROM MQT_DOMAIN_CLAIM_OUTCOMES")} == {AIR}
    finally:
        conn.close()


def test_the_users_that_run_the_system_see_every_domain(settings, admin_conn, domains):
    holders = {r[0].strip().lower() for r in db.query(
        admin_conn, "SELECT GRANTEE FROM SYSCAT.ROLEAUTH WHERE ROLENAME = 'ASOF_ALL_DOMAINS' AND GRANTEETYPE = 'U'")}
    assert {settings.asof_app_user, settings.asof_editor_user, settings.asof_review_user, settings.asof_analyst_user,
            settings.asof_mart_user} <= holders
    assert not holders & {u for pair in rowaccess.domain_users(settings).values() for u in pair}
    roles = db.query(admin_conn, "SELECT GRANTEE, ROLENAME FROM SYSCAT.ROLEAUTH WHERE GRANTEETYPE = 'U' "
                                 "AND ROLENAME LIKE 'ASOF^_DOMAIN^_%' ESCAPE '^'")
    assert {(u.strip().lower(), r.strip()) for u, r in roles} >= {
        (settings.asof_airline_analyst_user, "ASOF_DOMAIN_AIRLINE"), (settings.asof_airline_review_user, "ASOF_DOMAIN_AIRLINE"),
        (settings.asof_bank_analyst_user, "ASOF_DOMAIN_BANK"), (settings.asof_bank_review_user, "ASOF_DOMAIN_BANK")}
    db.use_schema(admin_conn, domains)
    assert db.query(admin_conn, "SELECT DOC_ID FROM DOMAIN_ACCESS ORDER BY DOC_ID") == [(AIR,), (BANK,)]
    assert db.query(admin_conn, "SELECT COUNT(*) FROM V_DOMAIN_SCOPE") == [(2,)]  # the owner holds SECADM
    everything = db.query(admin_conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")
    claims = db.query(admin_conn, "SELECT COUNT(*) FROM CLAIM_CITATION WHERE PASS_NO = 1")
    for role, sql, want in (("analyst", "SELECT COUNT(*) FROM V_AUDIT_DECISIONS", everything),
                            ("analyst", "SELECT SUM(DECISIONS) FROM V_DECISION_STATS", everything),  # counted once
                            ("analyst", "SELECT SUM(CLAIMS) FROM V_CLAIM_OUTCOMES_BY_AREA", claims),
                            ("app", "SELECT SUM(DECISIONS) FROM V_DECISION_STATS", everything),
                            ("mart", "SELECT COUNT(*) FROM ANSWER_LEDGER", everything),
                            ("app", "SELECT COUNT(*) FROM ANSWER_LEDGER", everything)):
        conn = _connect(settings, role, domains)
        try:
            assert db.query(conn, sql) == want, (role, sql)
        finally:
            conn.close()


def test_the_runtime_user_still_appends_for_both_domains_and_verifies_the_whole_chain(settings, admin_conn, domains):
    app = _connect(settings, "app", domains)
    try:
        new = {doc: ledger.append(app, entry(doc_id=doc), domains).ledger_id for doc in (AIR, BANK)}
        status = ledger.verify_chain(app, domains)
        total = int(db.query(app, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0])
    finally:
        app.close()
    truth = _by_doc(admin_conn, domains, "ANSWER_LEDGER")
    assert new[AIR] in truth[AIR] and new[BANK] in truth[BANK]
    assert (status.status, status.checked) == ("OK", total) and total == len(truth[AIR]) + len(truth[BANK])


def test_a_procedure_cannot_write_a_row_its_caller_could_not_see(settings, admin_conn, domains):
    """ENFORCED FOR ALL ACCESS: Db2 checks the row a procedure inserts on the caller's behalf against the caller's
    permissions (SQL20471N), so a domain user who could call APPEND_LEDGER could still write only its own domain."""
    db.use_schema(admin_conn, domains)
    db.execute(admin_conn, f"GRANT EXECUTE ON PROCEDURE {db.ident(domains)}.APPEND_LEDGER "
                           f"TO USER {db.ident(settings.asof_airline_analyst_user)}")
    admin_conn.commit()
    conn = _connect(settings, "analyst_airline", domains)
    try:
        with pytest.raises(db.DatabaseError) as refused:
            ledger.append(conn, entry(doc_id=BANK), domains)
        conn.rollback()
        assert refused.value.sqlstate == "22542" and "SQL20471N" in str(refused.value)
        own = ledger.append(conn, entry(doc_id=AIR), domains)
    finally:
        conn.close()
    assert own.ledger_id in _by_doc(admin_conn, domains, "ANSWER_LEDGER")[AIR]
    app = _connect(settings, "app", domains)
    try:
        assert ledger.verify_chain(app, domains).status == "OK"
    finally:
        app.close()


def test_a_domain_specialist_answers_its_own_domain_and_cannot_even_find_another(settings, domains):
    app = _connect(settings, "app", domains)
    try:
        held = ledger.append(app, entry(doc_id=AIR), domains).ledger_id
    finally:
        app.close()
    other = _connect(settings, "review_bank", domains)
    try:
        with pytest.raises(Exception) as hidden:
            _call(other, domains, held, _verdicts(held, "SUPPORTED"))
        other.rollback()
        assert db.wrap_error(hidden.value, "x").sqlstate == "75050"  # "Unknown ledger entry": Db2 hid the row
    finally:
        other.close()
    own = _connect(settings, "review_airline", domains)
    try:
        out = _call(own, domains, held, _verdicts(held, "SUPPORTED"))
        own.commit()
        assert str(out[14]).strip() == "SPECIALIST_CHECKED"
    finally:
        own.close()
    app = _connect(settings, "app", domains)
    try:
        reviewed = db.query(app, "SELECT DOC_ID, DECISION FROM ANSWER_LEDGER WHERE LEDGER_ID = ?", (int(out[12]),))
        assert [(r[0].strip(), r[1].strip()) for r in reviewed] == [(AIR, "REVIEWED")]
        assert ledger.verify_chain(app, domains).status == "OK"
    finally:
        app.close()


def test_ask_the_ledger_in_a_domain_scope_returns_only_that_domain(settings, admin_conn, domains):
    truth = _by_doc(admin_conn, domains, "ANSWER_LEDGER")
    query = "SELECT DOC_ID, COUNT(*) AS N FROM V_AUDIT_DECISIONS GROUP BY DOC_ID ORDER BY DOC_ID"
    llm = ScriptedLLM(sql=[LedgerSql(sql=query, explanation="x"), LedgerSql(sql=query, explanation="x")],
                      answer=[LedgerAnswer(answer="Bank only."), LedgerAnswer(answer="Both.")])
    asker = LedgerAsker(llm, settings, domains)
    assert BANK in asker.views("bank")  # the model's sample rows are read as bankread too
    scoped = asker.ask("How many decisions per policy document?", scope="bank")
    assert scoped.rows == [[BANK, len(truth[BANK])]] and scoped.scope_applied == [BANK]
    assert scoped.runs_as.startswith(settings.asof_bank_analyst_user)
    everything = asker.ask("How many decisions per policy document?")
    assert everything.rows == [[AIR, len(truth[AIR])], [BANK, len(truth[BANK])]]
    assert everything.scope_applied == [AIR, BANK] and json.dumps(everything.as_dict())


def test_setup_drops_the_permission_that_showed_the_mqt_to_everyone(settings, admin_conn, domains):
    """Installs from before the domain permissions had P_MQT_DECISION_STATS_ALL_ROWS (FOR ROWS WHERE 1 = 1). Db2 ORs a
    table's permissions, so left in place it would show every domain's counts to a domain analyst."""
    db.use_schema(admin_conn, domains)
    db.execute(admin_conn, f"CREATE PERMISSION {db.ident(domains)}.P_MQT_DECISION_STATS_ALL_ROWS ON "
                           f"{db.ident(domains)}.MQT_DECISION_STATS FOR ROWS WHERE 1 = 1 ENFORCED FOR ALL ACCESS ENABLE")
    admin_conn.commit()
    truth = _by_doc(admin_conn, domains, "ANSWER_LEDGER")
    sql = "SELECT SUM(DECISIONS) FROM V_DECISION_STATS"
    conn = _connect(settings, "analyst_airline", domains)
    try:
        assert db.query(conn, sql)[0][0] > len(truth[AIR])  # the leak the retired permission caused
        conn.rollback()
        schema.install(admin_conn, domains)
        assert not db.query(admin_conn, "SELECT 1 FROM SYSCAT.CONTROLS WHERE CONTROLSCHEMA = ? AND "
                                        "CONTROLNAME = 'P_MQT_DECISION_STATS_ALL_ROWS'", (domains,))
        assert db.query(conn, sql)[0][0] == len(_by_doc(admin_conn, domains, "ANSWER_LEDGER")[AIR])
    finally:
        conn.close()
