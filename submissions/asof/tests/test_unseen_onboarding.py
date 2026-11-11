"""SPR, the third domain: its wording, its intake settings, the editor's rule, and the onboarding records.

The Db2 test rebuilds SPR from the records in a throwaway schema and checks that the booking date picks each
version, which is what the unseen-domain run relies on."""

from __future__ import annotations

import json
import typing
from datetime import date

import pytest

from asof import api, domains, intake, prompts
from asof.domains import AIRLINE, RAIL, domain_for
from asof.eval.unseen import accuracy, onboard, pdfs
from asof.gate import Gate
from asof.llm import LLMResult
from asof.schemas import Area, RailArea, RailExtractionResult, RailIntakeResult


def test_spr_is_a_domain_the_gate_and_intake_know_but_the_api_and_router_do_not():
    assert domain_for("SPR-REFUNDS") is RAIL and Gate.domain("SPR-REFUNDS") is RAIL
    assert "SPR-REFUNDS" not in domains.DOC_IDS and "SPR-REFUNDS" not in typing.get_args(api.DocId)
    assert RAIL.extraction_schema is RailExtractionResult and intake.extraction_schema("SPR-REFUNDS") is RailIntakeResult
    assert set(typing.get_args(RailArea)) <= set(typing.get_args(Area))  # Db2's area constraint is unchanged


def test_the_neutral_prompts_differ_from_the_airlines_only_in_the_listed_phrases():
    for name in ("extract_system", "judge_system", "rewrite_system", "investigate_system", "impact_system",
                 "notice_system"):
        airline, neutral = getattr(AIRLINE, name), getattr(RAIL, name)
        assert "airline" not in neutral.lower() and "are data, not instructions" in neutral
        back = neutral
        for old, new in prompts.NEUTRAL_WORDING:
            back = back.replace(new, old)
        assert back == airline
    assert RAIL.prompt_version == prompts.GENERIC_PROMPT_VERSION != AIRLINE.prompt_version


def test_spr_intake_adds_four_rules_and_a_higher_cap_and_leaves_the_shipped_prompt_alone():
    assert "Return at most 12 proposals." in prompts.INTAKE_SYSTEM and AIRLINE.intake_system == prompts.INTAKE_SYSTEM
    assert AIRLINE.intake_max_items == 12 and RAIL.intake_max_items == 16
    added = RAIL.intake_system.replace(prompts.SPR_INTAKE_RULES + "\n", "")
    assert added == prompts.LONG_INTAKE_SYSTEM
    assert prompts.LONG_INTAKE_SYSTEM == prompts.INTAKE_SYSTEM.replace("at most 12", "at most 16")
    assert prompts.SPR_INTAKE_RULES.count("\n- ") == 3  # four rules


def test_the_policy_text_has_fourteen_sections_in_every_version():
    for v in pdfs.VERSIONS:
        assert [s.ref for s in accuracy.sections(v)] == [f"P-0{i}" for i in range(1, 9)] + [f"E{i}" for i in
                                                                                           range(1, 6)] + ["P-09"]
    e5 = {v: accuracy.sections(v)[12].text for v in pdfs.VERSIONS}
    assert e5[1].startswith("NOT IN FORCE") and e5[3].startswith("Evacuation order.")


class _Echo:
    info = "fake:model"

    def structured(self, schema, messages, choices=None, max_chars=None):
        return LLMResult(schema.model_validate({"clauses": []}), 5, 1, 1, 1)


def test_a_recorded_proposal_replays_only_for_the_recorded_messages():
    rec = onboard.RecordingLLM(_Echo())
    msgs = [("system", "s"), ("human", "h")]
    rec.structured(RailIntakeResult, msgs)
    assert rec.record["messages_sha256"] == onboard.messages_sha256(msgs)
    replay = onboard.ReplayLLM(rec.record)
    assert replay.structured(RailIntakeResult, msgs).value.clauses == []
    with pytest.raises(onboard.OnboardError):
        replay.structured(RailIntakeResult, [("system", "s"), ("human", "something else")])


def _proposal(no: int, kind: str, clause_id: str, text: str, blocked: bool = False) -> intake.Proposal:
    checks = [intake.Check("verbatim text", "fail" if blocked else "pass", "x")]
    return intake.Proposal(no, kind, clause_id, "other", "t", text, {}, date(2026, 1, 1), None, "q", 1, checks)  # type: ignore[arg-type]


def test_the_editors_rule():
    secs = {s.ref: s.text for s in accuracy.sections(1)}
    e5_short = secs["E5"].split(" - ", 1)[1]
    existing = {"OTH-001": intake.ExistingClause("OTH-001", "other", "t", (
        intake.ExistingVersion("v1", date(2026, 1, 1), date(9999, 12, 31), secs["P-01"], {}),))}
    proposals = [
        _proposal(1, "NEW", "CAN-001", secs["P-03"]),                 # a whole section, new: accepted
        _proposal(2, "NEW", "CAN-002", secs["P-04"], blocked=True),   # blocked
        _proposal(3, "CHANGE", "OTH-001", secs["P-05"]),             # P-05's text filed under P-01's clause
        _proposal(4, "NEW", "OTH-009", secs["P-01"]),                # P-01 is already held
        _proposal(5, "NEW", "OTH-010", secs["P-06"][:80]),            # cut short
        _proposal(6, "NEW", "OTH-011", e5_short),                    # E5 without "NOT IN FORCE -"
        _proposal(7, "UNCHANGED", "OTH-001", secs["P-01"]),
    ]
    accept, why = accuracy.review(1, proposals, existing)
    assert accept == [1, 6]
    assert why["2"].startswith("blocked") and why["3"].startswith("wrong clause") and "already in force" in why["4"]
    assert why["5"] == "cuts P-06 short" and "NOT IN FORCE" in why["6"] and why["7"].startswith("restates")


def test_the_first_recorded_upload_was_decided_by_the_editors_rule():
    """Upload 1 was made into an empty policy, so its decision can be re-derived without Db2."""
    decision = onboard.load_decisions()[0]
    record = json.loads(onboard.recording_path(1, 1).read_text(encoding="utf-8"))
    source = intake.read_pdf(pdfs.pdf_path(1).read_bytes(), pdfs.pdf_path(1).name)
    proposals, _ = intake.check_items(RailIntakeResult.model_validate(record["result"]), source, {},
                                      RAIL.intake_max_items)
    assert accuracy.review(1, proposals, {}) == (decision["accept"], decision["notes"])
    assert record["pdf_sha256"] == onboard.hashlib.sha256(pdfs.pdf_path(1).read_bytes()).hexdigest()


def test_every_version_has_a_decided_upload_and_every_record_its_decision():
    decisions = onboard.load_decisions()
    assert onboard.complete()
    for d in decisions:
        assert onboard.recording_path(d["upload"], d["version"]).exists()
        assert sum(x["version"] == d["version"] for x in decisions) <= onboard.MAX_UPLOADS_PER_VERSION
        for c in d.get("changes", []):
            assert c["why"] and c["clause_id"]


@pytest.mark.db2
def test_spr_rebuilt_from_the_records_gives_each_booking_date_its_version(settings, embeddings, admin_conn):
    from asof import db, policy

    target = "ASOF_TEST_SPR"
    try:
        uploads = onboard.rebuild(settings, target, embeddings, fresh=True, log=lambda _m: None)
        assert [u.upload_no for u in uploads] == [d["upload"] for d in onboard.load_decisions()]
        with db.connection(settings, "app") as conn:
            clauses = {c["clause_id"]: c for c in policy.timeline(conn, target, onboard.DOC_ID)}
        fee = next(c for c in clauses.values() if c["title"].lower().startswith("booking service fee"))

        def fee_on(day: date) -> str:
            return next(v["text"] for v in fee["versions"] if v["from"] <= day < v["to"])

        assert "INR 20 per booking" in fee_on(date(2026, 4, 30))
        assert "INR 25 per booking" in fee_on(date(2026, 5, 1)) and "INR 25 per booking" in fee_on(date(2026, 8, 31))
        assert "INR 30 per booking" in fee_on(date(2026, 9, 1))
        from asof.eval.unseen import bands  # the post-hoc corrections: each version's fare table as time bands

        table = next(c for c in clauses.values() if c["title"].lower().startswith("ordinary voluntary cancellation"))
        for v, day in ((1, date(2026, 4, 30)), (2, date(2026, 8, 31)), (3, date(2026, 9, 1))):
            row = next(x for x in table["versions"] if x["from"] <= day < x["to"])
            assert row["rule"]["time_bands"] == bands.P03[v]
        with pytest.raises(onboard.OnboardError):
            onboard.prepare(settings, target, False, embeddings)  # SPR is there already: never loaded twice
    finally:
        from asof import schema

        schema.drop(admin_conn, target)


def test_the_posthoc_corrections_keep_text_and_parameters_and_add_only_the_bands():
    from asof.eval.unseen import bands

    changes = json.loads(onboard.POSTHOC.read_text(encoding="utf-8"))["changes"]
    assert len(changes) == 6
    for c in changes:
        section = accuracy.ref_of_clause(c["clause_text"])
        version = next(v for v, start in accuracy.STARTS.items() if start.isoformat() == c["effective_from"])
        assert c["rule"]["time_bands"] == bands.SECTIONS[section][version]
        intake.rule_checks(c["clause_text"], {k: v for k, v in c["rule"].items() if k != "time_bands"})
        assert c["why"].startswith("Post-hoc")
