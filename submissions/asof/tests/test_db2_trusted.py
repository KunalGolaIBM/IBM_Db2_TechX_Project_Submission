"""Db2 integration: the trusted context (ASOF_TRUSTED_CONTEXT=true). Each request runs in Db2 as its API user.

A scratch schema with two API users, a checker and an auditor. The context is database-wide, so it is dropped (and
the users' roles revoked) when the module ends."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_db2_ledger import entry

from asof import db, ledger, replay, rowaccess, schema, seed, trusted, users
from asof.api import create_app
from asof.assistant import DemoAssistant
from asof.domains import DOMAINS
from asof.gate import Gate

pytestmark = pytest.mark.db2

RECORDING = replay.Recording.load() if replay.RECORDING_PATH.is_file() else None
SQL_SURROGATES = ("SELECT SURROGATEAUTHID FROM SYSCAT.SURROGATEAUTHIDS WHERE TRUSTEDID = ? AND TRUSTEDIDTYPE = 'C'")
SQL_ROLES = "SELECT ROLENAME FROM SYSCAT.ROLEAUTH WHERE GRANTEETYPE = 'U' AND GRANTEE = ?"
SQL_ROLE_PROCS = ("SELECT R.ROUTINENAME FROM SYSCAT.ROUTINEAUTH A JOIN SYSCAT.ROUTINES R ON R.ROUTINESCHEMA = A.SCHEMA "
                  "AND R.SPECIFICNAME = A.SPECIFICNAME WHERE A.GRANTEE = ? AND A.GRANTEETYPE = 'R' AND A.SCHEMA = ?")


@pytest.fixture(scope="module")
def tc(admin_conn, embeddings, settings):
    name = f"ASOF_C{uuid.uuid4().hex[:6].upper()}"
    s = settings.model_copy(update={"asof_auth": "users", "asof_trusted_context": True,
                                    "asof_trusted_context_address": ""})
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                            analyst_user=settings.asof_analyst_user)
        tokens = {"checker": users.add(admin_conn, "tc.checker", {"checker"}, name),
                  "auditor": users.add(admin_conn, "tc-auditor", {"auditor"}, name)}
        report = trusted.sync(admin_conn, s, name)
    except Exception:
        trusted.drop(admin_conn)
        schema.drop(admin_conn, name)
        raise
    pool = db.ConnectionPool(s, "app", trusted=True)
    yield SimpleNamespace(schema=name, settings=s, tokens=tokens, report=report, pool=pool)
    pool.close()
    for user in ("tc.checker", "tc-auditor", "tc.gone", "tc.bank"):
        users.disable(admin_conn, user, name)
    trusted.sync(admin_conn, s, name)  # revokes the disabled users' roles and takes them off the list
    trusted.drop(admin_conn)
    schema.drop(admin_conn, name)


def as_user(tc, name: str):
    """A pooled connection that runs as API user `name` (what the API does for each request)."""
    token = db.SESSION_USER.set(trusted.authid(name))
    try:
        return tc.pool.connect()
    finally:
        db.SESSION_USER.reset(token)


def test_setup_lists_exactly_the_api_users_for_the_runtime_user_and_address(admin_conn, settings, tc):
    (system, role, enabled), = db.query(admin_conn, trusted.SQL_CONTEXT, (trusted.CONTEXT,))
    assert (system.strip(), role.strip(), enabled.strip()) == (settings.asof_app_user.upper(), trusted.SESSION_ROLE, "Y")
    listed = {r[0].strip() for r in db.query(admin_conn, SQL_SURROGATES, (trusted.CONTEXT,))}
    assert listed == {"API_TC_CHECKER", "API_TC_AUDITOR"}  # never PUBLIC
    assert [r[0] for r in db.query(admin_conn, trusted.SQL_CONTEXT_ADDRESSES, (trusted.CONTEXT,))] == \
        [trusted.own_address(admin_conn)]
    assert tc.report.action in ("created", "updated")
    assert trusted.sync(admin_conn, tc.settings, tc.schema).action == "unchanged"  # a re-run changes nothing


def test_the_session_role_reads_like_the_runtime_user_but_only_the_api_roles_write(admin_conn, tc):
    session = {r[0].strip() for r in db.query(admin_conn, SQL_ROLE_PROCS, (trusted.SESSION_ROLE, tc.schema))}
    assert {"VERIFY_CHAIN", "CHANGE_IMPACT"} <= session and not session & set(trusted.WRITE_PROCEDURES)
    assert {r[0].strip() for r in db.query(admin_conn, SQL_ROLE_PROCS, ("ASOF_API_CHECKER", tc.schema))} == \
        {"APPEND_LEDGER"}
    assert {r[0].strip() for r in db.query(admin_conn, SQL_ROLES, ("API_TC_CHECKER",))} == \
        {"ASOF_API_CHECKER", "ASOF_TEXT_READER", "ASOF_ALL_DOMAINS"}
    assert {r[0].strip() for r in db.query(admin_conn, SQL_ROLES, ("API_TC_AUDITOR",))} == \
        {"ASOF_TEXT_READER", "ASOF_ALL_DOMAINS"}


@pytest.mark.skipif(RECORDING is None, reason="no recording shipped (python -m asof.replay record)")
def test_a_check_through_the_api_is_stored_by_the_api_user_who_asked(tc, embeddings):
    """POST /api/gate with the checker's token: the ledger row says API_TC_CHECKER stored it, through the context.
    The auditor's read of that row runs as API_TC_AUDITOR, and sees the text unmasked."""
    c = next(x for x in RECORDING.scenarios["checks"] if x["draft"])
    llm = replay.ReplayLLM(RECORDING)
    gate = Gate(llm, embeddings, tc.pool.connect, tc.schema)
    app = create_app(tc.settings, gate=gate, assistant=DemoAssistant(llm, embeddings, tc.pool.connect, tc.schema),
                     schema=tc.schema)
    with TestClient(app) as client:
        r = client.post("/api/gate", json={"question": c["question"], "draft_answer": c["draft"],
                                           "as_of_date": c["as_of"], "doc_id": c["doc_id"]},
                        headers={"authorization": f"Bearer {tc.tokens['checker']}"})
        assert r.status_code == 200, r.text
        assert r.json()["decision"] == c["decision"]
        got = client.get(f"/api/ledger/{r.json()['ledger_id']}",
                         headers={"authorization": f"Bearer {tc.tokens['auditor']}"}).json()
    who = got["stored_by"]
    assert who["user"] == "API_TC_CHECKER" and who["trusted_context"] == trusted.CONTEXT
    assert {"ASOF_API_CHECKER", "ASOF_API_SESSION", "ASOF_TEXT_READER"} <= set(who["roles"])
    assert got["final_answer"] != "[masked]"


def test_db2_refuses_an_auditor_session_that_tries_to_append(tc):
    conn = as_user(tc, "tc-auditor")
    try:
        assert db.query(conn, db.SQL_SESSION_USER)[0][0].strip() == "API_TC_AUDITOR"
        with pytest.raises(db.DatabaseError) as err:
            ledger.append(conn, entry(), tc.schema)
        assert err.value.sqlstate == "42501"  # SQL0551N: no EXECUTE on APPEND_LEDGER for this user
    finally:
        conn.close()
    conn = as_user(tc, "tc.checker")  # the same connection may be reused: it switches to the checker
    try:
        assert ledger.append(conn, entry(as_of=date(2026, 6, 2)), tc.schema).ledger_id >= 1
        assert ledger.verify_chain(conn, tc.schema).status == "OK"
    finally:
        conn.close()


@pytest.mark.parametrize("authid", ["DB2INST1", "ASOFEDIT", "API_NOBODY"])
def test_db2_refuses_a_switch_to_any_id_not_on_the_list(tc, authid):
    token = db.SESSION_USER.set(authid)
    try:
        with pytest.raises(db.DatabaseError) as err:
            tc.pool.connect()
    finally:
        db.SESSION_USER.reset(token)
    assert err.value.sqlstate == "42517"  # SQL20361N
    tc.pool.connect().close()  # the refused connection was closed; the pool still works


def test_a_disabled_users_next_request_is_refused_by_db2(admin_conn, tc):
    users.add(admin_conn, "tc.gone", {"checker"}, tc.schema)
    trusted.sync(admin_conn, tc.settings, tc.schema)
    as_user(tc, "tc.gone").close()  # the pooled connection now runs as API_TC_GONE
    users.disable(admin_conn, "tc.gone", tc.schema)
    report = trusted.sync(admin_conn, tc.settings, tc.schema)
    assert "no use for API_TC_GONE" in report.changes
    assert not db.query(admin_conn, SQL_ROLES, ("API_TC_GONE",))
    with pytest.raises(db.DatabaseError) as err:
        as_user(tc, "tc.gone")
    assert err.value.sqlstate == "42517"


def test_the_domain_row_permissions_apply_to_the_switched_user(admin_conn, tc):
    """06_domain_permissions.sql asks VERIFY_ROLE_FOR_USER(SESSION_USER, ...): evaluated for the API user's ID. An ID
    holding only the bank's domain role (granted here by hand; sync gives every API user all domains) sees only the
    bank's decisions, and Db2 refuses its append for the airline."""
    bank = next(d for d in (DOMAINS.values() if isinstance(DOMAINS, dict) else DOMAINS) if d.key == "bank")
    users.add(admin_conn, "tc.bank", {"checker"}, tc.schema)
    trusted.sync(admin_conn, tc.settings, tc.schema)
    with db.connection(tc.settings, "app") as app:  # one decision per domain, appended by the runtime user
        ledger.append(app, entry(doc_id=bank.doc_id), tc.schema)
        ledger.append(app, entry(), tc.schema)
    db.execute(admin_conn, "REVOKE ROLE ASOF_ALL_DOMAINS FROM USER API_TC_BANK")
    db.execute(admin_conn, f"GRANT ROLE {db.ident(rowaccess.role_for(bank))} TO USER API_TC_BANK")
    admin_conn.commit()
    try:
        conn = as_user(tc, "tc.bank")
        try:
            db.use_schema(conn, tc.schema)
            seen = {r[0].strip() for r in db.query(conn, "SELECT DISTINCT DOC_ID FROM ANSWER_LEDGER")}
            assert seen == {bank.doc_id}
            with pytest.raises(db.DatabaseError) as err:
                ledger.append(conn, entry(), tc.schema)  # an AURELIA-CSP row: outside its domain
            assert err.value.sqlstate is not None and err.value.sqlstate != "42501"  # the row permission, not EXECUTE
            assert ledger.append(conn, entry(doc_id=bank.doc_id), tc.schema).ledger_id >= 1
        finally:
            conn.close()
    finally:
        db.execute(admin_conn, f"REVOKE ROLE {db.ident(rowaccess.role_for(bank))} FROM USER API_TC_BANK")
        admin_conn.commit()
        trusted.sync(admin_conn, tc.settings, tc.schema)


def test_with_the_setting_off_there_is_no_context_and_nothing_switches(admin_conn, settings, tc):
    """Off (the default): sync drops the context, and the runtime pool is a plain one that runs as the runtime user."""
    off = tc.settings.model_copy(update={"asof_trusted_context": False})
    assert trusted.sync(admin_conn, off, tc.schema).action == "dropped"
    assert not db.query(admin_conn, trusted.SQL_CONTEXT, (trusted.CONTEXT,))
    token = db.SESSION_USER.set("API_TC_CHECKER")  # even if something set a user, a plain pool ignores it
    try:
        pool = db.ConnectionPool(settings, "app")
        conn = pool.connect()
        try:
            assert db.query(conn, db.SQL_SESSION_USER)[0][0].strip() == settings.asof_app_user.upper()
            a = ledger.append(conn, entry(as_of=date(2026, 6, 2)), tc.schema)
            assert ledger.get_entry(conn, a.ledger_id, tc.schema)["stored_by"]["trusted_context"] is None
        finally:
            conn.close()
            pool.close()
    finally:
        db.SESSION_USER.reset(token)
        assert trusted.sync(admin_conn, tc.settings, tc.schema).action == "created"  # back on for the rest
