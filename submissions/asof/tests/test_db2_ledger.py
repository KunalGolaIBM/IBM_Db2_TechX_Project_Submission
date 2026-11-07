"""Db2 integration: append-only ledger, hash chain, tamper detection, replay and privileges."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import date

import pytest

from asof import db, ledger, schema, seed

pytestmark = pytest.mark.db2


def entry(**over) -> ledger.LedgerEntry:
    base = dict(
        request_id=str(uuid.uuid4()), channel="api", doc_id="AURELIA-CSP", as_of=date(2026, 3, 10),
        question_redacted="Can I get the bereavement fare after I fly?",
        draft_redacted="Yes, apply retroactively within 90 days.", final_answer="Holding reply.",
        decision="ESCALATED", reason_code="NOT_COVERED", model_info="test:model", prompt_version="test",
        latency_ms=12, verdicts={"version": 1, "claims": [
            {"pass": 1, "claim_no": 1, "text": "apply retroactively", "area": "bereavement", "verdict": "CONTRADICTED",
             "llm_verdict": "SUPPORTED", "rule_check": "MISMATCH", "clause_id": "BRV-002", "clause_version": "v1",
             "clause_bus_start": "2026-01-01", "clause_sys_start": "2026-11-06 04:00:00.000001", "distance": 0.31,
             "quoted_span": "cannot be applied retroactively"},
            {"pass": 1, "claim_no": 2, "text": "lounge access", "area": "other", "verdict": "NOT_COVERED",
             "llm_verdict": "NOT_COVERED", "rule_check": "NOT_APPLICABLE", "clause_id": None, "clause_version": None,
             "clause_bus_start": None, "clause_sys_start": None, "distance": None, "quoted_span": None}]},
    )
    base.update(over)
    return ledger.LedgerEntry(**base)


@pytest.fixture
def scratch(admin_conn, embeddings, settings):
    """A private schema for tests that break the chain on purpose."""
    name = f"ASOF_T{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_documents(admin_conn, name)  # each ledger row names its policy document (FK_LEDGER_DOC)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)  # the grants cover every table, the FAQ store included
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)  # a failed setup must not leave a schema behind
        raise
    yield name
    schema.drop(admin_conn, name)


@pytest.fixture
def verifier(settings, scratch):
    """The runtime user: the only one that reads the ledger text unmasked, so the only one that can verify."""
    conn = db.connect(settings, "app")
    yield lambda: ledger.verify_chain(conn, scratch)
    conn.close()


def test_app_user_appends_and_reads_back(app_conn, test_schema):
    a = ledger.append(app_conn, entry(), test_schema)
    got = ledger.get_entry(app_conn, a.ledger_id, test_schema)
    assert got["row_hash"] == a.row_hash and got["decision"] == "ESCALATED"
    got_citations = [(c["pass_no"], c["claim_no"], c["verdict"]) for c in got["citations"]]
    assert got_citations == [(1, 1, "CONTRADICTED"), (1, 2, "NOT_COVERED")]
    assert got["citations"][0]["clause_bus_start"] == date(2026, 1, 1)
    assert ledger.verify_chain(app_conn, test_schema).status == "OK"


def test_rows_are_consecutive_and_linked(app_conn, test_schema):
    rows = [ledger.append(app_conn, entry(), test_schema) for _ in range(3)]
    assert [r.ledger_id for r in rows] == list(range(rows[0].ledger_id, rows[0].ledger_id + 3))
    stored = [ledger.get_entry(app_conn, r.ledger_id, test_schema) for r in rows]
    assert stored[1]["prev_hash"] == stored[0]["row_hash"] and stored[2]["prev_hash"] == stored[1]["row_hash"]


def test_chain_stays_intact_under_concurrent_writers(settings, app_conn, test_schema):
    errors: list[Exception] = []

    def writer():
        conn = db.connect(settings, "app")
        try:
            for _ in range(4):
                ledger.append(conn, entry(), test_schema)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            conn.close()

    threads = [threading.Thread(target=writer) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(120)
    assert not errors
    status = ledger.verify_chain(app_conn, test_schema)
    assert status.status == "OK", status


def test_a_held_chain_head_lock_makes_the_next_append_fail_in_seconds_not_hang(settings, scratch):
    """The runtime users run with SET CURRENT LOCK TIMEOUT, so a stuck writer cannot stall every check."""
    quick = settings.model_copy(update={"db2_lock_timeout_s": 2})
    blocker = db.connect(quick, "admin")  # the owner, in an open transaction that holds the head row
    app = db.connect(quick, "app")
    try:
        db.use_schema(blocker, scratch)
        db.execute(blocker, "UPDATE CHAIN_HEAD SET LAST_LEDGER_ID = LAST_LEDGER_ID WHERE HEAD_ID = 1")
        started = time.monotonic()
        with pytest.raises(db.DatabaseError) as err:
            ledger.append(app, entry(), scratch)
        waited = time.monotonic() - started
    finally:
        blocker.rollback()
        blocker.close()
        app.close()
    assert err.value.sqlstate in ("40001", "57033")  # SQL0911N reason 68 (timeout) or SQL0913N
    assert 1.5 < waited < 10


@pytest.mark.parametrize("sql", [
    "INSERT INTO {s}.ANSWER_LEDGER (LEDGER_ID) VALUES (999)",
    "UPDATE {s}.ANSWER_LEDGER SET FINAL_ANSWER = 'x'",
    "DELETE FROM {s}.ANSWER_LEDGER",
    "UPDATE {s}.CLAIM_CITATION SET VERDICT = 'SUPPORTED'",
    "DELETE FROM {s}.CLAIM_CITATION",
    "UPDATE {s}.CHAIN_HEAD SET LAST_HASH = 'x'",
])
def test_app_user_cannot_write_ledger_tables(app_conn, test_schema, sql):
    with pytest.raises(db.DatabaseError) as err:
        db.execute(app_conn, sql.format(s=test_schema))
    assert err.value.sqlstate == "42501"


@pytest.mark.parametrize("sql", [
    "UPDATE {s}.ANSWER_LEDGER SET FINAL_ANSWER = 'edited'",
    "DELETE FROM {s}.ANSWER_LEDGER",
    "UPDATE {s}.CLAIM_CITATION SET VERDICT = 'SUPPORTED'",
    "DELETE FROM {s}.CLAIM_CITATION",
])
def test_triggers_stop_even_the_owner(admin_conn, app_conn, test_schema, sql):
    ledger.append(app_conn, entry(), test_schema)
    with pytest.raises(db.DatabaseError) as err:
        db.execute(admin_conn, sql.format(s=test_schema))
    admin_conn.rollback()
    assert err.value.sqlstate == "75001"


def test_injection_strings_are_stored_as_plain_text(app_conn, test_schema):
    nasty = "'); DROP TABLE ASOF_TEST.ANSWER_LEDGER; -- é中"
    a = ledger.append(app_conn, entry(question_redacted=nasty, draft_redacted=nasty), test_schema)
    got = ledger.get_entry(app_conn, a.ledger_id, test_schema)
    assert got["question_redacted"] == nasty and got["draft_redacted"] == nasty


def test_db2_rejects_more_than_eight_claims_per_check(app_conn, test_schema):
    many = [{"pass": 1 + i // 8, "claim_no": 1 + i % 8, "text": "c", "area": "other", "verdict": "NOT_COVERED",
             "rule_check": "NOT_APPLICABLE"} for i in range(17)]
    with pytest.raises(db.DatabaseError) as err:
        ledger.append(app_conn, entry(verdicts={"claims": many}), test_schema)
    assert err.value.sqlstate == "75003"


def test_db2_rejects_an_unknown_decision(app_conn, test_schema):
    cur = app_conn.cursor()
    e = entry()
    with pytest.raises(Exception) as err:
        cur.callproc(f"{test_schema}.APPEND_LEDGER", (e.request_id, "api", "AURELIA-CSP", e.as_of, "q", "d", "f",
                                                      "MAYBE", "X", "m", "p", 1, json.dumps(e.verdicts), 0, "", None))
    app_conn.rollback()
    assert "23513" in str(err.value)


def _drop_trigger(conn, schema_name, name):
    db.execute(conn, f"DROP TRIGGER {db.ident(schema_name)}.{db.ident(name)}")
    conn.commit()


def test_verify_chain_catches_an_owner_who_edits_a_row(admin_conn, scratch, verifier):
    for _ in range(3):
        ledger.append(admin_conn, entry(), scratch)
    assert verifier().status == "OK"
    _drop_trigger(admin_conn, scratch, "ANSWER_LEDGER_NO_UPDATE")
    db.use_schema(admin_conn, scratch)
    db.execute(admin_conn, "UPDATE ANSWER_LEDGER SET FINAL_ANSWER = 'Yes, retroactive refunds are fine.' WHERE LEDGER_ID = 2")
    admin_conn.commit()
    status = verifier()
    assert (status.status, status.first_bad) == ("BROKEN", 2) and "content" in status.detail


def test_verify_chain_catches_an_edited_citation(admin_conn, scratch, verifier):
    ledger.append(admin_conn, entry(), scratch)
    _drop_trigger(admin_conn, scratch, "CLAIM_CITATION_NO_UPDATE")
    db.use_schema(admin_conn, scratch)
    db.execute(admin_conn, "UPDATE CLAIM_CITATION SET VERDICT = 'SUPPORTED' WHERE CLAIM_NO = 1")
    admin_conn.commit()
    status = verifier()
    assert status.status == "BROKEN" and "citations" in status.detail


def test_verify_chain_catches_a_deleted_last_row(admin_conn, scratch, verifier):
    for _ in range(2):
        ledger.append(admin_conn, entry(), scratch)
    for trig in ("ANSWER_LEDGER_NO_DELETE", "CLAIM_CITATION_NO_DELETE"):
        _drop_trigger(admin_conn, scratch, trig)
    db.use_schema(admin_conn, scratch)
    db.execute(admin_conn, "DELETE FROM CLAIM_CITATION WHERE LEDGER_ID = 2")
    db.execute(admin_conn, "DELETE FROM ANSWER_LEDGER WHERE LEDGER_ID = 2")
    admin_conn.commit()
    status = verifier()
    assert status.status == "BROKEN" and "chain head" in status.detail


def test_the_owner_reads_masked_text_and_cannot_verify_through_the_mask(admin_conn, scratch, verifier):
    ledger.append(admin_conn, entry(), scratch)
    db.use_schema(admin_conn, scratch)
    row = db.query(admin_conn, "SELECT QUESTION_REDACTED, DRAFT_REDACTED, FINAL_ANSWER, DECISION FROM ANSWER_LEDGER")[0]
    assert row == ("[masked]", "[masked]", "[masked]", "ESCALATED")  # column masks: text only for ASOF_TEXT_READER
    with pytest.raises(db.DatabaseError) as err:  # a false "BROKEN" over masked values would be worse than refusing
        ledger.verify_chain(admin_conn, scratch)
    assert err.value.sqlstate == "75030"
    assert verifier().status == "OK"


def test_replay_shows_the_row_used_and_a_later_change(admin_conn, embeddings, scratch):
    seed.seed_policy(admin_conn, embeddings, scratch)
    db.use_schema(admin_conn, scratch)
    sys_start = db.query(admin_conn, "SELECT SYS_START FROM POLICY_CLAUSE WHERE CLAUSE_ID = 'BRV-002' "
                                     "AND VERSION_LABEL = 'v2'")[0][0]
    claim = {"pass": 1, "claim_no": 1, "text": "retroactive within 90 days", "area": "bereavement", "verdict": "SUPPORTED",
             "llm_verdict": "SUPPORTED", "rule_check": "MATCH", "clause_id": "BRV-002", "clause_version": "v2",
             "clause_bus_start": "2026-05-01", "clause_sys_start": sys_start.isoformat(sep=" "), "distance": 0.2,
             "quoted_span": "within 90 days"}
    a = ledger.append(admin_conn, entry(as_of=date(2026, 6, 2), decision="PASS", reason_code="ALL_SUPPORTED",
                                        verdicts={"claims": [claim]}), scratch)
    assert ledger.replay(admin_conn, a.ledger_id, scratch)["clauses"][0]["status"] == "UNCHANGED"
    time.sleep(1.1)
    db.execute(admin_conn, "UPDATE POLICY_CLAUSE FOR PORTION OF BUSINESS_TIME FROM ? TO ? "
                           "SET CLAUSE_TEXT = ?, VERSION_LABEL = 'v3' WHERE CLAUSE_ID = 'BRV-002'",
               ("2026-06-01", "9999-12-31", "Retroactive requests must be submitted within 30 days of ticket issue."))
    admin_conn.commit()
    r = ledger.replay(admin_conn, a.ledger_id, scratch)["clauses"][0]
    assert r["status"] == "CHANGED_SINCE_DECISION"
    assert r["used"]["version_label"] == "v2" and r["held_at_decision"]["version_label"] == "v2"
    assert r["in_force_now"]["version_label"] == "v3"


def test_demo_ledger_reset_recreates_the_tables(admin_conn, embeddings, settings, scratch):
    seed.seed_policy(admin_conn, embeddings, scratch)
    seed.seed_faq(admin_conn, embeddings, scratch)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, scratch)
    for _ in range(3):
        ledger.append(admin_conn, entry(), scratch)
    db.use_schema(admin_conn, scratch)
    policy_rows = db.query(admin_conn, "SELECT COUNT(*) FROM POLICY_CLAUSE")[0][0]

    assert schema.reset_ledger(admin_conn, scratch) == 3
    seed.seed_chain_head(admin_conn, scratch)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, scratch)

    assert db.query(admin_conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0] == 0
    assert db.query(admin_conn, "SELECT COUNT(*) FROM POLICY_CLAUSE")[0][0] == policy_rows
    triggers = {r[0].strip() for r in db.query(admin_conn, "SELECT TRIGNAME FROM SYSCAT.TRIGGERS WHERE TRIGSCHEMA = ? "
                                                            "AND VALID = 'Y'", (scratch,))}
    assert {"ANSWER_LEDGER_NO_UPDATE", "ANSWER_LEDGER_NO_DELETE", "CLAIM_CITATION_NO_UPDATE"} <= triggers
    invalid = db.query(admin_conn, "SELECT ROUTINENAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? AND VALID <> 'Y'",
                       (scratch,))
    assert invalid == []
    app = db.connect(settings, "app")
    try:
        assert ledger.append(app, entry(), scratch).ledger_id == 1
        assert ledger.verify_chain(app, scratch).status == "OK"
    finally:
        app.close()


def test_a_decision_must_name_a_known_policy_document(app_conn, test_schema):
    """FK_LEDGER_DOC: the ledger cannot record a check against a document Db2 does not hold."""
    with pytest.raises(db.DatabaseError) as err:
        ledger.append(app_conn, entry(doc_id="NO-SUCH-DOC"), test_schema)
    assert err.value.sqlstate == "23503"
    assert ledger.verify_chain(app_conn, test_schema).status == "OK"  # the refused append left no trace


def test_a_receipt_catches_a_ledger_rebuilt_consistently_which_verify_chain_cannot(admin_conn, settings, scratch, verifier):
    """The residual risk VERIFY_CHAIN leaves: an owner who drops and rebuilds the ledger with a changed answer
    gets a chain that verifies. The row hash the caller kept (the receipt) no longer matches."""
    app = db.connect(settings, "app")
    try:
        issued = ledger.append(app, entry(final_answer="Bereavement fares must be requested before travel."), scratch)
        assert ledger.check_receipt(app, issued.ledger_id, issued.row_hash, scratch).verdict == "INTACT"
        assert ledger.check_receipt(app, issued.ledger_id + 1, issued.row_hash, scratch).verdict == "MISSING"
    finally:
        app.close()

    schema.reset_ledger(admin_conn, scratch)  # the owner throws the ledger away ...
    seed.seed_chain_head(admin_conn, scratch)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, scratch)
    app = db.connect(settings, "app")
    try:  # ... and writes a different history through the proper procedure
        forged = ledger.append(app, entry(final_answer="You can claim it after you travel."), scratch)
        assert forged.ledger_id == issued.ledger_id and forged.row_hash != issued.row_hash
        assert verifier().status == "OK"  # the rebuilt chain is internally consistent
        check = ledger.check_receipt(app, issued.ledger_id, issued.row_hash.upper(), scratch)
    finally:
        app.close()
    assert (check.found, check.matches, check.verdict) == (True, False, "MISMATCH")


def test_an_evidence_pack_holds_the_decision_its_clauses_the_chain_and_the_receipt(app_conn, test_schema):
    issued = ledger.append(app_conn, entry(), test_schema)
    pack = ledger.evidence(app_conn, issued.ledger_id, test_schema)
    assert pack["asof_evidence"] == 1 and pack["chain"]["status"] == "OK"
    assert pack["ledger_entry"]["ledger_id"] == issued.ledger_id
    assert pack["receipt"]["row_hash"] == issued.row_hash == pack["ledger_entry"]["row_hash"]
    assert [c["clause_id"] for c in pack["ledger_entry"]["citations"] if c["clause_id"]] == ["BRV-002"]
    assert {c["clause_id"] for c in pack["replay"]["clauses"]} == {"BRV-002"}
    json.dumps(pack, default=str)  # serialisable as the download is
    assert ledger.evidence(app_conn, issued.ledger_id + 10_000, test_schema) is None


def test_an_anchor_catches_a_ledger_rebuilt_consistently_with_no_receipt_at_all(admin_conn, settings, scratch,
                                                                             verifier, tmp_path):
    """Nobody kept a receipt. The chain-head anchors, kept outside Db2 under a key Db2 never sees, still show
    that rows 1 and 2 are not the rows that were anchored, while VERIFY_CHAIN finds the rebuilt chain OK."""
    from asof import anchor

    anchors = anchor.AnchorLog(tmp_path, b"k" * 40, scratch)
    app = db.connect(settings, "app")
    try:
        for answer in ("Bereavement fares must be requested before travel.", "The first bag costs $35."):
            issued = ledger.append(app, entry(final_answer=answer), scratch)
            anchors.append(issued.ledger_id, issued.row_hash)
        ok = anchor.verify(anchors, app, scratch)
        assert (ok.status, ok.covered_through, ok.unanchored_rows) == ("OK", 2, 0)
    finally:
        app.close()

    schema.reset_ledger(admin_conn, scratch)  # the owner throws the ledger away ...
    seed.seed_chain_head(admin_conn, scratch)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, scratch)
    app = db.connect(settings, "app")
    try:  # ... and writes a different history through the proper procedure
        for answer in ("You can claim it after you travel.", "The first bag costs $35."):
            ledger.append(app, entry(final_answer=answer), scratch)
        assert verifier().status == "OK"  # internally consistent
        caught = anchor.verify(anchors, app, scratch)
    finally:
        app.close()
    assert (caught.status, caught.first_bad_anchor) == ("MISMATCH", 1)
