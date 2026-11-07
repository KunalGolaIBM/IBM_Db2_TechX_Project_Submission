# SciFact Evaluation Analysis

## Dataset and split

- **Dataset:** SciFact release archive (`data.tar.gz`), CC BY-NC 2.0.
- **Archive SHA-256:** `11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be`
- **Corpus:** 5,183 abstracts, imported into Db2 as 9,242 passages.
- **Split:** The official test split has no public evidence labels. The labelled
  **dev** split was used as the held-out set. AEGIS never trained on SciFact.
- **Subset:** **first 100 claims by benchmark claim ID**, selected without consulting
  gold labels. The resulting distribution is 45 SUPPORTED / 20 CONTRADICTED / 35
  INSUFFICIENT_EVIDENCE. The earlier balanced 34/33/33 subset used gold labels for
  selection and is no longer the reported run.
- **Label mapping:** `SUPPORT` → `SUPPORTED`, `CONTRADICT` → `CONTRADICTED`, `NEI` →
  `INSUFFICIENT_EVIDENCE`.

## Pipeline

1. All abstracts imported with `SOURCE_TYPE='scifact'` and `EXTERNAL_ID` = original
   SciFact doc ID.
2. All passages loaded from Db2 once into a full-corpus BM25 index.
3. Top 10 passages retrieved per claim; top 4 passed to the verifier.
4. Gold labels and gold document IDs are used only for scoring/Recall@K; they are
   never given to retrieval or the verifier.
5. Model: local Ollama `qwen2.5:7b-instruct`, temperature 0, max 450 tokens.
6. Guardrails: citation validation, numeric checks, evidence-term overlap,
   missing-evidence abstention, comparability-aware conflict detection, absence/scope/
   citation guards, and a single malformed-JSON retry.

## Results — label-agnostic 100 claims

| Metric | Value |
| --- | ---: |
| Claims evaluated / scored | 100 / 100 |
| Coverage / errors | 1.0 / 0 |
| Accuracy | 0.700 |
| Macro precision | 0.710 |
| Macro recall | 0.675 |
| **Macro F1** | **0.678** |
| SUPPORTED precision / recall / F1 | 0.789 / 0.667 / 0.723 |
| CONTRADICTED precision / recall / F1 | 0.714 / 0.500 / 0.588 |
| INSUFFICIENT precision / recall / F1 | 0.625 / 0.857 / 0.723 |
| Retrieval Recall@1 / @3 / @5 / @10 | 0.55 / 0.67 / 0.76 / 0.77 |
| Mean / median / p95 latency | 36.60 s / 34.83 s / 53.70 s |
| Total measured claim processing | 3,660.5 s |

Confusion matrix (gold rows / predicted columns):

| Gold \ Pred | Supported | Contradicted | Insufficient |
| --- | ---: | ---: | ---: |
| Supported | 30 | 3 | 12 |
| Contradicted | 4 | 10 | 6 |
| Insufficient | 4 | 1 | 30 |

False positives: 5 of 35 NEI claims received a definitive label (4 supported, 1
contradicted). Contradiction recall is still the main weakness; 6/20 contradicted
claims were abstained on.

## Same-claims before/after comparison

The old balanced subset and the new label-agnostic subset overlap on **87 claims**.
Scoring the preserved pre-fix predictions and the final predictions on exactly those 87
claims isolates the code change from the selection change:

| Run on the same 87 claims | Accuracy | Macro F1 | Contradicted F1 | Contradicted recall |
| --- | ---: | ---: | ---: | ---: |
| Pre-fix predictions (balanced selection artifact) | 0.690 | 0.660 | 0.514 | 0.450 |
| **Final predictions** | **0.690** | **0.671** | **0.588** | **0.500** |

Macro F1 rose by 0.011 and contradiction F1 by 0.074 on identical claims; accuracy was
unchanged. Supported recall fell (0.706 → 0.647), so this is a trade-off, not a
uniform improvement. The full 100-claim numbers are not directly comparable to the old
balanced 0.615 macro F1 because the class distribution changed.

## Baseline comparison

Measured on the first 20 label-agnostic claims (8 SUPPORTED / 5 CONTRADICTED / 7
INSUFFICIENT), same model/temperature, top-4 retrieved passages for B and AEGIS.
Source: `reports/scifact_baselines.json`.

| Approach | Evidence | Accuracy | Macro precision | Macro recall | Macro F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| A — LLM only | none | 0.450 | 0.510 | 0.449 | 0.458 |
| B — LLM + retrieved passages | top 4 | 0.700 | 0.813 | 0.650 | 0.623 |
| AEGIS — complete pipeline | top 4 | 0.700 | 0.806 | 0.675 | **0.674** |

A has no access to the source abstracts, so its weaker score measures model memory, not
retrieval. B and AEGIS receive identical retrieved passages; AEGIS adds citation,
numeric, overlap, conflict, absence, scope, and citation guards. AEGIS is 0.051 macro F1
above B on 20 claims and improves contradiction recall (0.40 vs 0.20), but the subset is
far too small for a significance claim. AEGIS's supported recall is lower than B's
(0.625 vs 0.75), reflecting the stricter evidence-link requirements.

## Benchmark integrity

Verified by `experiments/verify_benchmark_integrity.py`; output:
`reports/benchmark_integrity.json`.

- Flipping every gold label does not change subset selection (`selection_ignores_labels`).
- No prediction record contains a gold/label field.
- All 139 cited passage IDs exist in Db2 and belong to a document retrieved for that
  claim (`missing_passages=[]`, `misattributed_passages=[]`).
- Gold labels are joined only after predictions are written.

## Interpretation

- This is development-set performance on a 100-claim subset, not the hidden-label test
  split and not a statistically significant comparison.
- Retrieval Recall@5 = 0.76 and Recall@10 = 0.77 bound classification performance.
- The model remains conservative: NEI recall is 0.857, contradiction recall 0.500.
  Abstaining is preferable to false certainty, but contradiction recall limits
  usefulness for refutation.
- SciFact claims are single sentences over abstracts; AEGIS's production PDF path and
  numeric checks are not fully exercised by this benchmark.
- The guards added for the controlled suite do not fire on this subset: no SciFact
  claim in the first 100 combines a universal marker with the guarded category nouns,
  and none uses an exclusivity claim over those categories.

## Reproducibility

```bash
make scifact-data
python experiments/run_scifact_eval.py --import --limit 100 --fresh \
  --model qwen2.5:7b-instruct --max-tokens 450
python experiments/verify_benchmark_integrity.py
python experiments/run_scifact_baselines.py
```

Outputs: `experiments/predictions/scifact_dev_predictions.jsonl`,
`experiments/results/scifact_dev_metrics.json`,
`experiments/results/scifact_doc_map.json`,
`reports/benchmark_integrity.json`, `reports/scifact_baselines.json`.
Preserved pre-fix artifacts: `reports/scifact_metrics_prefix.json`,
`reports/scifact_predictions_prefix.jsonl`.
