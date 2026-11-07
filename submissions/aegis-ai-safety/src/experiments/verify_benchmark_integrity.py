"""Benchmark-integrity checks for SciFact.

These checks verify that gold labels are not used for example selection or passed
to the verifier, and that cited evidence IDs map back to retrieved documents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.connection import query_all, transaction  # noqa: E402
from experiments.run_scifact_eval import _select_claims  # noqa: E402
from experiments.scifact_loader import load_scifact_claims  # noqa: E402

OUT = ROOT / "reports" / "benchmark_integrity.json"


def main() -> int:
    claims = load_scifact_claims(ROOT / "data" / "scifact" / "claims_dev.jsonl")
    selected = _select_claims(claims, 100)
    relabeled = [
        type(claim)(
            claim_id=claim.claim_id,
            claim=claim.claim,
            gold_label=("CONTRADICTED" if claim.gold_label == "SUPPORTED" else "SUPPORTED"),
            cited_doc_ids=claim.cited_doc_ids,
            evidence_doc_ids=claim.evidence_doc_ids,
        )
        for claim in claims
    ]
    selected_relabeled = _select_claims(relabeled, 100)
    selection_ignores_labels = [c.claim_id for c in selected] == [
        c.claim_id for c in selected_relabeled
    ]

    pred_path = ROOT / "experiments" / "predictions" / "scifact_dev_predictions.jsonl"
    predictions = [
        json.loads(line) for line in pred_path.read_text().splitlines() if line.strip()
    ]
    forbidden_fields = {"gold", "gold_label", "label", "evidence_label"}
    no_gold_in_predictions = all(not (forbidden_fields & set(record)) for record in predictions)

    # Evidence attribution: every cited passage must belong to a retrieved doc and
    # exist in the evaluation corpus.
    missing = []
    misattributed = []
    checked = 0
    with transaction() as connection:
        for record in predictions:
            retrieved = {int(doc_id) for doc_id in record.get("retrieved_doc_ids", [])}
            for passage_id in record.get("evidence_passage_ids", []):
                checked += 1
                rows = query_all(
                    connection,
                    "SELECT DOCUMENT_ID FROM PASSAGES WHERE PASSAGE_ID = ?",
                    (passage_id,),
                )
                if not rows:
                    missing.append({"claim_id": record["claim_id"], "passage_id": passage_id})
                elif int(rows[0]["document_id"]) not in retrieved:
                    misattributed.append(
                        {
                            "claim_id": record["claim_id"],
                            "passage_id": passage_id,
                            "document_id": int(rows[0]["document_id"]),
                        }
                    )

    results_path = ROOT / "experiments" / "results" / "scifact_dev_metrics.json"
    results = json.loads(results_path.read_text())
    settings = results.get("settings", {})
    selection_note = (
        "Label-agnostic: first N claims by benchmark ID; gold labels are only used for scoring."
    )
    payload = {
        "selection_ignores_labels": selection_ignores_labels,
        "selection_method": selection_note,
        "subset_size": len(selected),
        "gold_label_distribution_for_reporting_only": {
            label: sum(1 for claim in selected if claim.gold_label == label)
            for label in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
        },
        "predictions_contain_gold_fields": not no_gold_in_predictions,
        "predictions_record_count": len(predictions),
        "cited_passages_checked": checked,
        "missing_passages": missing,
        "misattributed_passages": misattributed,
        "evidence_attribution_passed": not missing and not misattributed,
        "model": settings.get("model"),
        "retrieval": settings.get("retrieval"),
        "retrieval_k": settings.get("retrieval_k"),
        "classification_k": settings.get("classification_k"),
        "predictions_file": str(pred_path.relative_to(ROOT)),
        "results_file": str(results_path.relative_to(ROOT)),
        "dataset_license": results.get("dataset", {}).get("license"),
        "note": "Gold labels are used only in the scoring step; the verifier receives claim text and retrieved passages.",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
