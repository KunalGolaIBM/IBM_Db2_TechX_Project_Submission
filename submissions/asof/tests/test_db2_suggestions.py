"""Change-impact suggestions in Db2: the agent drafts and checks, only the editor publishes,
and publishing splits the help-centre answer in time instead of rewriting its past."""

from __future__ import annotations

import time
import uuid
from datetime import date

import pytest
from fakes import ScriptedLLM, claims, judge, verdict

from asof import db, impactagent, policy, schema, seed
from asof.gate import Gate
from asof.schemas import RewriteResult

pytestmark = pytest.mark.db2

NEW_TEXT = ("Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more than 8 kg. "
            "The pet fee is $125 each way.")
CHANGE = policy.PolicyChange(clause_id="PET-001", effective_from=date(2026, 12, 1), version_label="v2", clause_text=NEW_TEXT,
                             rule={"max_pet_weight_kg": 8, "pet_fee_usd": 125}, change_note="Pet fee rises to $125")
DECEMBER = date(2026, 12, 1)


@pytest.fixture
def changed(admin_conn, embeddings, settings):
    """A scratch schema where the pet fee went up from 1 December, so PA-PET-001 needs review."""
    name = f"ASOF_S{uuid.uuid4().hex[:6].upper()}"
    schema.install(admin_conn, name)
    seed.seed_policy(admin_conn, embeddings, name)
    seed.seed_chain_head(admin_conn, name)
    seed.seed_published_answers(admin_conn, name)
    seed.seed_faq(admin_conn, embeddings, name)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    time.sleep(1.1)
    editor = db.connect(settings, "editor")
    try:
        policy.apply_change(editor, CHANGE, embeddings, name)
    finally:
        editor.close()
    yield name
    schema.drop(admin_conn, name)


def _connect(settings, role):
    return lambda: db.connect(settings, role)


def test_the_agent_drafts_checks_and_stores_a_fix_that_only_the_editor_can_publish(settings, embeddings, changed):
    llm = ScriptedLLM(
        rewrite=[RewriteResult(answer="Yes. Small cats and dogs can travel in the cabin if the pet and its carrier together "
                                      "weigh no more than 8 kg. The pet fee is $125 each way.")],
        extract=[claims(("The pet fee is $125 each way.", "pets", "amount"))],
        judge=[judge(verdict(1, "SUPPORTED", "PET-001", "The pet fee is $125 each way"))])
    gate = Gate(llm, embeddings, _connect(settings, "app"), changed)

    drafted = impactagent.draft_fixes(gate, "PET-001")

    assert [d["answer_id"] for d in drafted] == ["PA-PET-001"]
    d = drafted[0]
    assert (d["stale_from"], d["based_on_version"], d["check_decision"]) == (DECEMBER, "v2", "PASS")
    assert d["check_ledger_id"] and "$125" in d["text"] and "PET-001 v2" in d["text"]

    app, editor = db.connect(settings, "app"), db.connect(settings, "editor")
    try:
        with pytest.raises(db.DatabaseError) as err:  # the runtime user cannot publish
            policy.decide_suggestion(app, d["suggestion_id"], True, changed)
        assert err.value.sqlstate == "42501"
        published = policy.decide_suggestion(editor, d["suggestion_id"], True, changed)
        assert published == "PA-PET-001-v2"

        old = policy.published_answer(app, "PA-PET-001", changed)
        new = policy.published_answer(app, "PA-PET-001-v2", changed)
        assert (old["applies_to"], old["cited_version"], old["status"]) == (DECEMBER, "v1", "LIVE")  # history kept
        assert (new["applies_from"], new["cited_version"], new["status"]) == (DECEMBER, "v2", "LIVE")
        statuses = {(r["kind"], r["ref_id"]): r["status"] for r in policy.change_impact(app, "PET-001", changed)}
        assert statuses[("PUBLISHED", "PA-PET-001")] == statuses[("PUBLISHED", "PA-PET-001-v2")] == "STILL_VALID"

        with pytest.raises(db.DatabaseError) as err:  # decided once only
            policy.decide_suggestion(editor, d["suggestion_id"], False, changed)
        assert err.value.sqlstate == "75023"
    finally:
        app.close()
        editor.close()


def test_a_draft_the_check_did_not_release_cannot_be_approved(settings, changed):
    app, editor = db.connect(settings, "app"), db.connect(settings, "editor")
    try:
        sid = policy.add_suggestion(app, "PA-PET-001", "PET-001", DECEMBER, "v2", "Pets fly free.", "ESCALATED", None,
                                    [], changed)
        with pytest.raises(db.DatabaseError) as err:
            policy.decide_suggestion(editor, sid, True, changed)
        assert err.value.sqlstate == "75024"
        assert policy.decide_suggestion(editor, sid, False, changed) == ""  # rejecting is always possible
        assert policy.suggestions(app, "PET-001", changed)[0]["status"] == "REJECTED"
    finally:
        app.close()
        editor.close()


@pytest.mark.parametrize("answer_id, version, state", [
    ("PA-BAG-001", "v2", "75020"),  # that answer does not cite PET-001
    ("PA-PET-001", "v1", "75021"),  # v1 is not in force from 1 December any more
])
def test_suggestions_must_match_the_answer_and_the_version_in_force(settings, changed, answer_id, version, state):
    app = db.connect(settings, "app")
    try:
        with pytest.raises(db.DatabaseError) as err:
            policy.add_suggestion(app, answer_id, "PET-001", DECEMBER, version, "x", "PASS", None, [], changed)
        assert err.value.sqlstate == state
    finally:
        app.close()


def test_the_runtime_user_cannot_write_the_suggestion_table_directly(settings, changed):
    app = db.connect(settings, "app")
    try:
        db.use_schema(app, changed)
        with pytest.raises(db.DatabaseError) as err:
            db.execute(app, "UPDATE ANSWER_SUGGESTION SET STATUS = 'APPROVED'")
        assert err.value.sqlstate == "42501"
    finally:
        app.rollback()
        app.close()
