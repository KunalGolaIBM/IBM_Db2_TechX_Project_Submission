#!/usr/bin/env python3
"""Numerical verifier capability matrix.

Records actual behavior for supported and unsupported numerical situations. An
"unsupported" case is not a test failure; it documents a capability gap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.domain import PassageCandidate  # noqa: E402
from app.services.numerical_verifier import check_numerics  # noqa: E402

OUT = ROOT / "reports" / "numerical_test_results.json"


def passage(text: str, pid: int = 1) -> PassageCandidate:
    return PassageCandidate(
        passage_id=pid,
        document_id=1,
        document_title="Test source",
        filename="test.pdf",
        passage_text=text,
        page_number=1,
        passage_index=0,
        retrieval_score=1.0,
    )


CASES = [
    {
        "id": "layers_6_vs_8",
        "capability": "supported",
        "claim": "The encoder consists of 8 identical layers.",
        "evidence": "The encoder is a stack of 6 identical layers.",
        "expected": "conflict",
    },
    {
        "id": "bleu_28.4_vs_29.4",
        "capability": "supported",
        "claim": "The model reaches 28.4 BLEU.",
        "evidence": "The model reaches 29.4 BLEU.",
        "expected": "conflict",
    },
    {
        "id": "bert_base_params",
        "capability": "supported",
        "claim": "BERT-base contains 340 million parameters.",
        "evidence": "BERTBASE has 110M parameters; BERTLARGE has 340M parameters.",
        "expected": "conflict",
    },
    {
        "id": "percent_conflict_not_override",
        "capability": "supported-annotation",
        "claim": "The method improves accuracy by 5%.",
        "evidence": "95% of participants completed the survey.",
        "expected": "percent-annotated-not-override",
    },
    {
        "id": "percentage_points_arithmetic",
        "capability": "unsupported",
        "claim": "80% to 84% is a four-percentage-point improvement.",
        "evidence": "Accuracy increased from 80% to 84%.",
        "expected": "arithmetic",
    },
    {
        "id": "relative_percentage",
        "capability": "unsupported",
        "claim": "80% to 84% is a five percent relative increase.",
        "evidence": "Accuracy increased from 80% to 84%.",
        "expected": "arithmetic",
    },
    {
        "id": "decimal_vs_percent",
        "capability": "unsupported",
        "claim": "The score is 0.92.",
        "evidence": "The score is 92%.",
        "expected": "normalization",
    },
    {
        "id": "sample_sizes",
        "capability": "unsupported",
        "claim": "The sample size is 1,200 participants.",
        "evidence": "The sample size is 12,000 participants.",
        "expected": "count-context",
    },
    {
        "id": "negative_value",
        "capability": "unsupported",
        "claim": "Performance changed by -5%.",
        "evidence": "Performance changed by +5%.",
        "expected": "signed-number",
    },
    {
        "id": "rounding",
        "capability": "unsupported",
        "claim": "The coefficient is 0.333.",
        "evidence": "The coefficient is 0.33.",
        "expected": "rounding-tolerance",
    },
    {
        "id": "encoder_vs_decoder_context",
        "capability": "unsupported",
        "claim": "The encoder has six layers.",
        "evidence": "The decoder has six layers.",
        "expected": "entity-context",
    },
    {
        "id": "unrelated_percent_context",
        "capability": "unsupported",
        "claim": "Accuracy improved by 5%.",
        "evidence": "5% of participants withdrew from the study.",
        "expected": "metric-context",
    },
    {
        "id": "unit_conversion",
        "capability": "unsupported",
        "claim": "The distance is 1 km.",
        "evidence": "The distance is 1000 m.",
        "expected": "unit-conversion",
    },
    {
        "id": "multiple_metrics",
        "capability": "partial",
        "claim": "Accuracy is 80% and F1 is 0.75.",
        "evidence": "Accuracy is 85% and F1 is 0.75.",
        "expected": "metric-binding",
    },
]


def main() -> int:
    rows = []
    for case in CASES:
        result = check_numerics(case["claim"], [passage(case["evidence"])])
        actual = "none" if result is None else "conflict" if result.has_discrepancy else "match"
        if result and result.has_discrepancy and not result.override_eligible:
            actual = "percent-annotated-not-override"
        rows.append(
            {
                **case,
                "actual": actual,
                "summary": result.summary if result else None,
                "discrepancies": result.discrepancies if result else [],
                "matches": result.matches if result else [],
                "override_eligible": result.override_eligible if result else False,
                "behavior_matches_limited_claim": actual == case["expected"],
            }
        )
    supported = [row for row in rows if row["capability"] in ("supported", "supported-annotation")]
    summary = {
        "n": len(rows),
        "supported_cases": len(supported),
        "supported_passed": sum(1 for row in supported if row["behavior_matches_limited_claim"]),
        "unsupported_or_limited": sum(1 for row in rows if row["capability"] in ("unsupported", "partial")),
        "rows": rows,
    }
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
