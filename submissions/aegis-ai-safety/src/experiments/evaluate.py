#!/usr/bin/env python3
"""Compute AEGIS evaluation metrics from SciFact predictions.

This script never invents results. If the dataset or prediction file is absent,
it exits with an error and writes nothing.

Example:
    python experiments/evaluate.py \
        --claims data/scifact/claims_test.jsonl \
        --predictions experiments/predictions/scifact_test_predictions.json \
        --output experiments/results/scifact_test_metrics.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experiments.metrics import (
    classification_metrics,
    false_positive_examples,
    label_distribution,
    latency_stats,
    retrieval_recall_at_k,
)
from experiments.scifact_loader import load_predictions, load_scifact_claims


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AEGIS predictions against SciFact")
    parser.add_argument("--claims", required=True, help="SciFact claims JSONL/JSON file")
    parser.add_argument("--predictions", required=True, help="AEGIS prediction JSONL/JSON file")
    parser.add_argument("--output", help="Optional path for a JSON results file")
    args = parser.parse_args()

    try:
        claims = load_scifact_claims(args.claims)
        predictions = load_predictions(args.predictions)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    claim_ids = []
    gold = []
    predicted = []
    latencies = []
    gold_docs: dict[str, list[int]] = {}
    retrieved_docs: dict[str, list[int]] = {}
    for claim in claims:
        prediction = predictions.get(claim.claim_id)
        if not prediction:
            continue
        claim_ids.append(claim.claim_id)
        gold.append(claim.gold_label)
        predicted.append(str(prediction.get("predicted_label") or "").upper())
        if prediction.get("latency_ms") is not None:
            latencies.append(float(prediction["latency_ms"]))
        if claim.cited_doc_ids:
            gold_docs[claim.claim_id] = list(claim.cited_doc_ids)
        if prediction.get("retrieved_doc_ids") is not None:
            retrieved_docs[claim.claim_id] = list(prediction["retrieved_doc_ids"])

    if not claim_ids:
        print("ERROR: no claim IDs overlap between the dataset and predictions.", file=sys.stderr)
        return 2

    results = {
        "dataset": {
            "name": "SciFact",
            "claims_file": str(args.claims),
            "predictions_file": str(args.predictions),
            "evaluated_claims": len(claim_ids),
            "gold_label_distribution": label_distribution(gold),
        },
        "classification": classification_metrics(gold, predicted),
        "false_positive_examples": false_positive_examples(claim_ids, gold, predicted),
        "latency": latency_stats(latencies),
    }
    if retrieved_docs:
        results["retrieval"] = {
            f"recall_at_{k}": retrieval_recall_at_k(gold_docs, retrieved_docs, k)
            for k in (1, 5, 10)
        }

    payload = json.dumps(results, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {output_path}")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
