"""Indian Railways refunds, the third public demo domain: its data, PDFs, labelling, routing, and its recording.

The Db2 tests load the domain from the shipped recording (as setup and the public demo do) and replay both playground
scenarios to their recorded decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest

from asof import domains, indianrail, intake, replay, router, rules
from asof.domains import AIRLINE, BANK, INDIAN_RAIL

LABEL = "Summary of public rules, not an official IRCTC or Indian Railways statement."
# The shipped recording as it was before this domain (e4dd103): its 121 outputs, its 17 recorded checks and every other
# scenario summary, each as a SHA-256 of its JSON. Adding the domain may only add.
OLD_ENTRIES = (121, "ac8b112ac4af60e4e55b795534474bc2d4f4d7631def6a70d1f24171e66ae094")
OLD_CHECKS = (17, "ff827c6ac54f08f2009a02f9756ff6f46959d06492e2d7e66087bda4928ebf86")
OLD_OTHERS = "912d160f55760c917c633913338cb118db3ab28298c2d25d5a6030b11be9f040"
SCENARIO_LABELS = ("Indian Railways (summary, not official): travel 2 May 2026",
                   "Indian Railways (summary, not official): travel 20 Mar 2026")


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_it_is_a_public_domain_with_neutral_prompts_and_its_own_intake_rules():
    assert domains.domain_for("INDIAN-RAIL-REFUNDS") is INDIAN_RAIL and "INDIAN-RAIL-REFUNDS" in domains.DOC_IDS
    assert INDIAN_RAIL.judge_system == domains.RAIL.judge_system and "airline" not in INDIAN_RAIL.judge_system.lower()
    assert "effective_to: null" in INDIAN_RAIL.intake_system and AIRLINE.intake_system != INDIAN_RAIL.intake_system
    assert indianrail.doc_id() == INDIAN_RAIL.doc_id


def test_the_label_is_everywhere_it_shows():
    data = indianrail.data()
    assert data["label"] == LABEL and LABEL in data["doc"]["source_note"] and "not an official" in data["doc"]["title"]
    for v in data["versions"]:
        assert LABEL in indianrail.document(v)
    scenarios = [s for s in replay.load_scenarios()["playground"] if s["doc"] == INDIAN_RAIL.doc_id]
    assert [s["label"] for s in scenarios] == list(SCENARIO_LABELS) and all("not official" in s["label"] for s in scenarios)
    assert "Summary of public rules, not an official IRCTC or Indian Railways statement." in (
        indianrail.SAMPLES.parent.parent / "ui" / "app.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("n", [0, 1])
def test_each_pdf_is_its_summary_word_for_word(n):
    v = indianrail.data()["versions"][n]
    data = indianrail.pdf_path(v).read_bytes()
    assert data == indianrail.build_pdf(v)
    assert intake.read_pdf(data, "x.pdf").text.split() == intake.normalize(indianrail.document(v)).split()


def test_the_versions_and_their_bands_are_well_formed():
    versions = indianrail.data()["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    assert [indianrail.start(v) for v in versions] == [date(2020, 1, 1), date(2026, 4, 15)]
    for v in versions:
        rules.validate_time_bands(v["time_bands"])
        assert v["sources"] and all(u.startswith("https://") for u in v["sources"])
        assert len(indianrail._change_note(v)) <= 400 and v["sources"][0] in indianrail._change_note(v)


def test_the_editors_table_rule_keeps_flags_and_bands_and_drops_flat_numbers():
    bands = indianrail.data()["versions"][1]["time_bands"]
    out = indianrail.table_rule({"min_hours_before_flat_rate_cancellation": 72, "refund_allowed": True, "x_pct": 50}, bands)
    assert out == {"refund_allowed": True, "time_bands": bands}


Q = "I cancel my confirmed Sleeper ticket 6 hours before departure; how much do I get back?"


def test_the_bands_decide_the_scenarios():
    v1, v2 = (v["time_bands"] for v in indianrail.data()["versions"])
    assert rules.band_check("You get 50% back.", Q, {"time_bands": v2}).status == "MISMATCH"   # under 8 h: nothing
    assert rules.band_check("You get 50% back.", Q, {"time_bands": v1}).status == "MATCH"      # 4 to 12 h: 50%
    assert rules.band_check("No refund is given.", Q, {"time_bands": v2}).status == "MATCH"


def test_the_pair_vote_is_unchanged_and_the_rail_document_routes_on_a_clear_lead():
    """Without the rail document among the two nearest, the vote is the original two-document one."""
    class R(router.Router):
        def __init__(self, rows):
            super().__init__(None, None)
            self.rows = rows

        def nearest(self, question, draft, as_of):
            return self.rows

    def n(doc, d):
        return router.Nearest(doc, "X-001", "t", "v1", "text", d)

    pair = R([n(AIRLINE.doc_id, 0.2), n(BANK.doc_id, 0.7), n(INDIAN_RAIL.doc_id, 0.8)]).route("q", "d", date(2026, 5, 1))
    assert (pair.doc_id, set(pair.distances)) == (AIRLINE.doc_id, {AIRLINE.doc_id, BANK.doc_id})
    assert {x.doc_id for x in pair.nearest} == {AIRLINE.doc_id, BANK.doc_id}
    rail = R([n(AIRLINE.doc_id, 0.7), n(BANK.doc_id, 0.9), n(INDIAN_RAIL.doc_id, 0.2)]).route("q", "d", date(2026, 5, 1))
    assert (rail.doc_id, rail.method, set(rail.distances)) == (INDIAN_RAIL.doc_id, "db2", {INDIAN_RAIL.doc_id,
                                                                                           AIRLINE.doc_id})
    msgs = router.route_messages("q", "d", [], (INDIAN_RAIL.doc_id, AIRLINE.doc_id))
    assert "INDIAN-RAIL-REFUNDS" in msgs[0][1] and "FERNHOLLOW-FEES" not in msgs[0][1]
    assert router.route_messages("q", "d", []) == router.route_messages("q", "d", [], router.PAIR)
    assert "INDIAN-RAIL" not in router.route_messages("q", "d", [])[0][1]


def test_the_recording_only_adds_to_what_was_shipped():
    data = json.loads(replay.RECORDING_PATH.read_text(encoding="utf-8"))
    new = set(data["scenarios"].get("indian_rail", {}).get("keys", []))
    old = {k: v for k, v in data["entries"].items() if k not in new}
    assert (len(old), _sha(old)) == OLD_ENTRIES
    checks = [c for c in data["scenarios"]["checks"] if c["doc_id"] != INDIAN_RAIL.doc_id]
    assert (len(checks), _sha(checks)) == OLD_CHECKS
    others = {k: v for k, v in data["scenarios"].items() if k not in ("checks", "indian_rail")}
    assert _sha(others) == OLD_OTHERS


def test_both_scenarios_are_recorded_with_the_expected_decisions():
    data = json.loads(replay.RECORDING_PATH.read_text(encoding="utf-8"))
    got = {c["label"]: (c["decision"], c["as_of"]) for c in data["scenarios"]["checks"]
           if c["doc_id"] == INDIAN_RAIL.doc_id}
    assert got == {SCENARIO_LABELS[0]: ("CORRECTED", "2026-05-02"), SCENARIO_LABELS[1]: ("PASS", "2026-03-20")}
    assert data["scenarios"]["indian_rail"]["loaded"] is True


@pytest.mark.db2
def test_the_domain_loads_from_the_recording_and_both_scenarios_replay(settings, embeddings, admin_conn):
    import uuid

    from asof import db, policy, schema, seed
    from asof.gate import Gate, GateRequest

    name = f"ASOF_I{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                            analyst_user=settings.asof_analyst_user)
        assert indianrail.ensure(settings, name, embeddings, log=lambda _m: None)["loaded"] is True
        assert indianrail.ensure(settings, name, embeddings, log=lambda _m: None)["loaded"] is False  # idempotent
        with db.connection(settings, "app") as conn:
            (clause,) = policy.timeline(conn, name, INDIAN_RAIL.doc_id)
        in_force = [v for v in clause["versions"] if v["rule"].get("time_bands")]
        assert [v["from"] for v in in_force] == [date(2020, 1, 1), date(2026, 4, 15)]
        assert all("Sources: https://" in v["change_note"] for v in in_force)
        gate = Gate(replay.ReplayLLM(replay.Recording.load()), embeddings, lambda: db.connect(settings, "app"), name)
        draft = "You get 50% back."
        may = gate.check(GateRequest(Q, draft, date(2026, 5, 2), INDIAN_RAIL.doc_id, "demo"))
        march = gate.check(GateRequest(Q, draft, date(2026, 3, 20), INDIAN_RAIL.doc_id, "demo"))
        assert (may.decision, march.decision) == ("CORRECTED", "PASS")
        assert all(c.clause and c.clause.bus_start == date(2020, 1, 1) for c in march.claims)
    finally:
        schema.drop(admin_conn, name)


def test_a_near_tie_with_the_rail_document_goes_to_the_agent_which_may_pick_either():
    from asof.llm import LLMResult

    class Agent:
        info = "fake"

        def __init__(self, document):
            self.document, self.schemas = document, []

        def structured(self, schema, messages, choices=None):
            self.schemas.append(schema)
            return LLMResult(schema(document=self.document, confident=True, reason="r"), 1, 1, 1, 1)

    class R(router.Router):
        def __init__(self, rows, llm):
            super().__init__(None, None, llm=llm)
            self.rows = rows

        def nearest(self, question, draft, as_of):
            return self.rows

    rows = [router.Nearest(AIRLINE.doc_id, "A", "t", "v1", "x", 0.396), router.Nearest(BANK.doc_id, "B", "t", "v1", "x", 0.6),
            router.Nearest(INDIAN_RAIL.doc_id, "C", "t", "v1", "x", 0.400)]
    agent = Agent(INDIAN_RAIL.doc_id)
    route = R(rows, agent).route("q", "d", date(2026, 5, 2))
    assert (route.doc_id, route.method) == (INDIAN_RAIL.doc_id, "db2+agent") and agent.schemas == [router.RouteResultRail]
    assert R(rows, Agent("NEITHER")).route("q", "d", date(2026, 5, 2)).doc_id is None
    assert R(rows, None).route("q", "d", date(2026, 5, 2)).method == "ask"
