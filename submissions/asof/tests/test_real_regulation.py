"""The real-regulation demonstration (14 CFR 259.5 and part 260): pinned eCFR files, PDFs that keep every word, the
onboarding records, and the question set's shape. The Db2 test rebuilds the domain from the records."""

from __future__ import annotations

import hashlib
import json
import typing
from collections import defaultdict
from datetime import date

import pytest

from asof import api, domains, intake, prompts
from asof.domains import DOT, domain_for
from asof.eval.real import onboard, text
from asof.eval.real.questions import QUESTIONS
from asof.schemas import RailIntakeResult

ECFR_SHA256 = {
    "2023-01-03_259.5.xml": "37506537f05e3f2aaaba06bfaad5f8ee2fef0daa930949ecab7032a66dd1cad2",
    "2024-06-24_259.5.xml": "8e958df95df4d28cd3714de00f8b7b53e9fa40e30a243ae25d494a8dae3c4dd9",
    "2024-07-01_259.5.xml": "99e86d7d4d459e7ac72fbaf51b6c21dfbdaf19d208ecdda29659a9a9d1f36826",
    "2024-07-01_260.6.xml": "f6207742eb2c147b18eeeb568c94529c2d33fead8d61c1de9bb4fdb8143c709c",
    "2024-07-01_260.9.xml": "5777ba176b39e6738d76c740acebb08f88fd01e482701fd82c690f7cb99360bd",
    "2025-06-02_259.5.xml": "99e86d7d4d459e7ac72fbaf51b6c21dfbdaf19d208ecdda29659a9a9d1f36826",
    "2025-06-02_260.10.xml": "cefd451a3a150be15086b49d14deb02d2fdee671fa06b68aff5f674d811cf044",
    "2025-06-02_260.6.xml": "0ce631ed94fd1fde2e55e00c203feb3ead15d1a0da83d66f7bbca5d5ff44550b",
    "2026-07-02_259.5.xml": "969ac622e6f8e81a0c4965b0e82b3e205886a0a008de31e69607dc3624c5fea7",
}
PDF_SHA256 = {
    "us_dot_refunds_v1.pdf": "fdcf0a283b0ac6152b1e32492c1100ac302e6c8a230949f1fcfc7e66984c4593",
    "us_dot_refunds_v2.pdf": "bea957371c289258032b0fc77e8310464dfe4b3a0cd2a1c0dd87a7b62a3be9cf",
    "us_dot_refunds_v3.pdf": "8886e19a5881d6e9dec63f5ba1fade7fdd93df0ead798760578a2e7f81291ead",
}
RULE_DATE = date(2024, 6, 25)


@pytest.mark.parametrize(("name", "sha256"), sorted(ECFR_SHA256.items()))
def test_each_fetched_ecfr_file_is_unchanged_and_listed_with_its_url(name, sha256):
    assert hashlib.sha256((text.ECFR / name).read_bytes()).hexdigest() == sha256
    provenance = (text.HERE / "PROVENANCE.md").read_text(encoding="utf-8")
    on, section = name.removesuffix(".xml").split("_")
    assert sha256 in provenance and text.Source(on, section).url in provenance


def test_every_file_used_is_pinned_and_nothing_else_is_there():
    used = {s.path.name for v in text.VERSIONS for s in v.sources} | {s.path.name for s in text.EXTRA}
    assert used == set(ECFR_SHA256) == {p.name for p in text.ECFR.glob("*.xml")}


@pytest.mark.parametrize("version", text.VERSIONS, ids=lambda v: f"v{v.number}")
def test_intakes_reader_gets_back_every_word_and_the_pdf_is_pinned(version):
    data = text.pdf_path(version).read_bytes()
    assert data == text.build(version)
    assert hashlib.sha256(data).hexdigest() == PDF_SHA256[text.pdf_path(version).name]
    source = intake.read_pdf(data, text.pdf_path(version).name)
    assert source.text.split() == intake.normalize(text.document(version)).split()


def test_the_document_holds_the_regulations_paragraphs_word_for_word():
    """Every paragraph in a PDF is a run of the eCFR file's own text (259.5's gets the "(b)" of its parent prefixed)."""
    import xml.etree.ElementTree as ET  # noqa: S405 - the pinned files

    for version in text.VERSIONS:
        doc = intake.normalize(text.document(version))
        for s in version.sources:
            root = ET.fromstring(s.path.read_bytes())  # noqa: S314
            raw = intake.normalize(" ".join("".join(p.itertext()) for p in root.iter("P")))
            head, groups = text.paragraphs(s)
            assert head == intake.normalize(root.findtext("HEAD") or "")
            for g in groups:
                assert intake.normalize(g) in doc and intake.normalize(g.removeprefix("(b)")) in raw


def test_the_loaded_text_does_not_change_inside_a_version():
    """259.5(b)(5) on v1's last day, and on the 2026-07-02 amendment to 259.5's other paragraphs, is word for word
    the text loaded for v1 and v3."""
    para = lambda on: text.paragraphs(text.Source(on, "259.5", "(5)"))[1]  # noqa: E731
    assert para("2024-06-24") == para("2023-01-03") and para("2026-07-02") == para("2025-06-02")


def test_the_domain_is_like_rail_checked_by_doc_id_but_not_offered():
    assert domain_for("US-DOT-REFUNDS") is DOT and "US-DOT-REFUNDS" not in domains.DOC_IDS
    assert "US-DOT-REFUNDS" not in typing.get_args(api.DocId)
    assert DOT.intake_system.replace(prompts.REAL_INTAKE_RULES + "\n", "") == prompts.LONG_INTAKE_SYSTEM
    assert DOT.judge_system == prompts.GENERIC_JUDGE_SYSTEM and DOT.intake_max_items == 16


def test_the_onboarding_records_are_complete_and_name_their_pdfs():
    decisions = onboard.load_decisions()
    assert onboard.complete() and [d["version"] for d in decisions] == [1, 2, 3, 3]
    versions = {v.number: v for v in text.VERSIONS}
    for d in decisions:
        record = json.loads(onboard.recording_path(d["upload"], d["version"]).read_text(encoding="utf-8"))
        pdf = text.pdf_path(versions[d["version"]]).read_bytes()
        assert record["pdf_sha256"] == hashlib.sha256(pdf).hexdigest()
        assert set(d["items"]) == set(d["notes"]) and set(map(str, d["accept"])) <= set(d["items"])
        assert all(c["why"] for c in d["changes"])


def test_the_first_upload_is_what_intake_checked_and_was_accepted_unblocked():
    record = json.loads(onboard.recording_path(1, 1).read_text(encoding="utf-8"))
    v1 = text.VERSIONS[0]
    source = intake.read_pdf(text.pdf_path(v1).read_bytes(), text.pdf_path(v1).name)
    proposals, _ = intake.check_items(RailIntakeResult.model_validate(record["result"]), source, {}, 16)
    assert [p.item_no for p in proposals if not p.blocked] == onboard.load_decisions()[0]["accept"]
    assert proposals[0].effective_from == text.AS_OF_FLOOR


def test_the_question_set_pairs_each_question_across_the_rule():
    assert 6 <= len({q.id for q in QUESTIONS}) == len(QUESTIONS) <= 10
    pairs: dict[str, list] = defaultdict(list)
    for q in QUESTIONS:
        pairs[q.id[:-1]].append(q)
        assert q.question and q.draft and q.reading and q.as_of >= text.AS_OF_FLOOR
    for qs in pairs.values():
        assert len(qs) == 2 and len({(q.question, q.draft) for q in qs}) == 1
        before, after = sorted(qs, key=lambda q: q.as_of)
        assert before.as_of < RULE_DATE <= after.as_of


@pytest.mark.db2
def test_the_domain_rebuilt_from_the_records_changes_on_the_rules_dates(settings, embeddings, admin_conn):
    from asof import db, policy, schema

    target = "ASOF_TEST_REAL"
    try:
        onboard.rebuild(settings, target, embeddings, log=lambda _m: None)
        with db.connection(settings, "app") as conn:
            clauses = {c["clause_id"]: c for c in policy.timeline(conn, target, onboard.DOC_ID)}
        prompt = clauses["REF-001"]["versions"]

        def on(day: date) -> str:
            return next(v["text"] for v in prompt if v["from"] <= day < v["to"])

        assert "within 20 days" in on(date(2024, 6, 24)) and "processing fee" not in on(date(2024, 6, 24))
        assert "original form of payment" in on(date(2024, 6, 25)) and "processing fee" in on(date(2025, 2, 10))
        assert {c["versions"][0]["from"] for k, c in clauses.items() if k != "REF-001"} == {date(2024, 8, 12)}
        with pytest.raises(onboard.OnboardError):
            onboard.prepare(settings, db.SCHEMA, embeddings)  # never the main schema
    finally:
        schema.drop(admin_conn, target)
