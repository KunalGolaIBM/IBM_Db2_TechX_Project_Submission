"""The specialist inbox in Db2: a held decision is answered once, by a person, with a reply that passed the check.
Db2 itself refuses a contradicting reply, an uncovered reply without a note, a second answer, a reviewer who
submitted the check, and any REVIEWED row that does not come through RESOLVE_ESCALATION."""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
from fakes import ScriptedLLM, claims, judge, verdict

from asof import db, ledger, policy, review, schema, seed
from asof.gate import Gate, GateRequest

pytestmark = pytest.mark.db2

MARCH = date(2026, 3, 10)
QUESTION = "My grandmother died. Can my 12-year-old fly to the funeral alone?"
DRAFT = "Yes, children aged 12 can fly alone with our escort service for $150."
UNCOVERED_CLAIM = ("Children aged 12 can fly alone with an escort service for $150.", "other", "eligibility")
SUPPORTED_REPLY = "Bereavement fares must be requested before travel begins."
BEFORE_TRAVEL = "Bereavement fares must be requested before travel begins"
CONTRADICTING_REPLY = "You can request the bereavement fare after you travel."
JUDGMENT_REPLY = "We do not offer an escort service for children travelling alone, so a 12-year-old must fly with an adult."
NOTE = "No clause covers unaccompanied minors; our operations manual does not allow it."


@pytest.fixture
def inbox(admin_conn, embeddings, settings):
    name = f"ASOF_R{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    yield name
    schema.drop(admin_conn, name)


def _gate(settings, embeddings, name, **queues) -> Gate:
    return Gate(ScriptedLLM(**queues), embeddings, lambda: db.connect(settings, "app"), name)


def _held(settings, embeddings, name, requested_by=None) -> int:
    """One ESCALATED decision: the draft's only claim is covered by no clause."""
    gate = _gate(settings, embeddings, name, extract=[claims(UNCOVERED_CLAIM)], judge=[judge(verdict(1, "NOT_COVERED"))])
    r = gate.check(GateRequest(QUESTION, DRAFT, MARCH, "AURELIA-CSP", "chat", requested_by))
    assert (r.decision, r.reason_code) == ("ESCALATED", "NOT_COVERED") and r.ledger_id
    return r.ledger_id


def _count(settings, name) -> int:
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, name)
        return int(db.query(conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0])


def test_a_held_decision_waits_in_the_inbox_until_a_checked_reply_answers_it(settings, embeddings, inbox):
    held = _held(settings, embeddings, inbox)
    with db.connection(settings, "app") as conn:
        q = review.queue(conn, inbox)
    assert [i["ledger_id"] for i in q["open"]] == [held] and q["counts"]["open"] == 1
    assert q["open"][0]["question"] == QUESTION and q["open"][0]["waiting_minutes"] >= 0

    gate = _gate(settings, embeddings, inbox,
                 extract=[claims(("Bereavement fares must be requested before travel begins.", "bereavement", "procedure"))],
                 judge=[judge(verdict(1, "SUPPORTED", "BRV-002", BEFORE_TRAVEL))])
    done = review.resolve(gate, held, SUPPORTED_REPLY, reviewer="maria")

    assert done.outcome == "SPECIALIST_CHECKED" and done.ledger_id == held + 1
    assert done.final_answer.startswith(SUPPORTED_REPLY) and "BRV-002 v1" in done.final_answer
    with db.connection(settings, "app") as conn:
        entry = ledger.get_entry(conn, done.ledger_id, inbox)
        assert (entry["decision"], entry["reason_code"], entry["channel"]) == ("REVIEWED", "SPECIALIST_CHECKED", "chat")
        assert entry["question_redacted"] == QUESTION and entry["as_of_date"] == MARCH  # copied by Db2 from the held row
        assert entry["verdicts"]["review"] == {"of_ledger_id": held, "reviewer": "maria", "note": None,
                                               "check_reason": "ALL_SUPPORTED", "on_judgment": False}
        assert [c["clause_version"] for c in entry["citations"]] == ["v1"]
        assert ledger.verify_chain(conn, inbox).status == "OK"
        q = review.queue(conn, inbox)
        assert q["open"] == [] and q["answered"][0]["review_ledger_id"] == done.ledger_id
        assert review.reviewed_for(conn, done.ledger_id, inbox)["escalated_ledger_id"] == held
        # A specialist's reply is a released answer like any other: change impact follows its citations.
        impact = {r["ref_id"]: r["status"] for r in policy.change_impact(conn, "BRV-002", inbox) if r["kind"] == "ANSWER"}
        assert impact == {str(done.ledger_id): "HISTORICALLY_VALID"}

    again = _gate(settings, embeddings, inbox)
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(again, held, SUPPORTED_REPLY)
    assert refused.value.status == 409


def test_a_reply_that_contradicts_the_policy_is_never_recorded(settings, embeddings, inbox):
    held = _held(settings, embeddings, inbox)
    before = _count(settings, inbox)
    gate = _gate(settings, embeddings, inbox,
                 extract=[claims(("The bereavement fare can be requested after travel.", "bereavement", "eligibility"))],
                 judge=[judge(verdict(1, "CONTRADICTED", "BRV-002", "A bereavement fare cannot be applied retroactively"))])
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(gate, held, CONTRADICTING_REPLY)
    assert refused.value.status == 409 and refused.value.check.reason_code == "CONTRADICTED"
    assert "contradicts the policy" in str(refused.value)
    assert _count(settings, inbox) == before  # nothing written: not the reply, not its check


def test_an_uncovered_reply_needs_the_specialists_note_and_records_it(settings, embeddings, inbox):
    held = _held(settings, embeddings, inbox)
    # The claim carries part of the sentence; the rest is judged as written too (a second judge call).
    uncovered = dict(extract=[claims(("A 12-year-old must fly with an adult.", "other", "eligibility"))],
                     judge=[judge(verdict(1, "NOT_COVERED")), judge(verdict(1, "NOT_COVERED"))])
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(_gate(settings, embeddings, inbox, **uncovered), held, JUDGMENT_REPLY, note="ok")
    assert refused.value.status == 422 and "note" in str(refused.value)

    done = review.resolve(_gate(settings, embeddings, inbox, **uncovered), held, JUDGMENT_REPLY, note=NOTE)
    assert done.outcome == "SPECIALIST_JUDGMENT" and done.final_answer == JUDGMENT_REPLY  # no clause to cite
    with db.connection(settings, "app") as conn:
        assert review.review_of(conn, held, inbox)["note"] == NOTE
        assert ledger.get_entry(conn, done.ledger_id, inbox)["verdicts"]["review"]["note"] == NOTE  # hashed too


def test_a_specialist_cannot_answer_their_own_check(settings, embeddings, inbox):
    held = _held(settings, embeddings, inbox, requested_by="maria")
    gate = _gate(settings, embeddings, inbox,
                 extract=[claims(("Bereavement fares must be requested before travel begins.", "bereavement", "procedure"))],
                 judge=[judge(verdict(1, "SUPPORTED", "BRV-002", BEFORE_TRAVEL))])
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(gate, held, SUPPORTED_REPLY, reviewer="maria")
    assert refused.value.status == 403  # SQLSTATE 75054, from Db2


def test_only_held_decisions_reach_the_inbox(settings, embeddings, inbox):
    gate = _gate(settings, embeddings, inbox, extract=[claims()])
    passed = gate.check(GateRequest("Hello", "Hi! How can I help?", MARCH, "AURELIA-CSP"))
    assert passed.decision == "PASS"
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(_gate(settings, embeddings, inbox), passed.ledger_id, SUPPORTED_REPLY)
    assert refused.value.status == 409
    with pytest.raises(review.ReviewError) as missing:
        review.detail(lambda: db.connect(settings, "app"), embeddings, 999, inbox)
    assert missing.value.status == 404


def _verdicts(of: int, verdict_: str, reason: str = "ALL_SUPPORTED", as_of: str = "2026-03-10", version: str = "v1",
              bus_start: str = "2026-01-01", **extra) -> str:
    return json.dumps({"version": 1, "as_of": as_of, "review": {"of_ledger_id": of, "check_reason": reason},
                       "claims": [{"pass": 1, "claim_no": 1, "text": "t", "area": "bereavement", "verdict": verdict_,
                                   "llm_verdict": verdict_, "rule_check": "NOT_APPLICABLE", "clause_id": "BRV-002",
                                   "clause_version": version, "clause_bus_start": bus_start,
                                   "clause_sys_start": "2026-11-08 00:00:00", "distance": 0.1, "quoted_span": "q"}],
                       **extra})


def _call(conn, name, held, verdicts, check_reason="ALL_SUPPORTED", doc="AURELIA-CSP", note=""):
    db.use_schema(conn, name)
    cur = conn.cursor()
    try:
        return cur.callproc("RESOLVE_ESCALATION", (held, str(uuid.uuid4()), doc, "r", "r", check_reason, note, "",
                                                   "m", "p", 1, verdicts, 0, " " * 64, " " * 40))
    finally:
        cur.close()


@pytest.mark.parametrize("verdict_, reason, doc, extra, sqlstate", [
    ("CONTRADICTED", "ALL_SUPPORTED", "AURELIA-CSP", {}, "75055"),  # the verdicts show a contradiction, whatever the reason
    ("SUPPORTED", "CONTRADICTED", "AURELIA-CSP", {}, "75055"),
    ("SUPPORTED", "UNCHECKED_DETAILS", "AURELIA-CSP", {}, "75055"),
    ("SUPPORTED", "ALL_SUPPORTED", "AURELIA-CSP", {"unchecked": ["$5"]}, "75055"),  # a detail no claim covered
    ("SUPPORTED", "ALL_SUPPORTED", "AURELIA-CSP", {"error": "timeout"}, "75055"),  # a check that failed
    ("NOT_COVERED", "NOT_COVERED", "AURELIA-CSP", {}, "75056"),  # no note
    ("NOT_COVERED", "ALL_SUPPORTED", "AURELIA-CSP", {}, "75057"),  # verdicts and reason disagree
    ("SUPPORTED", "ALL_SUPPORTED", "AURELIA-CSP", {"hashed_reason": "NOT_COVERED"}, "75057"),  # reason not the one hashed
    ("SUPPORTED", "ALL_SUPPORTED", "AURELIA-CSP", {"as_of": "2026-06-02"}, "75057"),  # checked for another date
    ("SUPPORTED", "ALL_SUPPORTED", "AURELIA-CSP", {"version": "v2", "bus_start": "2026-05-01"}, "75058"),  # not in force
    ("SUPPORTED", "ALL_SUPPORTED", "FERNHOLLOW-FEES", {}, "75053"),  # another policy document
])
def test_db2_refuses_what_the_inbox_must_never_record(settings, embeddings, inbox, verdict_, reason, doc, extra, sqlstate):
    held = _held(settings, embeddings, inbox)
    extra = dict(extra)
    hashed = extra.pop("hashed_reason", reason)
    shape = {k: extra.pop(k) for k in ("as_of", "version", "bus_start") if k in extra}
    with db.connection(settings, "app") as conn:
        with pytest.raises(Exception) as refused:
            _call(conn, inbox, held, _verdicts(held, verdict_, hashed, **shape, **extra), reason, doc)
        conn.rollback()
        assert db.wrap_error(refused.value, "x").sqlstate == sqlstate
        assert review.queue(conn, inbox)["counts"]["open"] == 1


def test_a_reviewed_row_can_only_come_through_resolve_escalation(settings, embeddings, inbox, admin_conn):
    held = _held(settings, embeddings, inbox)
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, inbox)
        cur = conn.cursor()
        with pytest.raises(Exception) as direct:  # the check's own entry point refuses a REVIEWED decision
            cur.callproc("APPEND_LEDGER", (str(uuid.uuid4()), "chat", "AURELIA-CSP", MARCH, "q", "d", "f", "REVIEWED",
                                           "SPECIALIST_CHECKED", "m", "p", 1, "{}", 0, " " * 64, None))
        conn.rollback()
        assert db.wrap_error(direct.value, "x").sqlstate == "75004"
        with pytest.raises(Exception) as hidden:  # and the procedure behind both is granted to nobody
            cur.callproc("APPEND_LEDGER_ROW", (str(uuid.uuid4()), "chat", "AURELIA-CSP", MARCH, "q", "d", "f",
                                               "REVIEWED", "SPECIALIST_CHECKED", "m", "p", 1, "{}", 0, " " * 64, None))
        conn.rollback()
        assert db.wrap_error(hidden.value, "x").sqlstate == "42501"
        with pytest.raises(db.DatabaseError) as insert:
            db.execute(conn, "INSERT INTO ESCALATION_REVIEW (ESCALATED_LEDGER_ID, REVIEW_LEDGER_ID, OUTCOME) "
                             "VALUES (?, ?, 'SPECIALIST_CHECKED')", (held, held))
        conn.rollback()
        assert insert.value.sqlstate == "42501"
        out = _call(conn, inbox, held, _verdicts(held, "SUPPORTED"))
        conn.commit()
        assert str(out[14]).strip() == "SPECIALIST_CHECKED"
        assert ledger.verify_chain(conn, inbox).status == "OK"
    db.use_schema(admin_conn, inbox)
    with pytest.raises(db.DatabaseError) as update:  # append-only, even for the owner
        db.execute(admin_conn, "UPDATE ESCALATION_REVIEW SET NOTE = 'edited'")
    admin_conn.rollback()
    assert update.value.sqlstate == "75001"


def test_a_contradiction_the_extractor_missed_is_still_refused(settings, embeddings, inbox):
    """Seen with a small local model: extraction found no claim in "You can request the bereavement fare after you
    travel." A reply that talks policy but yields no claim has its policy sentences judged as written, so the
    contradiction is refused, not sent on a note."""
    held = _held(settings, embeddings, inbox)
    missed = dict(extract=[claims()],
                  judge=[judge(verdict(1, "CONTRADICTED", "BRV-002", "A bereavement fare cannot be applied retroactively"))])
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(_gate(settings, embeddings, inbox, **missed), held, CONTRADICTING_REPLY)
    assert refused.value.status == 409 and refused.value.check.reason_code == "CONTRADICTED"
    assert [c.text for c in refused.value.check.claims] == [CONTRADICTING_REPLY]  # judged as written
    # The same sentence, which no clause covers, goes out only with the specialist's note.
    uncovered = dict(extract=[claims()], judge=[judge(verdict(1, "NOT_COVERED"))])
    with pytest.raises(review.ReviewError) as no_note:
        review.resolve(_gate(settings, embeddings, inbox, **uncovered), held, JUDGMENT_REPLY)
    assert no_note.value.status == 422
    done = review.resolve(_gate(settings, embeddings, inbox, **uncovered), held, JUDGMENT_REPLY, note=NOTE)
    assert done.outcome == "SPECIALIST_JUDGMENT"
    small_talk = review.resolve(_gate(settings, embeddings, inbox, extract=[claims()]),
                                _held(settings, embeddings, inbox), "Thank you for your patience. I am sorry for your loss.")
    assert small_talk.outcome == "SPECIALIST_CHECKED"  # nothing a policy decides: nothing to judge, no note needed


def test_a_contradiction_beside_a_supported_claim_is_still_refused(settings, embeddings, inbox):
    """The review's case: the extractor found the bag claim and missed the bereavement one. Every policy sentence no
    claim carries is judged as written, so the reply is refused."""
    held = _held(settings, embeddings, inbox)
    reply = "The first checked bag costs $35 each way. " + CONTRADICTING_REPLY
    gate = _gate(settings, embeddings, inbox,
                 extract=[claims(("The first checked bag costs $35 each way.", "baggage", "amount"))],
                 judge=[judge(verdict(1, "SUPPORTED", "BAG-001", "The first checked bag costs $35 each way")),
                        judge(verdict(1, "CONTRADICTED", "BRV-002", "A bereavement fare cannot be applied retroactively"))])
    with pytest.raises(review.ReviewError) as refused:
        review.resolve(gate, held, reply)
    check = refused.value.check
    assert refused.value.status == 409 and check.reason_code == "CONTRADICTED"
    assert [(c.claim_no, c.verdict) for c in check.claims] == [(1, "SUPPORTED"), (2, "CONTRADICTED")]


def test_the_specialists_note_is_redacted_before_it_is_hashed(settings, embeddings, inbox):
    held = _held(settings, embeddings, inbox)
    uncovered = dict(extract=[claims(("A 12-year-old must fly with an adult.", "other", "eligibility"))],
                     judge=[judge(verdict(1, "NOT_COVERED")), judge(verdict(1, "NOT_COVERED"))])
    note = "Called the customer on 514-555-0199 and at jane.doe@example.com; operations confirmed no escort service."
    done = review.resolve(_gate(settings, embeddings, inbox, **uncovered), held, JUDGMENT_REPLY, note=note)
    with db.connection(settings, "app") as conn:
        stored = review.review_of(conn, held, inbox)["note"]
        hashed = ledger.get_entry(conn, done.ledger_id, inbox)["verdicts"]["review"]["note"]
    assert stored == hashed and "514-555-0199" not in stored and "jane.doe@example.com" not in stored
    assert "operations confirmed" in stored


def test_the_inbox_shows_each_claims_version_with_the_dates_it_was_in_force(settings, embeddings, inbox):
    """A held claim checked against BRV-002 v1 shows v1's end (1 May 2026), not an open end."""
    gate = _gate(settings, embeddings, inbox,
                 extract=[claims(("Bereavement fares must be requested before travel begins.", "bereavement", "procedure"),
                                 UNCOVERED_CLAIM)],
                 judge=[judge(verdict(1, "SUPPORTED", "BRV-002", BEFORE_TRAVEL), verdict(2, "NOT_COVERED"))])
    r = gate.check(GateRequest(QUESTION, DRAFT, MARCH, "AURELIA-CSP", "chat"))
    assert (r.decision, r.reason_code) == ("ESCALATED", "NOT_COVERED")
    d = review.detail(lambda: db.connect(settings, "app"), embeddings, r.ledger_id, inbox)
    by_clause = {c["clause_id"]: c for c in d["claims"]}
    assert str(by_clause["BRV-002"]["effective_to"]) == "2026-05-01"
    assert [c["effective_to"] for c in d["claims"] if not c.get("clause_id")] == [None]
