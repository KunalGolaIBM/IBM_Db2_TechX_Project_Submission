"""Corpus consistency + an offline simulation of the Db2 rule engine.

The real comparison happens in SP_RECORD_TRACE (SQL). This test mirrors the
same four operators in Python so the seed corpus can be validated without a
running database, and so the expected demo outcome is pinned by assertions.

If a scheme's rules or a sentence in data/schemes.json change, this test
tells you immediately what the user-visible verdicts will become.
"""

from __future__ import annotations

import json

import pytest

from src.config import DATA_DIR
from src.models import ALL_FACTS, RuleRow
from src.rules import classify

DEMO_FACTS = {
    "age": 34,
    "income_annual": 180000,
    "land_holding_acres": 2,
    "marital_status": "widow",
    "gender": "female",
    "state_code": "UP",
    "residence": "rural",
    "house_type": "kutcha",
    "category": "obc",
    "occupation": "farmer",
    "has_girl_child": "yes",
    "girl_age": 17,
    "has_bank_account": "yes",
    "income_tax_payer": "no",
}

VALID_OPS = {"eq", "in", "lte", "gte"}


@pytest.fixture(scope="module")
def corpus():
    with open(DATA_DIR / "schemes.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_corpus_size(corpus):
    assert len(corpus["schemes"]) >= 14
    chunks = sum(len(s["chunks"]) for s in corpus["schemes"])
    rules = sum(len(s["rules"]) for s in corpus["schemes"])
    assert chunks >= 35
    assert rules >= 40


def test_scheme_ids_are_unique(corpus):
    ids = [s["scheme_id"] for s in corpus["schemes"]]
    assert len(ids) == len(set(ids))


def test_every_scheme_has_rules_and_clauses(corpus):
    for scheme in corpus["schemes"]:
        assert scheme["rules"], scheme["scheme_id"]
        assert scheme["chunks"], scheme["scheme_id"]
        assert scheme["level"] in {"central", "state"}
        assert scheme["status"] == "ACTIVE"
        assert scheme["source_url"].startswith("http")


def test_rules_use_the_canonical_vocabulary(corpus):
    for scheme in corpus["schemes"]:
        for rule in scheme["rules"]:
            assert rule["criterion_code"] in ALL_FACTS, (scheme["scheme_id"], rule)
            assert rule["op"] in VALID_OPS
            if rule["op"] in {"lte", "gte"}:
                assert isinstance(rule["num"], (int, float))
            else:
                assert rule["text"]
            assert rule["clause_ref"]
            assert isinstance(rule["mandatory"], bool)


def test_every_rule_has_a_clause_on_the_same_page(corpus):
    # ingestion maps a rule to a chunk on the same page; this guarantees the
    # mapping never silently falls back to "first chunk" for everything.
    for scheme in corpus["schemes"]:
        pages = {chunk.get("page_no") for chunk in scheme["chunks"]}
        for rule in scheme["rules"]:
            assert rule.get("source_page") in pages, (scheme["scheme_id"], rule)


def test_no_duplicate_clause_refs_within_a_scheme(corpus):
    for scheme in corpus["schemes"]:
        refs = [chunk["clause_ref"] for chunk in scheme["chunks"]]
        assert len(refs) == len(set(refs)), scheme["scheme_id"]


def _compare(rule, facts):
    """Mirror of the CASE expression in sql/04_procedure.sql."""
    value = facts.get(rule["criterion_code"])
    if value is None:
        return "UNKNOWN"
    if rule["op"] == "eq":
        return "PASS" if str(value).lower() == str(rule["text"]).lower() else "FAIL"
    if rule["op"] == "in":
        return "PASS" if str(value).lower() in str(rule["text"]).lower().split(",") else "FAIL"
    if rule["op"] == "lte":
        return "PASS" if float(value) <= float(rule["num"]) else "FAIL"
    if rule["op"] == "gte":
        return "PASS" if float(value) >= float(rule["num"]) else "FAIL"
    return "UNKNOWN"


def simulate(scheme, facts):
    rows = []
    for index, rule in enumerate(scheme["rules"], start=1):
        rows.append(
            RuleRow(
                scheme_id=scheme["scheme_id"],
                rule_id=index,
                criterion_code=rule["criterion_code"],
                rule_op=rule["op"],
                mandatory=1 if rule["mandatory"] else 0,
                observed_value=str(facts.get(rule["criterion_code"], "")) or None,
                verdict=_compare(rule, facts),
                clause_ref=rule["clause_ref"],
                value_num=rule.get("num"),
                value_text=rule.get("text"),
            )
        )
    return rows


@pytest.fixture(scope="module")
def demo_outcomes(corpus):
    outcomes = {}
    filtered = 0
    for scheme in corpus["schemes"]:
        if scheme["state_code"] not in ("ALL", DEMO_FACTS["state_code"]):
            filtered += 1
            continue
        outcomes[scheme["scheme_id"]] = classify(simulate(scheme, DEMO_FACTS))
    return outcomes, filtered


def test_demo_household_gets_the_expected_verdicts(demo_outcomes):
    outcomes, _ = demo_outcomes
    assert outcomes == {
        "pm-kisan": "ELIGIBLE",
        "pmjay": "ELIGIBLE",          # BPL is advisory here
        "ujjwala": "CLARIFY",         # BPL is mandatory and unknown
        "sukanya-samriddhi": "NEAR_MISS",
        "pmay-g": "ELIGIBLE",
        "nsap-widow": "NEAR_MISS",
        "post-matric-scst": "NOT_ELIGIBLE",
        "nfsa-phh": "NEAR_MISS",
        "kanya-sumangala": "ELIGIBLE",
        "pm-svanidhi": "NOT_ELIGIBLE",
        "apy": "ELIGIBLE",
        "pmkvy": "NOT_ELIGIBLE",
        "pm-vishwakarma": "NOT_ELIGIBLE",
        "fasal-bima": "ELIGIBLE",
    }


def test_residency_filter_excludes_exactly_one_state_scheme(demo_outcomes):
    _, filtered = demo_outcomes
    assert filtered == 1


def test_demo_spread_is_balanced(demo_outcomes):
    outcomes, _ = demo_outcomes
    labels = list(outcomes.values())
    assert labels.count("ELIGIBLE") == 6
    assert labels.count("NEAR_MISS") == 3
    assert labels.count("CLARIFY") == 1
    assert labels.count("NOT_ELIGIBLE") == 4
