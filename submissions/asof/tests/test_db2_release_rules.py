"""Db2 integration: the release rules (08_release_rules.sql) and PREVIEW_POLICY_CHANGE.

Db2 refuses to store a PASS or CORRECTED decision unless every claim it releases is SUPPORTED by a clause version in
force on the customer's date and quoted from that version's text; a preview applies a change and undoes it itself.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import date

import pytest
from fakes import ScriptedLLM, claims, judge, verdict

from asof import db, ledger, policy, schema, seed
from asof.gate import HOLDING_REPLY, Gate, GateRequest

pytestmark = pytest.mark.db2

MARCH, JUNE = date(2026, 3, 10), date(2026, 6, 2)
BEFORE_TRAVEL = "Bereavement fares must be requested before travel begins."
PET_CHANGE = policy.PolicyChange(
    clause_id="PET-001", effective_from=date(2026, 12, 1), version_label="v2",
    clause_text="Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more "
                "than 8 kg. The pet fee is $125 each way.",
    rule={"max_pet_weight_kg": 8, "pet_fee_usd": 125}, change_note="Pet fee rises to $125 from 1 December 2026")


@pytest.fixture(scope="module")
def world(admin_conn, embeddings, settings):
    name = f"ASOF_L{uuid.uuid4().hex[:6].upper()}"
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


def claim(**kw) -> dict:
    """A released claim citing BRV-002 v1 (in force 2026-01-01 to 2026-04-30), quoted from its first sentence."""
    return {"pass": 1, "claim_no": 1, "text": "You must ask before you travel.", "area": "bereavement",
            "verdict": "SUPPORTED", "llm_verdict": "SUPPORTED", "rule_check": "NOT_APPLICABLE", "clause_id": "BRV-002",
            "clause_version": "v1", "clause_bus_start": "2026-01-01", "clause_sys_start": None, "distance": 0.1,
            "quoted_span": BEFORE_TRAVEL} | kw


def entry(decision: str, items: list[dict], as_of: date = MARCH, doc_id: str = "AURELIA-CSP") -> ledger.LedgerEntry:
    return ledger.LedgerEntry(str(uuid.uuid4()), "api", doc_id, as_of, "Can I get the bereavement fare after I fly?",
                              "draft", "final", decision, "ALL_SUPPORTED", "test", "test", 5, {"claims": items})


def append(settings, world: str, e: ledger.LedgerEntry) -> ledger.Appended:
    with db.connection(settings, "app") as conn:
        return ledger.append(conn, e, world)


def refused(settings, world: str, e: ledger.LedgerEntry) -> str | None:
    with pytest.raises(db.DatabaseError) as err:
        append(settings, world, e)
    return err.value.sqlstate


@pytest.mark.parametrize("decision, items, kwargs", [
    ("PASS", [claim()], {}),
    ("PASS", [], {}),  # no policy claims: nothing to back
    ("PASS", [claim(quoted_span="“Bereavement  FARES must be requested\nbefore travel begins.”")], {}),
    ("PASS", [claim(clause_version="v2", clause_bus_start="2026-05-01",
                    quoted_span="A retroactive request must be submitted within 90 days")], {"as_of": JUNE}),
    ("CORRECTED", [claim(verdict="CONTRADICTED", quoted_span=None), claim(**{"pass": 2})], {}),
    ("ESCALATED", [claim(verdict="NOT_COVERED", clause_id=None, clause_version=None, clause_bus_start=None,
                         quoted_span=None)], {"as_of": JUNE}),  # a hold is never refused
], ids=["pass", "pass-no-claims", "quote-case-spacing-curly-quotes", "v2-in-june", "corrected", "escalated"])
def test_a_release_the_policy_backs_is_stored(settings, world, decision, items, kwargs):
    assert append(settings, world, entry(decision, items, **kwargs)).ledger_id >= 1


@pytest.mark.parametrize("decision, items, kwargs, sqlstate", [
    ("PASS", [claim(verdict="NOT_COVERED")], {}, "75080"),
    ("PASS", [claim(clause_id=None, clause_version=None, clause_bus_start=None)], {}, "75080"),
    ("CORRECTED", [claim(), claim(**{"pass": 2, "verdict": "CONTRADICTED"})], {}, "75080"),
    ("PASS", [claim()], {"as_of": JUNE}, "75081"),  # v1 ended on 30 April
    ("PASS", [claim(clause_version="v2")], {}, "75081"),  # the label does not match the version cited
    ("PASS", [claim()], {"doc_id": "FERNHOLLOW-FEES"}, "75081"),  # an airline clause on a bank decision
    ("PASS", [claim(quoted_span="Bereavement fares may always be requested after travel.")], {}, "75082"),
    ("PASS", [claim(quoted_span=None)], {}, "75082"),
    ("PASS", [claim(quoted_span="must be")], {}, "75082"),  # in the text, but too short to stand alone
    ("CORRECTED", [claim(), claim(**{"pass": 2, "quoted_span": "no refund of the fare is ever given"})], {}, "75082"),
    ("PASS", [claim(), claim(**{"pass": 2})], {}, "75083"),  # a PASS has no re-check
    ("CORRECTED", [claim(verdict="CONTRADICTED")], {}, "75083"),  # a correction without its re-check
    ("PASS", [claim(), {"pass": 1, "verdict": "NOT_COVERED"}], {}, "75083"),  # an entry Db2 cannot read as a claim
    ("PASS", [claim(claim_no=1 + i % 8, **{"pass": 1 + i // 8}) for i in range(17)], {}, "75003"),
], ids=["not-supported", "no-clause", "recheck-contradicted", "not-in-force", "wrong-label", "other-document",
        "quote-not-in-text", "no-quote", "short-quote", "recheck-quote", "pass-with-recheck", "corrected-no-recheck",
        "unreadable-entry", "too-many-claims"])
def test_db2_refuses_a_release_the_policy_does_not_back(settings, world, decision, items, kwargs, sqlstate):
    assert refused(settings, world, entry(decision, items, **kwargs)) == sqlstate


def test_the_refusals_leave_the_chain_intact(settings, world):
    with db.connection(settings, "app") as conn:
        assert ledger.verify_chain(conn, world).status == "OK"


@pytest.mark.parametrize("decision, sqlstate", [("PASS", "75081"), ("CORRECTED", "75083")])
def test_the_trigger_refuses_a_direct_insert_even_by_the_owner(admin_conn, world, decision, sqlstate):
    db.use_schema(admin_conn, world)
    with pytest.raises(db.DatabaseError) as err:
        db.execute(admin_conn, "INSERT INTO ANSWER_LEDGER (LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, "
                               "QUESTION_REDACTED, DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, "
                               "PROMPT_VERSION, LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH) VALUES (900000, ?, "
                               "CURRENT TIMESTAMP, 'api', 'AURELIA-CSP', ?, 'q', 'd', 'f', ?, 'ALL_SUPPORTED', 'x', 'p', 1, "
                               "?, ?, ?)",
                   (str(uuid.uuid4()), JUNE, decision, json.dumps({"claims": [claim()]}), "0" * 64, "f" * 64))
    admin_conn.rollback()
    assert err.value.sqlstate == sqlstate


def test_a_policy_change_between_the_check_and_the_record_is_held_not_released(settings, world, embeddings):
    """The check saw PET-001 v1 in force on 15 December; the editor commits v2 from 1 December before the decision is
    recorded. Db2 refuses the PASS (75081), and the gate records a hold instead: the customer gets the holding reply."""
    draft = "The pet fee is $100 each way."
    llm = ScriptedLLM(extract=[claims((draft, "pets", "amount"))],
                      judge=[judge(verdict(1, "SUPPORTED", "PET-001", "The pet fee is $100 each way"))])
    gate = Gate(llm, embeddings, lambda: db.connect(settings, "app"), world, investigate=False)
    real_judge = gate.judge

    def judge_then_change(*args, **kwargs):
        out = real_judge(*args, **kwargs)
        with db.connection(settings, "editor") as editor:
            policy.apply_change(editor, PET_CHANGE, embeddings, world)
        return out

    gate.judge = judge_then_change  # type: ignore[method-assign]
    r = gate.check(GateRequest("What does my cat cost to fly?", draft, date(2026, 12, 15), "AURELIA-CSP", "chat"))

    assert (r.decision, r.reason_code, r.final_answer) == ("ESCALATED", "RELEASE_REFUSED", HOLDING_REPLY)
    assert r.released and r.ledger_id is not None and "75081" in (r.error or "")
    with db.connection(settings, "app") as conn:
        held = ledger.get_entry(conn, r.ledger_id, world)
        assert ledger.verify_chain(conn, world).status == "OK"
    assert held is not None and (held["decision"], held["reason_code"]) == ("ESCALATED", "RELEASE_REFUSED")
    assert held["final_answer"] == HOLDING_REPLY and draft not in held["final_answer"]
    assert held["verdicts"]["release_refused"]["sqlstate"] == "75081"
    assert [(c["clause_id"], c["clause_version"]) for c in held["citations"]] == [("PET-001", "v1")]


# ---------- PREVIEW_POLICY_CHANGE ----------

@pytest.fixture
def pets(admin_conn, embeddings, settings):
    """A fresh schema with two answers citing PET-001 v1 (20 November and 15 December), so a change from 1 December
    leaves one historically valid and makes one stale, and flags the help-centre answer."""
    name = f"ASOF_V{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
        pet = claim(text="The pet fee is $100 each way.", area="pets", clause_id="PET-001", rule_check="MATCH",
                    quoted_span="The pet fee is $100 each way")
        for on in (date(2026, 11, 20), date(2026, 12, 15)):
            append(settings, name, entry("PASS", [pet], as_of=on))
    except Exception:
        schema.drop(admin_conn, name)
        raise
    time.sleep(1.1)  # the change must get a later system time than the seed rows
    yield name
    schema.drop(admin_conn, name)


SNAPSHOT = {
    # Every row the clause table ever held, with its system-time period: a rolled-back change must leave no trace here.
    "clauses": "SELECT CLAUSE_ID, VERSION_LABEL, BUS_START, BUS_END, SYS_START, SYS_END, CLAUSE_TEXT, RULE_JSON, CHANGE_NOTE "
               "FROM POLICY_CLAUSE FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' "
               "ORDER BY CLAUSE_ID, BUS_START, SYS_START",
    "history": "SELECT CLAUSE_ID, VERSION_LABEL, BUS_START, SYS_START, SYS_END FROM POLICY_CLAUSE_HIST "
               "ORDER BY CLAUSE_ID, BUS_START, SYS_START",
    "published": "SELECT ANSWER_ID, STATUS, CITED_VERSION, APPLIES_FROM, APPLIES_TO FROM PUBLISHED_ANSWER ORDER BY ANSWER_ID",
    "ledger": "SELECT LEDGER_ID, DECISION, ROW_HASH FROM ANSWER_LEDGER ORDER BY LEDGER_ID",
    "citations": "SELECT LEDGER_ID, PASS_NO, CLAIM_NO, CLAUSE_ID, CLAUSE_VERSION FROM CLAIM_CITATION ORDER BY 1, 2, 3",
    "head": "SELECT LAST_LEDGER_ID, LAST_HASH FROM CHAIN_HEAD",
    "suggestions": "SELECT COUNT(*) FROM ANSWER_SUGGESTION",
    "notices": "SELECT COUNT(*) FROM CORRECTION_NOTICE",
}


def snapshot(admin_conn, name: str) -> dict[str, list]:
    db.use_schema(admin_conn, name)
    out = {k: db.query(admin_conn, sql) for k, sql in SNAPSHOT.items()}
    admin_conn.commit()
    return out


def test_a_preview_leaves_nothing_behind_and_reports_exactly_what_the_change_does(settings, embeddings, pets, admin_conn):
    before = snapshot(admin_conn, pets)
    with db.connection(settings, "editor") as editor:
        preview = policy.preview_change(editor, PET_CHANGE, embeddings, pets)
        assert snapshot(admin_conn, pets) == before  # history table and system-time periods included
        applied = policy.apply_change(editor, PET_CHANGE, embeddings, pets)
        real = policy.change_impact(editor, PET_CHANGE.clause_id, pets)
    assert preview["preview"] is True and preview["impact"] == real  # every column of every row, in Db2's order
    assert {k: preview[k] for k in applied} == applied == {"rows_changed": 1, "published_flagged": 1, "embedded_in": "app"}
    assert sorted(r["status"] for r in real) == ["HISTORICALLY_VALID", "NEEDS_REVIEW", "STALE"]
    after = snapshot(admin_conn, pets)
    assert len(after["history"]) == len(before["history"]) + 1  # the real change did land, history and all


def test_db2_undoes_a_preview_itself_even_on_an_autocommit_connection(settings, embeddings, pets, admin_conn):
    before = snapshot(admin_conn, pets)
    with db.connection(settings, "editor", autocommit=True) as editor:
        preview = policy.preview_change(editor, PET_CHANGE, embeddings, pets)
    assert len(preview["impact"]) == 3
    assert snapshot(admin_conn, pets) == before


def test_a_refused_preview_raises_the_procedure_error_and_leaves_nothing(settings, embeddings, pets, admin_conn):
    before = snapshot(admin_conn, pets)
    with db.connection(settings, "editor", autocommit=True) as editor:
        with pytest.raises(db.DatabaseError) as err:
            policy.preview_change(editor, PET_CHANGE.model_copy(update={"version_label": "v1"}), embeddings, pets)
    assert err.value.sqlstate == "75012"  # APPLY_POLICY_CHANGE's own refusal, re-raised unchanged
    assert snapshot(admin_conn, pets) == before


def test_only_the_editor_may_preview(settings, embeddings, pets):
    with db.connection(settings, "app") as app:
        with pytest.raises(db.DatabaseError) as err:
            policy.preview_change(app, PET_CHANGE, embeddings, pets)
    assert err.value.sqlstate == "42501"


@pytest.fixture(scope="module")
def pets_unpublished(admin_conn, embeddings, settings):
    """The pets schema without its help-centre answers: the change's UPDATE of published answers then touches no row,
    which raises NOT FOUND inside APPLY_POLICY_CHANGE (the case a rail clause hit on 12 Nov 2026)."""
    name = f"ASOF_U{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
        pet = claim(text="The pet fee is $100 each way.", area="pets", clause_id="PET-001", rule_check="MATCH",
                    quoted_span="The pet fee is $100 each way")
        for on in (date(2026, 11, 20), date(2026, 12, 15)):
            append(settings, name, entry("PASS", [pet], as_of=on))
    except Exception:
        schema.drop(admin_conn, name)
        raise
    time.sleep(1.1)
    yield name
    schema.drop(admin_conn, name)


def test_a_preview_reports_the_impact_when_no_published_answer_cites_the_clause(settings, embeddings, pets_unpublished):
    with db.connection(settings, "editor") as editor:
        preview = policy.preview_change(editor, PET_CHANGE, embeddings, pets_unpublished)
        real = policy.change_impact(editor, PET_CHANGE.clause_id, pets_unpublished)
    assert preview["published_flagged"] == 0
    assert sorted(r["status"] for r in preview["impact"]) == ["HISTORICALLY_VALID", "STALE"]
    # what CHANGE_IMPACT says today, before the change: both answers still cite the version in force for their date
    assert sorted(r["status"] for r in real) == ["HISTORICALLY_VALID", "HISTORICALLY_VALID"]
