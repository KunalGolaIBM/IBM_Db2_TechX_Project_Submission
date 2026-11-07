#!/usr/bin/env python3
"""Retrieval-only evaluation: 40 real-paper cases + SciFact predictions."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.repository import Db2Repository  # noqa: E402
from app.models.domain import ExtractedClaim  # noqa: E402
from experiments.metrics import retrieval_recall_at_k  # noqa: E402
from experiments.retrieval_eval import CorpusBM25Index  # noqa: E402
from experiments.scifact_loader import load_scifact_claims  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "research_claims.json"
OUT = ROOT / "reports" / "retrieval_quality.json"

PAPER_PREFIX = {
    "transformer": "Attention Is All You Need",
    "bert": "BERT: Pre-training of Deep Bidirectional Transformers",
    "lora": "LoRA: Low-Rank Adaptation of Large Language Models",
}


def paper_from_source(source: str) -> str | None:
    lowered = source.lower()
    for key in PAPER_PREFIX:
        if lowered.startswith(key):
            return key
    return None


def main() -> int:
    settings = get_settings()
    repository = Db2Repository(settings)
    docs = repository.list_documents(limit=100)
    internal = {}
    for key, prefix in PAPER_PREFIX.items():
        match = next((doc for doc in docs if doc["title"].startswith(prefix)), None)
        if match:
            internal[key] = int(match["document_id"])
    if len(internal) < 3:
        print("ERROR: paper documents missing", file=sys.stderr)
        return 2

    index = CorpusBM25Index(repository, "pdf")
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["claims"]
    gold: dict[str, list[int]] = {}
    predicted: dict[str, list[int]] = {}
    latencies = []
    misses = []
    details = []
    for case in cases:
        paper = paper_from_source(case["source"])
        if paper is None:
            continue
        claim = ExtractedClaim(case["claim"], case["claim"], "FACTUAL")
        started = time.monotonic()
        candidates = index.retrieve(claim, top_k=5)
        latency_ms = (time.monotonic() - started) * 1000
        latencies.append(latency_ms)
        docs_seen = []
        for candidate in candidates:
            if candidate.document_id not in docs_seen:
                docs_seen.append(candidate.document_id)
        gold[case["claim_id"]] = [internal[paper]]
        predicted[case["claim_id"]] = docs_seen
        hit = internal[paper] in docs_seen
        details.append(
            {
                "claim_id": case["claim_id"],
                "category": case["category"],
                "expected_paper": paper,
                "retrieved_docs": docs_seen,
                "hit_at_5": hit,
                "latency_ms": round(latency_ms, 2),
            }
        )
        if not hit or docs_seen[0] != internal[paper]:
            misses.append(
                {
                    "claim_id": case["claim_id"],
                    "expected_paper": paper,
                    "top_1": docs_seen[0] if docs_seen else None,
                    "hit_at_5": hit,
                }
            )

    result = {
        "controlled_40": {
            "cases_with_gold_paper": len(gold),
            "recall": {
                f"at_{k}": retrieval_recall_at_k(gold, predicted, k) for k in (1, 3, 5)
            },
            "latency_ms": {
                "mean": round(sum(latencies) / len(latencies), 2),
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
            },
            "top1_misses_or_wrong": misses,
            "details": details,
        }
    }

    # SciFact retrieval from the completed 100-claim run.
    pred_path = ROOT / "experiments" / "predictions" / "scifact_dev_predictions.jsonl"
    map_path = ROOT / "experiments" / "results" / "scifact_doc_map.json"
    if pred_path.exists() and map_path.exists():
        doc_map = {
            int(external): int(inner)
            for external, inner in json.loads(map_path.read_text(encoding="utf-8")).items()
        }
        claims = load_scifact_claims(ROOT / "data" / "scifact" / "claims_dev.jsonl")
        selected = {str(json.loads(line)["claim_id"]) for line in pred_path.read_text().splitlines() if line.strip()}
        preds = {
            str(record["claim_id"]): record
            for record in (json.loads(line) for line in pred_path.read_text().splitlines() if line.strip())
        }
        scifact_gold = {}
        scifact_pred = {}
        for claim in claims:
            if claim.claim_id not in selected:
                continue
            gold_docs = [doc_map[i] for i in claim.cited_doc_ids if i in doc_map]
            if gold_docs:
                scifact_gold[claim.claim_id] = gold_docs
                scifact_pred[claim.claim_id] = preds[claim.claim_id]["retrieved_doc_ids"]
        result["scifact_100"] = {
            f"recall_at_{k}": retrieval_recall_at_k(scifact_gold, scifact_pred, k)
            for k in (1, 3, 5, 10)
        }
        result["scifact_100"]["claims_with_gold"] = len(scifact_gold)
        result["scifact_100"]["retrieval_mean_ms"] = round(
            sum(float(preds[c]["retrieval_ms"]) for c in scifact_gold) / len(scifact_gold), 2
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
