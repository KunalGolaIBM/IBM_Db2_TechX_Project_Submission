"""Policy intake in Db2: drafts are stored and decided only through the editor's procedures, Db2 hashes the file
itself, a preview leaves nothing behind, and approval puts exactly the reviewed items into force."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pdfs import REVISION, make_pdf
from test_intake import CREDITS, clause, num

from asof import db, intake, schema, seed
from asof.retriever import clauses_as_of
from asof.schemas import IntakeResult

pytestmark = pytest.mark.db2

CREDIT_TEXT = ("Travel credits are valid for 24 months from the date they are issued. The booking must be made before the "
               "credit expires, but the flight itself may take place after the expiry date.")
DELAY_TEXT = "Delay compensation must be claimed within 1 year of the flight date through the online claims form."
SPORTS = "One set of golf clubs, skis or a snowboard may be checked for a fee of $75 each way."


@pytest.fixture
def scratch(admin_conn, embeddings, settings):
    name = f"ASOF_I{uuid.uuid4().hex[:6].upper()}"
    schema.install(admin_conn, name)
    seed.seed_policy(admin_conn, embeddings, name)
    seed.seed_chain_head(admin_conn, name)
    seed.seed_published_answers(admin_conn, name)
    seed.seed_faq(admin_conn, embeddings, name)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    yield name
    schema.drop(admin_conn, name)


def _draft(settings, name, user="maria", extra=()):
    """The revision PDF with four checked proposals: two changes, one new clause, one unchanged; plus `extra`."""
    src = intake.read_pdf(make_pdf([REVISION]), "revision-2027-1.pdf")
    with db.connection(settings, "app") as reader:
        existing = intake.existing_clauses(reader, "AURELIA-CSP", name)
    proposals, _ = intake.check_items(IntakeResult(clauses=[
        clause(),
        clause(text=SPORTS, cid=None, rule=[num("sports_equipment_fee_usd", 75)], title="Sports equipment"),
        clause(text=CREDIT_TEXT, cid="CRD-001", area="travel_credit", start="2027-03-01", quote=CREDITS,
               rule=[num("credit_validity_months", 24)], title="Travel credit validity"),
        clause(text=DELAY_TEXT, cid="DLY-005", area="delay", rule=[num("claim_window_days", 365)], title="Claims"),
        *extra]), src, existing)
    with db.connection(settings, "editor") as editor:
        draft_id = intake.store_draft(editor, src, "AURELIA-CSP", "scripted:test", proposals, user, name)
    return src, proposals, draft_id


def _count(conn, name, sql, params=()):
    db.use_schema(conn, name)
    return int(db.query(conn, sql, params)[0][0])


def test_a_draft_is_stored_with_db2s_own_hash_of_the_file_and_nothing_is_in_force(settings, scratch):
    src, proposals, draft_id = _draft(settings, scratch)
    assert [p.kind for p in proposals] == ["CHANGE", "NEW", "CHANGE", "UNCHANGED"]
    with db.connection(settings, "app") as reader:
        draft = intake.get_draft(reader, draft_id, scratch)
        assert draft["status"] == "PENDING" and draft["sha256"] == src.sha256 and draft["uploaded_by"] == "maria"
        assert intake.source_pdf(reader, draft_id, scratch)[1] == src.data
        assert _count(reader, scratch, "SELECT COUNT(*) FROM POLICY_CLAUSE WHERE CLAUSE_ID = 'BAG-006'") == 0


def test_db2_refuses_a_file_whose_hash_differs_from_the_applications(settings, scratch):
    with db.connection(settings, "editor") as editor:
        db.use_schema(editor, scratch)
        cur = editor.cursor()
        with pytest.raises(Exception, match="75040"):
            cur.callproc("ADD_POLICY_DRAFT", ("AURELIA-CSP", "x.pdf", "0" * 64, b"%PDF-1.4 x", 1, "x", "m", "", 0))
        editor.rollback()


def test_a_preview_applies_and_measures_the_draft_then_leaves_nothing_behind(settings, embeddings, scratch):
    _, _, draft_id = _draft(settings, scratch)
    with db.connection(settings, "editor") as editor:
        before = _count(editor, scratch, "SELECT COUNT(*) FROM POLICY_CLAUSE")
        out = intake.decide(editor, draft_id, True, [1, 2, 3], embeddings, user="omar", preview=True, schema=scratch)
        assert [(a["clause_id"], a["version"]) for a in out["applied"]] == [("BAG-001", "v3"), ("BAG-006", "v1"),
                                                                            ("CRD-001", "v2")]
        assert {"BAG-001", "CRD-001"} <= set(out["impact"])
        assert any(r["ref_id"] == "PA-BAG-001" and r["status"] == "NEEDS_REVIEW" for r in out["impact"]["BAG-001"])
        assert _count(editor, scratch, "SELECT COUNT(*) FROM POLICY_CLAUSE") == before
    with db.connection(settings, "app") as reader:
        assert intake.get_draft(reader, draft_id, scratch)["status"] == "PENDING"
        assert _count(reader, scratch, "SELECT COUNT(*) FROM PUBLISHED_ANSWER WHERE STATUS = 'NEEDS_REVIEW'") == 0


def test_the_uploader_cannot_approve_their_own_document(settings, embeddings, scratch):
    _, _, draft_id = _draft(settings, scratch, user="maria")
    with db.connection(settings, "editor") as editor:
        for approver in ("maria", None):
            with pytest.raises(db.DatabaseError) as err:
                intake.decide(editor, draft_id, True, [1], embeddings, user=approver, schema=scratch)
            assert err.value.sqlstate == "75044"


def test_db2_refuses_to_accept_an_unchanged_or_blocked_item_or_an_item_that_does_not_exist(settings, embeddings, scratch):
    blocked = clause(text="Your first bag is free.", rule=[num("first_bag_fee_usd", 0)])  # not in the document
    _, proposals, draft_id = _draft(settings, scratch, extra=[blocked])
    assert proposals[4].blocked
    with db.connection(settings, "editor") as editor:
        for accept in ([4], [5], [1, 9]):  # UNCHANGED, blocked, unknown
            with pytest.raises(db.DatabaseError) as err:
                intake.decide(editor, draft_id, True, accept, embeddings, user="omar", schema=scratch)
            assert err.value.sqlstate == "75045"
        with pytest.raises(ValueError, match="at least one"):
            intake.decide(editor, draft_id, True, [], embeddings, user="omar", schema=scratch)


def test_approval_puts_exactly_the_accepted_items_into_force_with_their_provenance(settings, embeddings, scratch):
    src, _, draft_id = _draft(settings, scratch)
    with db.connection(settings, "editor") as editor:
        out = intake.decide(editor, draft_id, True, [1, 2], embeddings, user="omar", schema=scratch)
    assert [(a["clause_id"], a["version"]) for a in out["applied"]] == [("BAG-001", "v3"), ("BAG-006", "v1")]
    with db.connection(settings, "app") as reader:
        draft = intake.get_draft(reader, draft_id, scratch)
        assert draft["status"] == "APPLIED" and draft["decided_by_user"] == "omar"
        assert [(i["item_no"], i["status"], i["applied_version"]) for i in draft["items_detail"]] == [
            (1, "APPLIED", "v3"), (2, "APPLIED", "v1"), (3, "REJECTED", None), (4, "REJECTED", None)]
        db.use_schema(reader, scratch)
        note, by = db.query(reader, "SELECT CHANGE_NOTE, CHANGED_BY FROM POLICY_CLAUSE WHERE CLAUSE_ID = 'BAG-001' "
                                    "AND VERSION_LABEL = 'v3'")[0]
        assert note == f"Policy intake: draft {draft_id} item 1, revision-2027-1.pdf (sha256 {src.sha256[:16]})"
        assert by.strip() == settings.asof_editor_user.upper()
        assert _count(reader, scratch, "SELECT COUNT(*) FROM POLICY_CLAUSE WHERE CLAUSE_ID = 'CRD-001'") == 1
        assert _count(reader, scratch, "SELECT COUNT(*) FROM PUBLISHED_ANSWER WHERE ANSWER_ID = 'PA-BAG-001' "
                                       "AND STATUS = 'NEEDS_REVIEW'") == 1
    vector = embeddings.embed_query("How much is the first checked bag?")
    with db.connection(settings, "app") as reader:  # the as-of retrieval the check uses, on both sides of the date
        on = {c.clause_id: c for c in clauses_as_of(reader, vector, date(2027, 2, 1), "AURELIA-CSP", 5, None, scratch)}
        before = {c.clause_id: c for c in clauses_as_of(reader, vector, date(2027, 1, 31), "AURELIA-CSP", 5, None, scratch)}
    assert on["BAG-001"].version_label == "v3" and "$45" in on["BAG-001"].clause_text
    assert before["BAG-001"].version_label == "v2"


def test_a_decided_draft_cannot_be_decided_or_applied_again(settings, embeddings, scratch):
    _, _, draft_id = _draft(settings, scratch)
    with db.connection(settings, "editor") as editor:
        intake.decide(editor, draft_id, True, [1], embeddings, user="omar", schema=scratch)
        with pytest.raises(db.DatabaseError) as err:
            intake.decide(editor, draft_id, False, [], embeddings, user="omar", schema=scratch)
        assert err.value.sqlstate == "75047"
        db.use_schema(editor, scratch)
        cur = editor.cursor()
        with pytest.raises(Exception, match="75048"):
            cur.callproc("APPLY_DRAFT_ITEM", (draft_id, 1, None, " " * 20, 0, 0))
        editor.rollback()


def test_rejecting_a_draft_changes_nothing(settings, embeddings, scratch):
    _, _, draft_id = _draft(settings, scratch)
    with db.connection(settings, "editor") as editor:
        before = _count(editor, scratch, "SELECT COUNT(*) FROM POLICY_CLAUSE")
        out = intake.decide(editor, draft_id, False, [], embeddings, user="omar", schema=scratch)
        assert out["applied"] == [] and _count(editor, scratch, "SELECT COUNT(*) FROM POLICY_CLAUSE") == before
    with db.connection(settings, "app") as reader:
        draft = intake.get_draft(reader, draft_id, scratch)
        assert draft["status"] == "REJECTED" and {i["status"] for i in draft["items_detail"]} == {"REJECTED"}


def test_only_the_procedures_write_drafts_and_only_the_editor_may_call_them(settings, scratch):
    _, _, draft_id = _draft(settings, scratch)
    with db.connection(settings, "app") as app:
        db.use_schema(app, scratch)
        cur = app.cursor()
        for proc, args in (("DECIDE_POLICY_DRAFT", (draft_id, 1, "1", "omar", 0)),
                           ("APPLY_DRAFT_ITEM", (draft_id, 1, None, " " * 20, 0, 0))):
            with pytest.raises(Exception, match="42501|SQL0551N"):
                cur.callproc(proc, args)
            app.rollback()
    with db.connection(settings, "editor") as editor:
        for sql in ("UPDATE POLICY_DRAFT SET STATUS = 'APPLIED'", "DELETE FROM POLICY_DRAFT_ITEM",
                    "UPDATE POLICY_DRAFT_ITEM SET BLOCKED = 0"):
            db.use_schema(editor, scratch)
            with pytest.raises(db.DatabaseError) as err:
                db.execute(editor, sql)
            assert err.value.sqlstate == "42501"
            editor.rollback()
        db.use_schema(editor, scratch)
        cur = editor.cursor()
        with pytest.raises(Exception, match="75048"):  # a pending draft's item cannot be pushed into force
            cur.callproc("APPLY_DRAFT_ITEM", (draft_id, 1, None, " " * 20, 0, 0))
        editor.rollback()
