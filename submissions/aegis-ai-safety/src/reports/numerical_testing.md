# Numerical Verification Tests

## Scope

The deterministic numerical verifier compares simple literal expressions in a claim
with the passages cited or retrieved. It is an explainable guard, not a statistics
engine.

Automated matrix: `experiments/numerical_test_suite.py`  
Raw results: `reports/numerical_test_results.json`

## Supported behavior — 4/4 passed

| Case | Expected | Actual | Status |
| --- | --- | --- | --- |
| 6 encoder layers vs 8 claimed | conflict | `8 identical layers` vs `6 identical layers` | PASS |
| BLEU 28.4 vs 29.4 | conflict | claimed 28.4, evidence 29.4 | PASS |
| BERT-base 340M vs 110M | entity-aware conflict | 340M for BASE vs evidence 110M for BASE | PASS |
| Percent mismatch | equality? | annotated as percent conflict but **not** used to override | PASS |

The percentage override was deliberately disabled after SciFact testing showed a false
CONTRADICTED result caused by comparing an accuracy percentage with an unrelated
prevalence percentage. Percentages still appear in the numeric explanation, but the
language model retains classification authority for percent contexts.

## Unsupported / limited situations

| Situation | Actual behavior |
| --- | --- |
| 80% → 84% = four percentage points | Values are matched, but the arithmetic relation is not computed. |
| 80% → 84% = 5% relative increase | Values are matched; relative arithmetic is not computed. |
| 0.92 vs 92% | No normalization between decimal and percent; unsupported. |
| Sample size 1,200 vs 12,000 | No “sample size” unit; unsupported. |
| Negative value -5% vs +5% | Sign is not currently parsed; values may match incorrectly. |
| Rounding 0.333 vs 0.33 | Exact comparison only; no tolerance. |
| Encoder six layers vs decoder six layers | Same unit/value matches; entity context is not modeled for layers. |
| Accuracy 80% vs F1 0.75 | Metric names are not bound to numbers; only unit-level comparison. |
| Unrelated 5% contexts | A percent value can be reported as a “match”; it no longer overrides. |
| 1 km vs 1000 m | Units/conversions are not parsed. |

## Assessment

The verifier is useful for explicit value conflicts in BLEU, layers, parameter counts,
times, and storage-size units, but it is not a general numerical reasoning engine. The
following are explicitly **not** supported:

- percentage-point vs relative-change arithmetic;
- decimal/percent normalization;
- rounding tolerance;
- signed numbers;
- unit conversion;
- metric-to-number binding when multiple metrics appear in one passage;
- statistical significance, confidence intervals, and p-values.

These gaps are documented rather than presented as capabilities. Classification for
percent-based claims remains model-driven, with the numeric text shown for review.
