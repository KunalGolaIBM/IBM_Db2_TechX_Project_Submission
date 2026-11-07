# Experiments — SciFact Evaluation

Reproducible SciFact evaluation for AEGIS. The adapter, Db2 import, retrieval
evaluation, verifier predictions, and metrics are implemented. The latest measured run
is stored under `experiments/results/`.

## Dataset: SciFact

- **Source:** https://github.com/allenai/scifact and
  https://huggingface.co/datasets/allenai/scifact
- **Archive:** https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz
- **License:** **CC BY-NC 2.0** (https://creativecommons.org/licenses/by-nc/2.0/).
  The dataset is not redistributed and must not be used commercially.
- **Corpus:** 5,183 abstracts.
- **Splits:** 1,261 train / 300 dev / 300 test claims in this release.
- **Evaluation split:** the official **test** split does not publish evidence labels,
  so the **dev** split (300 labelled claims) is used as the held-out labelled set.
  AEGIS never trains on SciFact.
- **Labels:** `SUPPORT` → `SUPPORTED`, `CONTRADICT` → `CONTRADICTED`, `NEI` →
  `INSUFFICIENT_EVIDENCE`.

Manifest: [`scifact_manifest.json`](scifact_manifest.json).

## Files

| File | Purpose |
| --- | --- |
| `scifact_loader.py` | Load corpus and claim JSONL/JSON; derive labels and cited docs |
| `scifact_adapter.py` | Convert abstracts into Db2 documents with external IDs |
| `retrieval_eval.py` | Full-corpus BM25 index loaded from Db2 |
| `run_scifact_eval.py` | Import, retrieve, verify, checkpoint predictions, compute metrics |
| `metrics.py` | Macro F1, per-class precision/recall, confusion matrix, FP analysis, Recall@K, latency |
| `benchmark.py` | Alias entry point for metrics from an existing predictions file |
| `evaluate.py` | Metrics CLI |
| `profile_pipeline.py` | Per-stage pipeline profiling |
| `tests/test_metrics.py` | Metric unit tests |

## Run the evaluation

```bash
make scifact-data          # downloads SciFact separately (license: CC BY-NC 2.0)
python experiments/run_scifact_eval.py --import --limit 100 --model qwen2.5:7b-instruct
```

The runner:

1. imports all 5,183 abstracts into Db2 (`source_type='scifact'`, external IDs preserved);
2. loads dataset passages from Db2 and builds a full-corpus BM25 index;
3. retrieves top-10 passages per claim without using gold labels;
4. passes only the claim and top 4 retrieved passages to the verifier;
5. writes predictions incrementally (resumable);
6. scores macro F1, per-class precision/recall, confusion matrix, false positives,
   retrieval Recall@1/5/10, and latency.

`--limit 0` evaluates all 300 labelled dev claims. A nonzero limit selects the first N
claims by benchmark claim ID. Selection never consults gold labels; labels are used only
for scoring. Report the subset size explicitly and do not present subset results as
full-split results.

### Prediction format

JSONL records include:

```json
{"claim_id":"3","predicted_label":"SUPPORTED","retrieved_doc_ids":[123],
 "evidence_passage_ids":[45],"retrieval_ms":170.2,"verification_ms":41000,
 "latency_ms":41170.2,"numerical_analysis":null}
```

Gold labels are stored only in the evaluation split and are joined at scoring time;
they are never passed to retrieval or the verifier.

## Latest results

Measured on 2026-11-06 with local `qwen2.5:7b-instruct`, the first 100 claims by
benchmark claim ID (selected without gold labels; 45/20/35), full-corpus Db2-backed
BM25, top-4 passages for the verifier:

| Metric | Value |
| --- | ---: |
| Macro F1 | 0.678 |
| Accuracy | 0.700 |
| SUPPORTED P / R / F1 | 0.789 / 0.667 / 0.723 |
| CONTRADICTED P / R / F1 | 0.714 / 0.500 / 0.588 |
| INSUFFICIENT P / R / F1 | 0.625 / 0.857 / 0.723 |
| Recall@1 / @5 / @10 | 0.55 / 0.76 / 0.77 |
| Mean / median / p95 latency | 36.6 s / 34.8 s / 53.7 s |
| Errors / coverage | 0 / 1.0 |

Results: [`results/scifact_dev_metrics.json`](results/scifact_dev_metrics.json).
Predictions: [`predictions/scifact_dev_predictions.jsonl`](predictions/scifact_dev_predictions.jsonl).
Document map: [`results/scifact_doc_map.json`](results/scifact_doc_map.json).
Integrity audit: `../reports/benchmark_integrity.json`.
Import: 5,183 abstracts → 9,242 passages in 15.45 s.

The test split has no public evidence labels; the dev split is the held-out labelled
set. This is a subset, not the full 300 claims, and not a claim of statistical
significance. The 20-claim baseline comparison is in `../reports/scifact_baselines.json`.

## Performance

`python experiments/profile_pipeline.py` records PDF processing, claim extraction, Db2
retrieval, LLM verification, and persistence separately. See
[`docs/performance.md`](../docs/performance.md).

## Separation from the demo

`data/samples/` contains a fictional SolarCell-X demo and a synthetic paper-demo
summary. Those outcomes are not SciFact performance and must never be presented as
such.
