"""The routing evaluation's labelled cases: which policy document a question and draft belong to, or that a person
must be asked.

Written and pinned before the router existed (the test split's SHA-256 is fixed below and checked by a test), so
nothing about the router shaped them. Each case names the document a careful human would check the draft against, or
ASK when the question could belong to either document, to neither, or needs both. The drafts are only routing input:
they are not meant to be correct answers. Categories:

    clear_airline, clear_bank   one document's vocabulary only
    trap                        words the other document also uses (refund, transfer, travelling, international)
    ambiguous                   nothing says which document applies
    out_of_scope                not a policy question for either document
    mixed                       needs both documents at once, so one check cannot cover it
    injection                   tells the router where to send it; the content decides
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
SPLITS = {"routing-dev": "routing_cases_dev.jsonl", "routing-test": "routing_cases_test.jsonl"}
ASK = "ASK"
# Pinned before the router was written. Never edit routing_cases_test.jsonl; tune only on the dev split.
FROZEN = {"routing-test": "10d986622a49b9e76758acc4be60d5e337e6a5416ef7fc03edbb0fdd89185692"}


@dataclass(frozen=True)
class RoutingCase:
    id: str
    category: str
    question: str
    draft: str
    as_of: date
    expected: str  # a doc_id, or ASK
    acceptable: tuple[str, ...]
    note: str


def split_sha256(split: str) -> str:
    return hashlib.sha256((HERE / SPLITS[split]).read_bytes()).hexdigest()


def load(split: str) -> list[RoutingCase]:
    out = []
    for line in (HERE / SPLITS[split]).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out.append(RoutingCase(d["id"], d["category"], d["question"], d["draft"], date.fromisoformat(d["as_of"]),
                                   d["expected"], tuple(d["acceptable"]), d["note"]))
    return out
