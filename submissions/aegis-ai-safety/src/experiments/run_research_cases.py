#!/usr/bin/env python3
"""Run the 40-case controlled real-paper challenge set through AEGIS.

The claims are already atomic; this tests retrieval, evidence-grounded
verification, numeric checks, and evidence attribution. Expected labels are used
only for scoring and are never passed to the pipeline.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
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
from experiments.retrieval_eval import CorpusBM25Index  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "research_claims.json"
CSV_PATH = ROOT / "reports" / "research_verification_results.csv"
SUMMARY_PATH = ROOT / "reports" / "research_verification_summary.json"


def main() -> int:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload["claims"]

    settings = get_settings()
    settings = settings.model_copy(
        update={
            "llm_max_tokens": 450,
            "llm_timeout_seconds": 180,
            "llm_max_retries": 1,
            "llm_evidence_top_k": 4,
            "llm_temperature": 0.0,
        }
    )
    repository = Db2Repository(settings)
    index = CorpusBM25Index(repository, "pdf")
    if len(index.passages) < 50:
        print("ERROR: the three paper PDFs are not in the library.", file=sys.stderr)
        return 2

    llm = LangChainLLMClient(settings)
    verifier = ClaimVerificationService(llm, repair_explanations=False)

    rows = []
    started_all = time.monotonic()
    for position, case in enumerate(cases, start=1):
        extracted = ExtractedClaim(
            original_claim=case["claim"],
            normalized_claim=case["claim"],
            claim_type="FACTUAL",
        )
        started = time.monotonic()
        error = ""
        try:
            candidates = index.retrieve(extracted, top_k=6)
            assessment = verifier.verify(extracted, candidates[:4])
            predicted = assessment.classification.value
            evidence = assessment.evidence
            numeric = assessment.numerical_analysis or ""
        except Exception as exc:  # one case must not abort the suite
            predicted = "VERIFICATION_ERROR"
            evidence = []
            numeric = ""
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
        elapsed_ms = (time.monotonic() - started) * 1000
        rows.append(
            {
                "claim_id": case["claim_id"],
                "category": case["category"],
                "claim": case["claim"],
                "expected": case["expected"],
                "predicted": predicted,
                "match": predicted == case["expected"],
                "evidence_passage_ids": ";".join(str(item.passage_id) for item in evidence),
                "evidence_documents": ";".join(item.document_title for item in evidence),
                "evidence_pages": ";".join(
                    str(item.page_number) if item.page_number is not None else ""
                    for item in evidence
                ),
                "model": f"{settings.llm_provider}/{settings.llm_model}",
                "latency_ms": round(elapsed_ms, 2),
                "numerical_analysis": numeric,
                "source_expectation": case["source"],
                "error": error,
            }
        )
        print(
            f"{position:02d}/{len(cases)} {case['claim_id']} {predicted:<22} "
            f"expected {case['expected']:<22} {elapsed_ms/1000:.1f}s",
            flush=True,
        )

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_category: dict[str, dict] = {}
    for category in sorted({row["category"] for row in rows}):
        subset = [row for row in rows if row["category"] == category]
        by_category[category] = {
            "n": len(subset),
            "correct": sum(1 for row in subset if row["match"]),
            "accuracy": round(sum(1 for row in subset if row["match"]) / len(subset), 6),
        }
    errors = sum(1 for row in rows if row["predicted"] == "VERIFICATION_ERROR")
    summary = {
        "suite": payload["suite"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": f"{settings.llm_provider}/{settings.llm_model}",
        "n": len(rows),
        "correct": sum(1 for row in rows if row["match"]),
        "accuracy": round(sum(1 for row in rows if row["match"]) / len(rows), 6),
        "by_category": by_category,
        "errors": errors,
        "total_seconds": round(time.monotonic() - started_all, 2),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 2),
        "confusion": {},
    }
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        confusion[row["expected"]][row["predicted"]] += 1
    summary["confusion"] = {k: dict(v) for k, v in confusion.items()}
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
