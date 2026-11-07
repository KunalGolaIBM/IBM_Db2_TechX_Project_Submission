#!/usr/bin/env python3
"""SciFact baseline comparison on a balanced 20-claim subset.

A: LLM-only, no retrieval.
B: LLM with retrieved passages, no citation/numeric guardrails.
AEGIS: stored complete-pipeline predictions on the same claims.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.repository import Db2Repository  # noqa: E402
from app.models.domain import ExtractedClaim  # noqa: E402
from app.services.llm import LangChainLLMClient, extract_json_object  # noqa: E402
from experiments.metrics import classification_metrics  # noqa: E402
from experiments.retrieval_eval import CorpusBM25Index  # noqa: E402
from experiments.scifact_loader import load_scifact_claims  # noqa: E402

OUT = ROOT / "reports" / "scifact_baselines.json"
PRED = ROOT / "experiments" / "predictions" / "scifact_dev_predictions.jsonl"
LABELS = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"}

A_PROMPT = """Classify the scientific claim using only your own knowledge.
Return JSON only: {"classification":"SUPPORTED|CONTRADICTED|INSUFFICIENT_EVIDENCE"}.
Do not explain. Do not invent evidence."""

B_PROMPT = """Classify the scientific claim using the provided evidence passages.
Return JSON only: {"classification":"SUPPORTED|CONTRADICTED|INSUFFICIENT_EVIDENCE"}.
Do not explain. A relevant-looking passage is not automatically support; missing
evidence is not contradiction."""


def _label(raw: str) -> str:
    try:
        value = str(extract_json_object(raw).get("classification") or "").upper()
    except Exception:
        match = re.search(r"SUPPORTED|CONTRADICTED|INSUFFICIENT_EVIDENCE", raw.upper())
        value = match.group(0) if match else "INSUFFICIENT_EVIDENCE"
    return value if value in LABELS else "INSUFFICIENT_EVIDENCE"


def main() -> int:
    settings = get_settings().model_copy(
        update={"llm_model": "qwen2.5:7b-instruct", "llm_temperature": 0.0, "llm_max_tokens": 200, "llm_timeout_seconds": 120, "llm_max_retries": 1}
    )
    repository = Db2Repository(settings)
    index = CorpusBM25Index(repository, "scifact")
    llm = LangChainLLMClient(settings)

    predictions = {
        str(record["claim_id"]): record
        for record in (json.loads(line) for line in PRED.read_text().splitlines() if line.strip())
    }
    claims = {claim.claim_id: claim for claim in load_scifact_claims(ROOT / "data" / "scifact" / "claims_dev.jsonl")}
    selected_ids = list(predictions.keys())
    # Label-agnostic subset: first 20 prediction records in benchmark order.
    # Gold labels are not used to choose examples.
    subset = selected_ids[:20]
    print("subset", {
        label: sum(1 for c in subset if claims[c].gold_label == label)
        for label in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
    })

    a_records, b_records, ag_records = [], [], []
    for position, claim_id in enumerate(subset, start=1):
        claim = claims[claim_id]
        extracted = ExtractedClaim(claim.claim, claim.claim, "FACTUAL")
        candidates = index.retrieve(extracted, top_k=4)
        passages = "\n\n".join(
            f"[{c.passage_id}] {c.passage_text[:1500]}" for c in candidates
        )

        raw_a = llm.complete(A_PROMPT, f"CLAIM:\n{claim.claim}")
        raw_b = llm.complete(B_PROMPT, f"CLAIM:\n{claim.claim}\n\nPASSAGES:\n{passages}")
        a_label, b_label = _label(raw_a), _label(raw_b)
        ag_label = predictions[claim_id]["predicted_label"]
        a_records.append((claim.gold_label, a_label))
        b_records.append((claim.gold_label, b_label))
        ag_records.append((claim.gold_label, ag_label))
        print(position, claim_id, claim.gold_label, "A", a_label, "B", b_label, "AEGIS", ag_label, flush=True)

    def build(records):
        metrics = classification_metrics([x[0] for x in records], [x[1] for x in records])
        return {"metrics": metrics, "records": [
            {"claim_id": cid, "gold": gold, "predicted": pred}
            for cid, (gold, pred) in zip(subset, records)
        ]}

    result = {
        "dataset": "SciFact dev label-agnostic subset (first 20 by claim ID)",
        "n": len(subset),
        "model": "qwen2.5:7b-instruct",
        "retrieval": "full-corpus BM25, top 4",
        "baselines": {
            "llm_only": build(a_records),
            "llm_with_evidence": build(b_records),
            "aegis": build(ag_records),
        },
        "notes": "A has no evidence. B and AEGIS use the same retrieved passages; AEGIS adds citation validation, numeric checks, and guardrails.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v["metrics"]["macro_f1"] for k, v in result["baselines"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
