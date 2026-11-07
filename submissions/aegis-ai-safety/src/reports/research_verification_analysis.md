# Real-Paper Verification Analysis

## Test set

40 controlled claims over three real arXiv papers:

- *Attention Is All You Need* (arXiv 1706.03762)
- *BERT* (arXiv 1810.04805)
- *LoRA* (arXiv 2106.09685)

The PDFs were parsed with PyMuPDF, stored in IBM Db2 with page provenance, and used as
the evidence corpus. Fixture: `tests/fixtures/research_claims.json`.

| Category | Cases |
| --- | ---: |
| Supported | 10 |
| Contradicted | 10 |
| Insufficient evidence | 10 |
| Numerical (supported and contradicted) | 10 |
| **Total** | **40** |

Claims are already atomic in the fixture, so this suite isolates retrieval, evidence
grounding, numeric checks, and attribution. Claim extraction is tested separately by the
application and API tests. Expected labels are stored only for scoring.

## Results

All four runs below use the same 40 cases, model (`qwen2.5:7b-instruct`, temperature 0),
and scoring. None hides or replaces a failing case.

| Run | Correct | Accuracy | Errors | Mean latency |
| --- | ---: | ---: | ---: | ---: |
| Baseline (before fixes) | 33/40 | 82.5% | 0 | 26.4 s |
| After QA guardrails (C08/C09 still missing) | 38/40 | 95.0% | 0 | 21.1 s |
| After C02/C04 fix (C10 missed once) | 39/40 | 97.5% | 0 | 26.1 s |
| After conflict/citation guards | 40/40 | 100.0% | 0 | 25.4 s |
| **Final (this report)** | **40/40** | **100%** | **0** | **22.4 s** |

Final category results:

| Category | Correct | Accuracy |
| --- | --- | --- |
| Supported | 10/10 | 100% |
| Contradicted | 10/10 | 100% |
| Insufficient | 10/10 | 100% |
| Numerical | 10/10 | 100% |

Total processing time: **894.7 s** for 40 cases. Artifacts:
`reports/research_verification_results.csv`,
`reports/research_verification_summary.json`.
Retained intermediate runs: `..._baseline.csv`, `..._postfix1.*`, `..._postfix4.*`.

## Fixes validated by the suite

1. **C08 / C09 missed contradictions:** retrieval now expands claim synonyms
   (`scratch → fine-tune/pre-train`, `store/copy → checkpoint/storage/weights`) so the
   specific abstract statements enter the top-4 context. The universal-claim prompt rule
   and an exclusivity guard provide a second path when the model abstains.
2. **C02 / C04 regressions:** retrieval expansion covers `convolutional ↔ convolutions`
   and `objective(s)`; the prompt now distinguishes an exclusivity claim from a
   universal requirement. An exclusivity guard resolves an abstention when a passage
   explicitly adds another member of the exclusive category.
3. **H07 conflicting evidence:** a comparability-aware conflict guard preserves both
   passages and returns `INSUFFICIENT_EVIDENCE` with a conflicting-evidence warning.
4. **Absence is not contradiction:** contradictions inferred from “does not address /
   mention / discuss” are downgraded to `INSUFFICIENT_EVIDENCE`.
5. **Scope guard:** universal claims about a category the cited passage never discusses
   (e.g., “every deep learning framework”) are abstained on instead of forced to
   `CONTRADICTED`.
6. **Citation guard:** a claim citing a specific author/year is abstained on when the
   cited passage does not identify that source.
7. **Malformed JSON:** local-model responses with unescaped quotes are repaired, and
   one parse retry is attempted before declaring `VERIFICATION_ERROR`.
8. **Earlier QA fixes retained:** boilerplate/relevance guard, entity-aware numeric
   matching, `times`/GB-MB units, percent-override safety, Db2 injected settings.

## Artifacts

- Baseline CSV: `reports/research_verification_results_baseline.csv`
- Intermediate CSVs: `reports/research_verification_results_postfix1.csv`,
  `reports/research_verification_results_postfix4.csv`
- Final CSV: `reports/research_verification_results.csv`
- Final summary: `reports/research_verification_summary.json`

## Interpretation

The controlled suite is not a representative scientific benchmark and is not used to
claim general accuracy. It demonstrates:

- explicit support, contradiction, insufficient evidence, and numeric checks;
- that the specific C08/C09 and C02/C04 failures found in review now pass reproducibly
  across repeated runs;
- that guards abstain rather than force either support or contradiction when the
  evidence is absent, noncomparable, or about a different scope.

The guards are conservative, pattern-based safety checks, not a general entailment
engine. Their failure modes are documented in
`reports/hallucination_failure_analysis.md` and `docs/limitations.md`.
