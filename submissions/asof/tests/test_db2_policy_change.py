"""Db2 integration: policy changes through APPLY_POLICY_CHANGE, change impact, timeline, history."""

from __future__ import annotations

import time
import uuid
from datetime import date

import pytest

from asof import db, ledger, policy, schema, seed

pytestmark = pytest.mark.db2

PET_CHANGE = policy.PolicyChange(
    clause_id="PET-001", effective_from=date(2026, 12, 1), version_label="v2",
    clause_text="Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more "
                "than 8 kg. The pet fee is $125 each way.",
    rule={"max_pet_weight_kg": 8, "pet_fee_usd": 125}, change_note="Pet fee rises to $125 from 1 December 2026")


@pytest.fixture
def world(admin_conn, embeddings, settings):
    name = f"ASOF_P{uuid.uuid4().hex[:6].upper()}"
    schema.install(admin_conn, name)
    seed.seed_policy(admin_conn, embeddings, name)
    seed.seed_chain_head(admin_conn, name)
    seed.seed_published_answers(admin_conn, name)
    seed.seed_faq(admin_conn, embeddings, name)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    yield name
    schema.drop(admin_conn, name)


def answer_citing_pet_fee(conn, name, as_of: date) -> int:
    claim = {"pass": 1, "claim_no": 1, "text": "The pet fee is $100 each way.", "area": "pets", "verdict": "SUPPORTED",
             "llm_verdict": "SUPPORTED", "rule_check": "MATCH", "clause_id": "PET-001", "clause_version": "v1",
             "clause_bus_start": "2026-01-01", "clause_sys_start": None, "distance": 0.2,
             "quoted_span": "The pet fee is $100 each way"}
    e = ledger.LedgerEntry(str(uuid.uuid4()), "api", "AURELIA-CSP", as_of, "Pet fee?", "The pet fee is $100 each way.",
                           "The pet fee is $100 each way.", "PASS", "ALL_SUPPORTED", "test", "test", 5, {"claims": [claim]})
    return ledger.append(conn, e, name).ledger_id


def test_change_splits_the_version_and_reports_impact(settings, embeddings, world):
    app, editor = db.connect(settings, "app"), db.connect(settings, "editor")
    try:
        november = answer_citing_pet_fee(app, world, date(2026, 11, 20))
        december = answer_citing_pet_fee(app, world, date(2026, 12, 15))
        time.sleep(1.1)

        result = policy.apply_change(editor, PET_CHANGE, embeddings, world)
        assert result == {"rows_changed": 1, "published_flagged": 1, "embedded_in": "app"}  # no Db2 model here

        impact = {(r["kind"], r["ref_id"]): r for r in policy.change_impact(editor, "PET-001", world)}
        assert impact[("ANSWER", str(november))]["status"] == "HISTORICALLY_VALID"
        stale = impact[("ANSWER", str(december))]
        assert (stale["status"], stale["cited_version"], stale["current_version"]) == ("STALE", "v1", "v2")
        pub = impact[("PUBLISHED", "PA-PET-001")]
        assert (pub["status"], pub["state"], pub["stale_from"]) == ("NEEDS_REVIEW", "NEEDS_REVIEW", date(2026, 12, 1))

        versions = next(c for c in policy.timeline(app, world) if c["clause_id"] == "PET-001")["versions"]
        assert [(v["version"], v["from"], v["params"]["pet_fee_usd"]) for v in versions] == [
            ("v1", date(2026, 1, 1), 100.0), ("v2", date(2026, 12, 1), 125.0)]
        assert versions[1]["changed_by"] == settings.asof_editor_user.upper()

        hist = policy.history(app, "PET-001", world)
        assert any(not h["current"] and h["to"] == date(9999, 12, 31) for h in hist)  # the replaced open-ended row
        assert ledger.replay(app, december, world)["clauses"][0]["status"] == "CHANGED_SINCE_DECISION"
        assert ledger.verify_chain(app, world).status == "OK"
    finally:
        app.close()
        editor.close()


def test_only_the_editor_can_change_policy(settings, embeddings, world):
    app, editor = db.connect(settings, "app"), db.connect(settings, "editor")
    try:
        with pytest.raises(db.DatabaseError) as err:
            policy.apply_change(app, PET_CHANGE, embeddings, world)
        assert err.value.sqlstate == "42501"
        db.use_schema(editor, world)  # outside the raises block: only the UPDATE may fail
        with pytest.raises(db.DatabaseError) as err:
            db.execute(editor, "UPDATE POLICY_CLAUSE SET CLAUSE_TEXT = 'x'")
        assert err.value.sqlstate == "42501"
        with pytest.raises(db.DatabaseError) as err:
            db.execute(editor, "UPDATE PUBLISHED_ANSWER SET STATUS = 'LIVE'")
        assert err.value.sqlstate == "42501"
    finally:
        app.close()
        editor.close()


@pytest.mark.parametrize("change, state", [
    ({"version_label": "v1"}, "75012"),                                             # label already used
    ({"clause_id": "ZZZ-999"}, None),                                               # unknown clause (Python check)
    ({"effective_from": date(2026, 12, 1), "effective_to": date(2026, 11, 1)}, None),  # empty period
])
def test_bad_changes_are_rejected(settings, embeddings, world, change, state):
    editor = db.connect(settings, "editor")
    try:
        bad = PET_CHANGE.model_copy(update=change)
        with pytest.raises((db.DatabaseError, ValueError)) as err:
            policy.apply_change(editor, bad, embeddings, world)
        if state:
            assert err.value.sqlstate == state
    finally:
        editor.close()


@pytest.mark.parametrize("field, value", [
    ("clause_id", "PET-001'; --"), ("version_label", "final"), ("rule", {"x": {"nested": 1}}),
    ("rule", {"bad key!": 1}), ("clause_text", "short"), ("effective_from", date(2019, 1, 1)),
])
def test_change_input_is_validated(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        policy.PolicyChange.model_validate(PET_CHANGE.model_dump() | {field: value})


def test_if_the_db2_model_is_missing_the_change_still_lands_with_a_local_vector(settings, embeddings, world):
    editor = db.connect(settings, "editor")
    try:
        result = policy.apply_change(editor, PET_CHANGE, embeddings, world, in_db=True)
    finally:
        editor.close()
    assert result["embedded_in"] == "app (Db2 model unavailable)" and result["rows_changed"] == 1


def test_without_a_db2_model_or_local_embeddings_the_procedure_refuses(settings, world):
    editor = db.connect(settings, "editor")
    try:
        with pytest.raises(db.DatabaseError) as err:
            policy.apply_change(editor, PET_CHANGE, None, world, in_db=True)
        assert err.value.sqlstate == "75014"
    finally:
        editor.close()


def test_a_preview_reports_the_real_impact_and_leaves_nothing_behind(settings, embeddings, world, admin_conn):
    """POST /api/policy/preview: APPLY_POLICY_CHANGE and CHANGE_IMPACT in one transaction, rolled back."""
    def state():
        db.use_schema(admin_conn, world)
        clauses = db.query(admin_conn, "SELECT COUNT(*) FROM POLICY_CLAUSE WHERE CLAUSE_ID = ?", ("PET-001",))[0][0]
        history = db.query(admin_conn, "SELECT COUNT(*) FROM POLICY_CLAUSE_HIST WHERE CLAUSE_ID = ?", ("PET-001",))[0][0]
        status = db.query(admin_conn, "SELECT STATUS FROM PUBLISHED_ANSWER WHERE ANSWER_ID = ?", ("PA-PET-001",))[0][0]
        admin_conn.commit()
        return clauses, history, status.strip()

    def rows(impact):
        return sorted((r["kind"], str(r["ref_id"]), r["status"], r["current_version"]) for r in impact)

    before = state()
    editor = db.connect(settings, "editor")
    try:
        preview = policy.preview_change(editor, PET_CHANGE, embeddings, world)
        after_preview = state()
        applied = policy.apply_change(editor, PET_CHANGE, embeddings, world)
        real = policy.change_impact(editor, PET_CHANGE.clause_id, world)
    finally:
        editor.close()
    assert after_preview == before == (1, 0, "LIVE")  # no split, no history row, no flag
    assert preview["preview"] is True and preview["rows_changed"] == applied["rows_changed"]
    assert preview["published_flagged"] == applied["published_flagged"] == 1
    assert rows(preview["impact"]) == rows(real) and ("PUBLISHED", "PA-PET-001", "NEEDS_REVIEW", "v1, v2") in rows(real)
    assert state() == (2, 1, "NEEDS_REVIEW")  # the real change did land
