"""Evaluation of the gate on labelled cases.

Airline (Aurelia Air): `dev` (20 cases, including the scenarios used while debugging; fine to
iterate on) and `test` (40 new cases, committed before the first run and frozen: the runner
refuses to run it if the file's SHA-256 changes). Bank (Fernhollow Bank, the second domain):
`bank-dev` (12) and `bank-test` (26), frozen the same way before its first run. Escalations (both
domains): `escalation-dev` (14, for iterating) and `escalation-test` (33, frozen before its first run)
target the known causes of escalating a draft that could have been corrected or passed.
`situation-test` (12, both domains, frozen before its first run) holds drafts whose premise about the
customer ("the delay was within our control") contradicts or restates what the customer said; its
first run found a gap that was then fixed, so `situation-test2` (12 new cases) is the blind one.
`situation-test3` (20, both domains) was written after a later run of situation-test2 released a draft whose
premise the claim extractor had turned into a general rule, and pinned before any change meant to fix that.

Metrics:
- false-allow rate: drafts that are wrong for their date but were released as PASS,
  over all wrong drafts. The safety number.
- false-block rate: correct drafts that were rewritten or escalated, over all correct drafts.
- safe decisions: the decision was one of the case's acceptable outcomes.
- ideal decisions: exactly the expected decision (PASS, CORRECTED or ESCALATED).
- citation accuracy: the key claim was checked against the right clause version.
- rule overrides: claims the rule checker turned from the judge's SUPPORTED to CONTRADICTED.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any, TypeVar

from pydantic import BaseModel

from ..llm import LLMResult, structured_call

T = TypeVar("T", bound=BaseModel)

SPLITS = {"dev": "cases_dev.jsonl", "test": "cases_test.jsonl",
          "bank-dev": "bank_cases_dev.jsonl", "bank-test": "bank_cases_test.jsonl",
          "extractor-test": "extractor_cases_test.jsonl", "bank-test2": "bank_cases_test2.jsonl",
          "escalation-dev": "escalation_cases_dev.jsonl", "escalation-test": "escalation_cases_test.jsonl",
          "situation-dev": "situation_cases_dev.jsonl", "situation-test": "situation_cases_test.jsonl",
          "situation-test2": "situation_cases_test2.jsonl", "situation-test3": "situation_cases_test3.jsonl",
          "list-dev": "list_cases_dev.jsonl", "list-test": "list_cases_test.jsonl"}
SPLIT_DOC = {"dev": "AURELIA-CSP", "test": "AURELIA-CSP", "bank-dev": "FERNHOLLOW-FEES", "bank-test": "FERNHOLLOW-FEES",
             "extractor-test": "AURELIA-CSP", "bank-test2": "FERNHOLLOW-FEES",
             # both documents; every case names its own doc_id
             "escalation-dev": "AURELIA-CSP", "escalation-test": "AURELIA-CSP",
             "situation-dev": "AURELIA-CSP", "situation-test": "AURELIA-CSP", "situation-test2": "AURELIA-CSP",
             "situation-test3": "AURELIA-CSP", "list-dev": "AURELIA-CSP", "list-test": "AURELIA-CSP"}
# Pinned when the test split was committed (81b5b69), before any run.
FROZEN_TEST_SHA256 = "bfb24f0ac4722bd6925e4e12a4820bc1e498f15958f9701c447161e78cffd5b2"
# Each frozen split, pinned in the commit that added it and before its first run.
FROZEN = {"test": FROZEN_TEST_SHA256,
          "bank-test": "ad6907ec5ffdc572a6232f1599c7eddfc65fdb8d5e39ef4837e14e2c3593a3f9",
          # Drafts that try to talk the extractor out of a wrong claim (both domains), pinned before its first run.
          "extractor-test": "163e48a9e708f19c4697f422a0d615225a41e4223cf1f7b84ec2060239f1454b",
          # A second, blind bank split: the first one stopped being blind when its run found a data gap that was fixed.
          "bank-test2": "1378b2855e109e114a4c2890ee71f536fc18c9ffac2b2ffd4cea7417baa0870b",
          # New cases (both domains) aimed at the known causes of unnecessary escalations (T06, T12, T20, T31,
          # T33, T36 and similar), pinned before its first run and before any change meant to reduce them.
          "escalation-test": "fecf9760292348940e921e924d61eee4e2f0648c5de7340f73fa4aa0f0c95510",
          # Drafts whose premise about the customer contradicts what the customer said, and drafts that restate it
          # correctly. Written after the change that shows the judge the question (11ef14c), from scratch, and
          # pinned before its first run: a blind measure of that change, not a set it was tuned on.
          "situation-test": "d0e0ec60d809c7678bf1bcb0a8b93e0a974e3d02f32682ea45fdccf2264a3393",
          # New cases written after the situation_conflict change (12e8d93), which situation-test motivated, and
          # pinned before its first run: the blind measure of that change.
          "situation-test2": "fb6bc52aef058a581585ecfcbdd2c07f8c149518b6cb402e7e7ca761cb46a13d",
          # Premise drafts (both domains) written after the 5861368 run of situation-test2 released SU01, whose
          # premise the extractor had turned into a general rule. Pinned before its first run and before any change
          # meant to fix that, so it gives a baseline on the unchanged check and then the measure of the change.
          "situation-test3": "cfb8c55b6beb7dbae7ad4fef5be8482cd7f8c4a9c9aea5c701f85bef65e273a9",
          # Drafts that claim a relation or a document qualifies when the clause's list (eligible_relations,
          # accepted_documents) leaves it out, and correct drafts that name listed ones or rightly exclude others.
          # Written after the watsonx.ai run released T20 (a mother-in-law counted as immediate family), from scratch,
          # and pinned before its first run and before any change meant to catch that.
          "list-test": "97974df816f6130690c48e9259dbd3251bec5b9580364abdc781624faca1536a"}
EVAL_SCHEMA = "ASOF_EVAL"
DECISIONS = ("PASS", "CORRECTED", "ESCALATED")


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    question: str
    draft: str
    as_of: date
    draft_ok: bool
    expected: str
    acceptable: tuple[str, ...]
    key_clause: str | None
    key_version: str | None
    note: str
    doc_id: str | None = None  # a split's cases may span documents; None means the split's own


def _path(split: str):
    return resources.files("asof") / "eval" / SPLITS[split]


def split_sha256(split: str) -> str:
    return hashlib.sha256(_path(split).read_bytes()).hexdigest()


def load_cases(split: str) -> list[Case]:
    cases = []
    for line in _path(split).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        cases.append(Case(d["id"], d["category"], d["question"], d["draft"], date.fromisoformat(d["as_of"]),
                          bool(d["draft_ok"]), d["expected"], tuple(d["acceptable"]), d["key_clause"],
                          d["key_version"], d["note"], d.get("doc_id")))
    return cases


class CountingLLM:
    """Passes calls through to the real client and counts them, per case."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls = 0
        self.input_tokens = 0   # as the provider reports them; 0 where it reports none
        self.output_tokens = 0

    @property
    def info(self) -> str:
        return self.inner.info

    def begin_check(self) -> None:
        getattr(self.inner, "begin_check", lambda: None)()

    def structured(self, schema: type[T], messages: list[tuple[str, str]], choices: dict[str, list[str]] | None = None,
                   max_chars: int | None = None) -> LLMResult[T]:
        self.calls += 1
        result = structured_call(self.inner, schema, messages, choices, max_chars)
        self.input_tokens += result.input_tokens or 0
        self.output_tokens += result.output_tokens or 0
        return result

    def tool_round(self, messages, tools):
        self.calls += 1
        msg = self.inner.tool_round(messages, tools)
        usage = getattr(msg, "usage_metadata", None) or {}
        self.input_tokens += usage.get("input_tokens") or 0
        self.output_tokens += usage.get("output_tokens") or 0
        return msg

    def run(self, fn):
        self.calls += 1
        return self.inner.run(fn)


def score(case: Case, result) -> dict[str, Any]:
    """One case's outcome as a flat record."""
    claims = [(1, c) for c in result.claims] + [(2, c) for c in result.rewrite_claims]
    cited = None
    if case.key_clause:
        cited = any(c.clause and c.clause.clause_id == case.key_clause and c.clause.version_label == case.key_version
                    for c in result.claims)
    return {
        "id": case.id, "category": case.category, "as_of": case.as_of.isoformat(), "draft_ok": case.draft_ok,
        "expected": case.expected, "acceptable": list(case.acceptable), "decision": result.decision,
        "reason": result.reason_code, "ideal": result.decision == case.expected,
        "safe": result.decision in case.acceptable,
        "false_allow": (not case.draft_ok) and result.decision == "PASS",
        "false_block": case.draft_ok and result.decision != "PASS",
        "cited_key_clause": cited, "error": result.error,
        "rule_overrides": sum(1 for _, c in claims if c.llm_verdict == "SUPPORTED" and c.verdict == "CONTRADICTED"),
        "latency_ms": result.latency_ms,
        "claims": [f"p{p}#{c.claim_no} {c.verdict} (llm {c.llm_verdict}, rule {c.rule_check}) "
                   f"{c.clause.clause_id + ' ' + c.clause.version_label if c.clause else '-'}: {c.text[:90]}"
                   for p, c in claims],
        "final_answer": result.final_answer[:400],
        "unchecked": list(getattr(result, "unchecked", []))[:10],
        "agent_tool_calls": len(getattr(result, "investigation", []) or []),
        "agent_new_clauses": sorted({c for step in (getattr(result, "investigation", []) or []) for c in step.get("new", [])}),
    }


def _rate(num: int, den: int) -> float | None:
    return None if den == 0 else round(num / den, 6)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    def block(rs: list[dict[str, Any]]) -> dict[str, Any]:
        bad = [r for r in rs if not r["draft_ok"]]
        good = [r for r in rs if r["draft_ok"]]
        keyed = [r for r in rs if r["cited_key_clause"] is not None]
        lat = sorted(r["latency_ms"] for r in rs) or [0]
        return {
            "n": len(rs),
            "wrong_drafts": len(bad), "false_allows": sum(r["false_allow"] for r in bad),
            "correct_drafts": len(good), "false_blocks": sum(r["false_block"] for r in good),
            "false_allow_rate": _rate(sum(r["false_allow"] for r in bad), len(bad)),
            "false_block_rate": _rate(sum(r["false_block"] for r in good), len(good)),
            "safe_rate": _rate(sum(r["safe"] for r in rs), len(rs)),
            "ideal_rate": _rate(sum(r["ideal"] for r in rs), len(rs)),
            "escalation_rate": _rate(sum(r["decision"] == "ESCALATED" for r in rs), len(rs)),
            "correction_rate": _rate(sum(r["decision"] == "CORRECTED" for r in rs), len(rs)),
            "citation_accuracy": _rate(sum(bool(r["cited_key_clause"]) for r in keyed), len(keyed)),
            "rule_overrides": sum(r["rule_overrides"] for r in rs),
            # Wrong drafts where the deterministic rule check found a RULE_JSON mismatch on the draft itself,
            # whatever the judge said: the backstop working, not only overruling.
            "rule_flagged": sum(1 for r in bad if any(c.startswith("p1#") and "rule MISMATCH" in c
                                                      for c in r.get("claims", []))),
            "errors": sum(r["reason"] == "ERROR_FAIL_CLOSED" for r in rs),
            "latency_p50_ms": int(statistics.median(lat)),
            "latency_p90_ms": int(lat[min(len(lat) - 1, int(round(0.9 * (len(lat) - 1))))]),
            "llm_calls_mean": round(statistics.fmean(r["llm_calls"] for r in rs), 2) if rs and "llm_calls" in rs[0] else None,
        }

    categories = sorted({r["category"] for r in records})
    return {"overall": block(records), "by_category": {c: block([r for r in records if r["category"] == c])
                                                       for c in categories}}
