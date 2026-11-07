#!/usr/bin/env python3
"""Run the held-out SciFact evaluation against the real AEGIS pipeline.

The SciFact test split does not publish evidence labels, so this runner uses the
dev split (300 labelled claims) as a held-out set. Gold labels are used only for
scoring and for retrieval Recall@K; they are never passed to retrieval or the
verifier.

Typical use:

    make scifact-data
    python experiments/run_scifact_eval.py --import --limit 100

Outputs:
    experiments/predictions/scifact_dev_predictions.jsonl
    experiments/results/scifact_dev_metrics.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.repository import Db2Repository  # noqa: E402
from app.models.domain import ExtractedClaim  # noqa: E402
from app.services.claim_verification import ClaimVerificationService  # noqa: E402
from app.services.llm import LangChainLLMClient  # noqa: E402
from experiments.metrics import (  # noqa: E402
    classification_metrics,
    false_positive_examples,
    label_distribution,
    latency_stats,
    retrieval_recall_at_k,
)
from experiments.retrieval_eval import CorpusBM25Index  # noqa: E402
from experiments.scifact_adapter import import_scifact_corpus, scifact_document_map  # noqa: E402
from experiments.scifact_loader import ScifactClaim, load_scifact_claims  # noqa: E402

SCIFACT_SOURCE = "scifact"
PREDICTIONS_FILE = ROOT / "experiments" / "predictions" / "scifact_dev_predictions.jsonl"
RESULTS_FILE = ROOT / "experiments" / "results" / "scifact_dev_metrics.json"
DOC_MAP_FILE = ROOT / "experiments" / "results" / "scifact_doc_map.json"


def _select_claims(claims: list[ScifactClaim], limit: int) -> list[ScifactClaim]:
    if limit <= 0 or limit >= len(claims):
        return sorted(claims, key=lambda claim: int(claim.claim_id))
    # Label-agnostic, deterministic subset: first N by benchmark claim ID. Gold
    # labels are never consulted when choosing evaluation examples.
    return sorted(claims, key=lambda claim: int(claim.claim_id))[:limit]


def _load_done(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            done.add(str(json.loads(line)["claim_id"]))
        except (KeyError, json.JSONDecodeError):
            continue
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AEGIS on SciFact dev")
    parser.add_argument("--corpus", default="data/scifact/corpus.jsonl")
    parser.add_argument("--claims", default="data/scifact/claims_dev.jsonl")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Import corpus into Db2")
    parser.add_argument("--limit", type=int, default=0, help="0 = all claims; otherwise balanced subset")
    parser.add_argument("--model", default=os.getenv("EVAL_LLM_MODEL", "qwen2.5:3b-instruct"))
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("EVAL_LLM_MAX_TOKENS", "450")))
    parser.add_argument("--retrieval-k", type=int, default=10)
    parser.add_argument("--classification-k", type=int, default=4)
    parser.add_argument("--fresh", action="store_true", help="Discard previous predictions")
    parser.add_argument("--output", default=str(RESULTS_FILE))
    args = parser.parse_args()

    if not Path(args.corpus).exists() or not Path(args.claims).exists():
        print(
            "ERROR: SciFact data is missing. Run `make scifact-data` first "
            "(license: CC BY-NC 2.0).",
            file=sys.stderr,
        )
        return 2

    base = get_settings()
    settings = base.model_copy(
        update={
            "llm_model": args.model,
            "llm_max_tokens": args.max_tokens,
            "llm_timeout_seconds": 120,
            "llm_max_retries": 1,
            "llm_evidence_top_k": args.classification_k,
            "llm_temperature": 0.0,
        }
    )
    repository = Db2Repository(settings)

    import_stats = None
    if args.do_import:
        print(f"Importing SciFact corpus from {args.corpus} ...", flush=True)
        started = time.monotonic()
        import_stats = import_scifact_corpus(repository, args.corpus)
        import_stats["elapsed_seconds"] = round(time.monotonic() - started, 2)
        print(f"Import: {import_stats}", flush=True)

    doc_map = scifact_document_map(repository)
    if not doc_map:
        print("ERROR: no SciFact documents found in Db2. Use --import first.", file=sys.stderr)
        return 2
    DOC_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOC_MAP_FILE.write_text(
        json.dumps({str(external): internal for external, internal in sorted(doc_map.items())}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    claims = _select_claims(load_scifact_claims(args.claims), args.limit)
    print(
        f"Evaluating {len(claims)} claims with model={args.model}, "
        f"retrieval_k={args.retrieval_k}, classification_k={args.classification_k}",
        flush=True,
    )

    PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if args.fresh and PREDICTIONS_FILE.exists():
        PREDICTIONS_FILE.unlink()
    done = _load_done(PREDICTIONS_FILE)

    llm = LangChainLLMClient(settings)
    print("Loading SciFact passages from Db2 for BM25 index ...", flush=True)
    retriever = CorpusBM25Index(repository, SCIFACT_SOURCE)
    print(
        f"Indexed {len(retriever.passages)} passages in {retriever.load_seconds:.2f}s",
        flush=True,
    )
    verifier = ClaimVerificationService(llm, repair_explanations=False)

    started_total = time.monotonic()
    with PREDICTIONS_FILE.open("a", encoding="utf-8") as output:
        for index, claim in enumerate(claims, start=1):
            if claim.claim_id in done:
                continue
            extracted = ExtractedClaim(
                original_claim=claim.claim,
                normalized_claim=claim.claim,
                claim_type="FACTUAL",
            )
            t0 = time.monotonic()
            candidates = retriever.retrieve(extracted, top_k=args.retrieval_k)
            retrieval_ms = (time.monotonic() - t0) * 1000

            retrieved_doc_ids: list[int] = []
            for candidate in candidates:
                if candidate.document_id not in retrieved_doc_ids:
                    retrieved_doc_ids.append(candidate.document_id)

            t1 = time.monotonic()
            try:
                assessment = verifier.verify(extracted, candidates[: args.classification_k])
            except Exception as exc:  # one claim must not abort the run
                verification_ms = (time.monotonic() - t1) * 1000
                record = {
                    "claim_id": claim.claim_id,
                    "predicted_label": "VERIFICATION_ERROR",
                    "verification_method": "verification_exception",
                    "retrieved_doc_ids": retrieved_doc_ids,
                    "evidence_passage_ids": [],
                    "retrieval_ms": round(retrieval_ms, 2),
                    "verification_ms": round(verification_ms, 2),
                    "latency_ms": round(retrieval_ms + verification_ms, 2),
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
                output.write(json.dumps(record) + "\n")
                output.flush()
                print(
                    f"  {index}/{len(claims)} | VERIFICATION_ERROR | {type(exc).__name__}",
                    flush=True,
                )
                continue
            verification_ms = (time.monotonic() - t1) * 1000

            record = {
                "claim_id": claim.claim_id,
                "predicted_label": assessment.classification.value,
                "verification_method": assessment.verification_method,
                "retrieved_doc_ids": retrieved_doc_ids,
                "evidence_passage_ids": [item.passage_id for item in assessment.evidence],
                "retrieval_ms": round(retrieval_ms, 2),
                "verification_ms": round(verification_ms, 2),
                "latency_ms": round(retrieval_ms + verification_ms, 2),
                "numerical_analysis": assessment.numerical_analysis,
            }
            output.write(json.dumps(record) + "\n")
            output.flush()
            if index % 10 == 0 or index == len(claims):
                elapsed = time.monotonic() - started_total
                per_claim = elapsed / max(1, len(done) + index)
                remaining = len(claims) - index
                print(
                    f"  {index}/{len(claims)} | {assessment.classification.value} | "
                    f"{elapsed:.0f}s elapsed | ~{per_claim * remaining:.0f}s remaining",
                    flush=True,
                )

    predictions = {}
    for line in PREDICTIONS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            predictions[str(record["claim_id"])] = record

    gold_labels: list[str] = []
    predicted_labels: list[str] = []
    valid_claim_ids: list[str] = []
    errors = 0
    latencies: list[float] = []
    retrieval_gold: dict[str, list[int]] = {}
    retrieval_predicted: dict[str, list[int]] = {}
    for claim in claims:
        prediction = predictions.get(claim.claim_id)
        if not prediction:
            continue
        latencies.append(float(prediction["latency_ms"]))
        gold_external = [doc_id for doc_id in claim.cited_doc_ids if doc_id in doc_map]
        if gold_external:
            retrieval_gold[claim.claim_id] = [doc_map[doc_id] for doc_id in gold_external]
            retrieval_predicted[claim.claim_id] = [
                int(doc_id) for doc_id in prediction["retrieved_doc_ids"]
            ]
        label = prediction["predicted_label"]
        if label == "VERIFICATION_ERROR":
            errors += 1
            continue
        if label not in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"):
            errors += 1
            continue
        valid_claim_ids.append(claim.claim_id)
        gold_labels.append(claim.gold_label)
        predicted_labels.append(label)

    if not valid_claim_ids:
        print("ERROR: no valid predictions to score.", file=sys.stderr)
        return 1

    classification = classification_metrics(gold_labels, predicted_labels)
    results = {
        "dataset": {
            "name": "SciFact",
            "split": "dev",
            "license": "CC BY-NC 2.0",
            "claims_file": args.claims,
            "corpus_file": args.corpus,
            "corpus_documents": len(doc_map),
            "evaluated_claims": len(claims),
            "scored_claims": len(valid_claim_ids),
            "errors": errors,
            "coverage": round(len(valid_claim_ids) / len(claims), 6),
            "gold_label_distribution": label_distribution(gold_labels),
            "note": "SciFact test split has no public evidence labels; dev is used as the held-out labelled set.",
        },
        "settings": {
            "model": args.model,
            "temperature": 0.0,
            "retrieval": "db2_full_corpus_bm25",
            "retrieval_k": args.retrieval_k,
            "classification_k": args.classification_k,
            "max_tokens": args.max_tokens,
            "repair_explanations": False,
            "prompt_version": "aegis-claim-verification-v1",
        },
        "classification": classification,
        "retrieval": {
            **{f"recall_at_{k}": retrieval_recall_at_k(retrieval_gold, retrieval_predicted, k) for k in (1, 3, 5, 10)},
            "claims_with_gold_docs": len(retrieval_gold),
            "mean_retrieval_ms": round(sum(p["retrieval_ms"] for p in predictions.values()) / len(predictions), 2),
        },
        "latency": latency_stats(latencies),
        "total_claim_processing_seconds": round(sum(latencies) / 1000, 2),
        "total_evaluation_seconds": round(retriever.load_seconds + sum(latencies) / 1000, 2),
        "false_positive_examples": false_positive_examples(
            valid_claim_ids, gold_labels, predicted_labels
        ),
        "predictions_file": str(PREDICTIONS_FILE.relative_to(ROOT)),
        "document_id_map_file": str(DOC_MAP_FILE.relative_to(ROOT)),
        "import": import_stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {output_path}", flush=True)
    print(json.dumps({
        "macro_f1": classification["macro_f1"],
        "accuracy": classification["accuracy"],
        "n": classification["n"],
        "coverage": results["dataset"]["coverage"],
        "retrieval": results["retrieval"],
        "latency": results["latency"],
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
