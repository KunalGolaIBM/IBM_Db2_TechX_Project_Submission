"""Evaluation of the gate on labelled cases.

Two splits: `dev` (20 cases, including the scenarios used while debugging; fine to iterate
on) and `test` (40 new cases, committed before the first run and frozen: the runner refuses
to run it if the file's SHA-256 changes).

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
from typing import Any

from pydantic import BaseModel

SPLITS = {"dev": "cases_dev.jsonl", "test": "cases_test.jsonl"}
# Pinned when the test split was committed (81b5b69), before any run.
FROZEN_TEST_SHA256 = "bfb24f0ac4722bd6925e4e12a4820bc1e498f15958f9701c447161e78cffd5b2"
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
                          d["key_version"], d["note"]))
    return cases


class CountingLLM:
    """Passes calls through to the real client and counts them, per case."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    @property
    def info(self) -> str:
        return self.inner.info

    def structured(self, schema: type[BaseModel], messages):
        self.calls += 1
        return self.inner.structured(schema, messages)

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
    }


def _rate(num: int, den: int) -> float | None:
    return None if den == 0 else round(num / den, 4)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    def block(rs: list[dict[str, Any]]) -> dict[str, Any]:
        bad = [r for r in rs if not r["draft_ok"]]
        good = [r for r in rs if r["draft_ok"]]
        keyed = [r for r in rs if r["cited_key_clause"] is not None]
        lat = sorted(r["latency_ms"] for r in rs) or [0]
        return {
            "n": len(rs),
            "false_allow_rate": _rate(sum(r["false_allow"] for r in bad), len(bad)),
            "false_block_rate": _rate(sum(r["false_block"] for r in good), len(good)),
            "safe_rate": _rate(sum(r["safe"] for r in rs), len(rs)),
            "ideal_rate": _rate(sum(r["ideal"] for r in rs), len(rs)),
            "escalation_rate": _rate(sum(r["decision"] == "ESCALATED" for r in rs), len(rs)),
            "correction_rate": _rate(sum(r["decision"] == "CORRECTED" for r in rs), len(rs)),
            "citation_accuracy": _rate(sum(bool(r["cited_key_clause"]) for r in keyed), len(keyed)),
            "rule_overrides": sum(r["rule_overrides"] for r in rs),
            "errors": sum(r["reason"] == "ERROR_FAIL_CLOSED" for r in rs),
            "latency_p50_ms": int(statistics.median(lat)),
            "latency_p90_ms": int(lat[min(len(lat) - 1, int(round(0.9 * (len(lat) - 1))))]),
            "llm_calls_mean": round(statistics.fmean(r["llm_calls"] for r in rs), 2) if rs and "llm_calls" in rs[0] else None,
        }

    categories = sorted({r["category"] for r in records})
    return {"overall": block(records), "by_category": {c: block([r for r in records if r["category"] == c])
                                                       for c in categories}}
