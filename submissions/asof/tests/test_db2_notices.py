"""Correction notices in Db2: the agent drafts one for each answer a policy change made stale for its customer's date,
the correction passes the full check on that date, and only a specialist's approval marks it sent. Db2 verifies every
claim made about a notice before storing it, and refuses to send one whose policy changed again since."""

from __future__ import annotations

import json
import time
import uuid
from datetime import date

import pytest
from fakes import ScriptedLLM, claims, judge, verdict

from asof import db, impactagent, ledger, notices, policy, schema, seed
from asof.gate import Gate
from asof.schemas import RewriteResult

pytestmark = pytest.mark.db2

V2_TEXT = ("Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more than 8 kg. "
           "The pet fee is $125 each way.")
PET_V2 = policy.PolicyChange(clause_id="PET-001", effective_from=date(2026, 12, 1), version_label="v2", clause_text=V2_TEXT,
                             rule={"max_pet_weight_kg": 8, "pet_fee_usd": 125}, change_note="Pet fee rises to $125")
PET_V3 = PET_V2.model_copy(update={"version_label": "v3", "clause_text": V2_TEXT.replace("$125", "$150"),
                                   "rule": {"max_pet_weight_kg": 8, "pet_fee_usd": 150}, "change_note": "Pet fee to $150"})
NOVEMBER, DECEMBER = date(2026, 11, 20), date(2026, 12, 15)
CORRECTION = "Your cat can travel in the cabin with you. The pet fee is $125 each way."


def _answer(conn, name, as_of: date, version="v1", bus_start="2026-01-01", text="The pet fee is $100 each way.") -> int:
    claim = {"pass": 1, "claim_no": 1, "text": text, "area": "pets", "verdict": "SUPPORTED", "llm_verdict": "SUPPORTED",
             "rule_check": "MATCH", "clause_id": "PET-001", "clause_version": version, "clause_bus_start": bus_start,
             "clause_sys_start": None, "distance": 0.2, "quoted_span": text}
    e = ledger.LedgerEntry(str(uuid.uuid4()), "chat", "AURELIA-CSP", as_of, "Can my cat fly with me, and what does it cost?",
                           text, text + "\n\nPolicy references: PET-001 " + version + ".", "PASS", "ALL_SUPPORTED", "test",
                           "test", 5, {"claims": [claim]})
    return ledger.append(conn, e, name).ledger_id


@pytest.fixture
def stale(admin_conn, embeddings, settings):
    """A scratch schema with two pet-fee answers (November and December trips), then the pet fee raised to $125 from
    1 December: the December answer is now stale, the November one is still right for its date."""
    name = f"ASOF_N{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
        with db.connection(settings, "app") as app:
            ids = {"november": _answer(app, name, NOVEMBER), "december": _answer(app, name, DECEMBER)}
        time.sleep(1.1)
        with db.connection(settings, "editor") as editor:
            policy.apply_change(editor, PET_V2, embeddings, name)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    yield name, ids
    schema.drop(admin_conn, name)


def _gate(settings, embeddings, name, **queues) -> Gate:
    return Gate(ScriptedLLM(**queues), embeddings, lambda: db.connect(settings, "app"), name)


def _checked_correction(settings, embeddings, name) -> Gate:
    return _gate(settings, embeddings, name, rewrite=[RewriteResult(answer=CORRECTION)],
                 extract=[claims(("A cat can travel in the cabin.", "pets", "eligibility"),
                                 ("The pet fee is $125 each way.", "pets", "amount"))],
                 judge=[judge(verdict(1, "SUPPORTED", "PET-001", "Small cats and dogs may travel in the cabin"),
                              verdict(2, "SUPPORTED", "PET-001", "The pet fee is $125 each way"))])


def test_the_agent_drafts_a_checked_notice_only_for_the_answer_that_went_stale(settings, embeddings, stale):
    name, ids = stale
    drafted = impactagent.draft_notices(_checked_correction(settings, embeddings, name), "PET-001", requested_by="rita")

    assert [d["ledger_id"] for d in drafted] == [ids["december"]]  # November's answer is still right for its date
    d = drafted[0]
    assert (d["cited_version"], d["current_version"], d["check_decision"]) == ("v1", "v2", "PASS")
    assert "version v1" in d["notice"] and "version v2 applies to your date now" in d["notice"]
    assert "15 December 2026" in d["notice"] and "$125" in d["notice"] and "PET-001 v2" in d["notice"]
    with db.connection(settings, "app") as conn:
        [n] = notices.list_notices(conn, "PET-001", None, name)
        assert (n["status"], n["requested_by"], n["check_ledger_id"]) == ("PENDING", "rita", d["check_ledger_id"])
        check = ledger.get_entry(conn, d["check_ledger_id"], name)
        assert (check["channel"], check["as_of_date"], check["decision"]) == ("email", DECEMBER, "PASS")
        assert [c["clause_version"] for c in check["citations"]] == ["v2", "v2"]  # checked against the new version

    # A second run finds nothing to do: the stale answer already has an open notice.
    assert impactagent.draft_notices(_gate(settings, embeddings, name), "PET-001") == []

    with db.connection(settings, "app") as conn:
        notices.decide(conn, n["notice_id"], True, "rita", name)
        [sent] = notices.list_notices(conn, "PET-001", "SENT", name)
        assert sent["decided_by_user"] == "rita" and sent["decided_at"] is not None
        with pytest.raises(db.DatabaseError) as again:
            notices.decide(conn, n["notice_id"], False, "rita", name)
        assert again.value.sqlstate == "75063"


def _add(conn, name, ledger_id, *, cited="v1", current="v2", decision="PASS", check=0):
    return notices.add(conn, ledger_id=ledger_id, clause_id="PET-001", cited=cited, current=current, correction="c",
                       notice="n", check_decision=decision, check_ledger_id=check, trace=[], requested_by=None, schema=name)


def test_db2_checks_every_claim_made_about_a_notice(settings, stale):
    name, ids = stale
    with db.connection(settings, "app") as conn:
        good_check = _answer(conn, name, DECEMBER, "v2", "2026-12-01", "The pet fee is $125 each way.")
        other_date = _answer(conn, name, date(2026, 12, 20), "v2", "2026-12-01", "The pet fee is $125 each way.")
        for kwargs, ledger_id, sqlstate in [
            ({"check": good_check}, ids["november"], "75061"),             # not stale: v1 still applies in November
            ({"check": good_check, "cited": "v2"}, ids["december"], "75060"),  # the answer never cited v2
            ({"check": other_date}, ids["december"], "75062"),             # a check for another customer date
            ({"check": good_check, "decision": "CORRECTED"}, ids["december"], "75062"),  # not that check's decision
            ({"check": 0, "decision": "PASS"}, ids["december"], "75062"),  # a released check must name its row
        ]:
            with pytest.raises(db.DatabaseError) as refused:
                _add(conn, name, ledger_id, **kwargs)
            assert refused.value.sqlstate == sqlstate, kwargs
        first = _add(conn, name, ids["december"], check=good_check)
        with pytest.raises(db.DatabaseError) as twice:  # one open notice per answer and version
            _add(conn, name, ids["december"], check=good_check)
        assert twice.value.sqlstate == "23505"
        notices.decide(conn, first, False, None, name)
        assert _add(conn, name, ids["december"], check=good_check) > first  # a rejected draft makes way


def test_a_held_correction_can_be_rejected_but_never_sent(settings, stale):
    name, ids = stale
    with db.connection(settings, "app") as conn:
        held = _add(conn, name, ids["december"], decision="ESCALATED")
        with pytest.raises(db.DatabaseError) as refused:
            notices.decide(conn, held, True, None, name)
        assert refused.value.sqlstate == "75064"
        notices.decide(conn, held, False, None, name)
        assert notices.list_notices(conn, None, "REJECTED", name)[0]["notice_id"] == held


def test_a_notice_is_not_sent_if_the_policy_changed_again_since_it_was_drafted(settings, embeddings, stale):
    name, ids = stale
    with db.connection(settings, "app") as conn:
        check = _answer(conn, name, DECEMBER, "v2", "2026-12-01", "The pet fee is $125 each way.")
        pending = _add(conn, name, ids["december"], check=check)
    time.sleep(1.1)
    with db.connection(settings, "editor") as editor:
        policy.apply_change(editor, PET_V3, embeddings, name)
    with db.connection(settings, "app") as conn:
        with pytest.raises(db.DatabaseError) as refused:
            notices.decide(conn, pending, True, None, name)
        assert refused.value.sqlstate == "75065"


def test_notices_are_written_only_through_the_procedures_and_never_rewritten(settings, admin_conn, stale):
    name, ids = stale
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, name)
        with pytest.raises(db.DatabaseError) as insert:
            db.execute(conn, "INSERT INTO CORRECTION_NOTICE (LEDGER_ID, CLAUSE_ID, CITED_VERSION, CURRENT_VERSION, "
                             "AS_OF_DATE, CORRECTION_TEXT, NOTICE_TEXT, CHECK_DECISION, AGENT_TRACE) "
                             "VALUES (?, 'PET-001', 'v1', 'v2', '2026-12-15', 'c', 'n', 'ESCALATED', '[]')", (ids["december"],))
        conn.rollback()
        assert insert.value.sqlstate == "42501"
        nid = _add(conn, name, ids["december"], decision="ESCALATED")
    db.use_schema(admin_conn, name)
    for sql in ("UPDATE CORRECTION_NOTICE SET NOTICE_TEXT = 'edited' WHERE NOTICE_ID = ?",
                "DELETE FROM CORRECTION_NOTICE WHERE NOTICE_ID = ?"):
        with pytest.raises(db.DatabaseError) as refused:  # even the owner
            db.execute(admin_conn, sql, (nid,))
        admin_conn.rollback()
        assert refused.value.sqlstate == "75001"
    trace = json.loads(db.query(admin_conn, "SELECT AGENT_TRACE FROM CORRECTION_NOTICE WHERE NOTICE_ID = ?", (nid,))[0][0])
    assert trace == []


def test_the_notice_wording_states_no_policy_of_its_own():
    from datetime import datetime

    text = notices.compose(answered_at=datetime(2026, 11, 8, 9, 30), as_of=DECEMBER, question="What is the pet fee?",
                           clause_id="PET-001", clause_title="Pets in the cabin", cited="v1", current="v2",
                           current_from=date(2026, 12, 1), correction=CORRECTION + "\n\nPolicy references: PET-001 v2.")
    fixed = text.replace(CORRECTION, "")
    assert "$" not in fixed.split("What applies to your date now:")[0]  # no amount outside the checked correction
    assert text.startswith("A correction to our reply of 8 November 2026") and "15 December 2026" in text
    assert notices.without_references("Yes.\n\nPolicy references: PET-001 v1 (in effect from 2026-01-01).") == "Yes."
