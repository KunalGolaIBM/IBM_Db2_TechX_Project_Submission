"""The shipped recording, replayed through Db2 with no model at all.

Every built-in scenario must reach the decision it reached when it was recorded against the live
model, with retrieval, the rule check, the decision and the ledger running for real. Anything that
was not recorded must be held for a specialist (fail closed) and still land in the ledger.
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from asof import db, impactagent, ledger, policy, replay, schema, seed
from asof.askledger import LedgerAsker
from asof.assistant import DemoAssistant
from asof.gate import HOLDING_REPLY, Gate, GateRequest

pytestmark = pytest.mark.db2

RECORDING = replay.Recording.load() if replay.RECORDING_PATH.is_file() else None


@pytest.fixture(scope="module")
def replayed(admin_conn, embeddings, settings):
    if RECORDING is None:
        pytest.skip("no recording shipped yet (python -m asof.replay record)")
    name = f"ASOF_R{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                            analyst_user=settings.asof_analyst_user)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    time.sleep(1.1)  # the preset change below must get a later system time than the seed rows
    llm = replay.ReplayLLM(RECORDING)
    app = lambda: db.connect(settings, "app")  # noqa: E731
    yield SimpleNamespace(schema=name, llm=llm, gate=Gate(llm, embeddings, app, name),
                          bot=DemoAssistant(llm, embeddings, app, name))
    schema.drop(admin_conn, name)


def test_the_sample_policy_revision_replays_through_the_db2_timeline(replayed, settings):
    """Policy intake in replay mode: the model's proposal comes from the recording, the clauses it is compared
    with come from Db2's timeline view, and the checks run live. First in the module: a later test applies the
    BAG-001 preset ($45 from 1 Jan 2027), after which the sample's $45 section is, rightly, UNCHANGED."""
    from asof import intake

    source = intake.read_pdf(intake.SAMPLE_PDF.read_bytes(), intake.SAMPLE_PDF.name)
    conn = db.connect(settings, "app")
    try:
        proposals, discarded, model = intake.propose(replayed.llm, source, "AURELIA-CSP", conn, replayed.schema)
    finally:
        conn.close()
    assert model.startswith("replay:") and not discarded
    assert [(p.clause_id, p.kind, p.blocked) for p in proposals] == [
        ("BAG-001", "CHANGE", False), ("BAG-006", "NEW", False), ("CRD-001", "CHANGE", False),
        ("DLY-005", "UNCHANGED", False)]

def test_every_built_in_check_replays_to_its_recorded_decision(replayed):
    got = []
    for c in RECORDING.scenarios["checks"]:
        draft = c["draft"] or replayed.bot.answer(c["question"]).text
        r = replayed.gate.check(GateRequest(c["question"], draft, date.fromisoformat(c["as_of"]), c["doc_id"], "demo"))
        got.append((c["label"], draft == c["draft_checked"], r.decision, r.reason_code, r.model_info.startswith("replay:")))
    want = [(c["label"], True, c["decision"], c["reason_code"], True) for c in RECORDING.scenarios["checks"]]
    assert got == want


def test_an_unrecorded_draft_is_held_and_still_recorded(replayed, settings):
    r = replayed.gate.check(GateRequest("Can I bring my bike?", "Yes, bikes fly free on every Aurelia Air flight.",
                                        date(2026, 5, 5), "AURELIA-CSP", "api"))
    assert (r.decision, r.reason_code, r.final_answer) == ("ESCALATED", "ERROR_FAIL_CLOSED", HOLDING_REPLY)
    assert "replay mode" in (r.error or "") and r.ledger_id is not None
    conn = db.connect(settings, "app")
    try:
        assert ledger.verify_chain(conn, replayed.schema).status == "OK"
    finally:
        conn.close()


def test_the_ask_the_ledger_examples_replay_their_sql_which_then_runs_live(replayed, settings):
    asker = LedgerAsker(replayed.llm, settings, replayed.schema)
    got = [(a["question"], asker.ask(a["question"])) for a in RECORDING.scenarios["ask"]]
    assert [(q, r.status, r.sql) for q, r in got] == [(a["question"], a["status"], a["sql"]) for a in RECORDING.scenarios["ask"]]


def test_every_preset_replays_the_change_impact_agent_in_recorded_order(replayed, settings, embeddings):
    presets, recorded = replay.load_scenarios()["presets"], RECORDING.scenarios["impact"]
    assert [p["label"] for p in presets] == [r["preset"] for r in recorded]
    for preset, rec in zip(presets, recorded, strict=True):
        with db.connection(settings, "app") as reader:
            assert replay.next_version(policy.timeline(reader, replayed.schema), preset["clause"]) == rec["version_label"]
        with db.connection(settings, "editor") as ed:
            policy.apply_change(ed, policy.PolicyChange(
                clause_id=preset["clause"], effective_from=preset["from"], version_label=rec["version_label"],
                clause_text=preset["text"], rule=preset["rule"], change_note=preset["note"]), embeddings, replayed.schema)
        drafted = impactagent.draft_fixes(replayed.gate, preset["clause"])
        assert [(d["answer_id"], d.get("check_decision"), d.get("error")) for d in drafted] == \
            [(d["answer_id"], d["check_decision"], None) for d in rec["drafts"]], preset["label"]


def test_analytics_says_how_many_decisions_were_replayed(replayed, settings):
    with db.connection(settings, "app") as conn:
        stats = policy.analytics(conn, replayed.schema)
        db.use_schema(conn, replayed.schema)
        total = db.query(conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0]
    assert stats["replayed_decisions"] == total > 0  # every decision in this schema came from the recording
    assert sum(d["count"] for d in stats["decisions"]) == total


def test_analytics_counts_what_the_rule_check_said_about_every_draft_claim(replayed, settings):
    with db.connection(settings, "app") as conn:
        rc = policy.analytics(conn, replayed.schema)["rule_checks"]
        db.use_schema(conn, replayed.schema)
        claims = db.query(conn, "SELECT COUNT(*) FROM CLAIM_CITATION WHERE PASS_NO = 1")[0][0]
        mismatches = db.query(conn, "SELECT COUNT(*) FROM CLAIM_CITATION WHERE PASS_NO = 1 AND RULE_CHECK = 'MISMATCH'")[0][0]
    assert rc["match"] + rc["mismatch"] + rc["not_applicable"] == claims > 0
    assert rc["mismatch"] == mismatches > 0  # the replayed scenarios include wrong amounts the rules catch
    assert rc["mismatch_judge_agreed"] <= rc["mismatch"]

