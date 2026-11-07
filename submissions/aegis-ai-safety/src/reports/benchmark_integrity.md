# Benchmark Integrity Audit

Script: `experiments/verify_benchmark_integrity.py`
Output: `reports/benchmark_integrity.json`

Run against the final label-agnostic SciFact predictions
(`experiments/predictions/scifact_dev_predictions.jsonl`) and metrics
(`experiments/results/scifact_dev_metrics.json`).

## Checks and results

| Check | Result |
| --- | --- |
| Subset selection is label-agnostic | PASS — flipping every gold label leaves the 100 selected claim IDs unchanged |
| Predictions contain gold/label fields | PASS — none |
| Predictions records | 100 |
| Cited passage IDs checked | 139 |
| Missing passages | 0 |
| Passages attributed to a document not retrieved for that claim | 0 |
| Evidence attribution | PASS |
| Coverage / verification errors | 1.0 / 0 |

Selection method: first N claims by benchmark claim ID. Gold labels are joined only in
the scoring step. The verifier receives claim text and retrieved passages; it does not
receive gold labels, gold document IDs, or expected evidence.

## Reporting-only gold distribution

| Class | Claims |
| --- | ---: |
| SUPPORTED | 45 |
| CONTRADICTED | 20 |
| INSUFFICIENT_EVIDENCE | 35 |

This distribution is reported after selection for transparency. It is not used to choose
examples.

## Configuration

- Model: `qwen2.5:7b-instruct`, temperature 0, max 450 tokens
- Retrieval: Db2 full-corpus BM25, top 10
- Classification context: top 4 passages
- Dataset: SciFact dev, CC BY-NC 2.0

## Reproduce

```bash
python experiments/run_scifact_eval.py --limit 100 --fresh \
  --model qwen2.5:7b-instruct --max-tokens 450
python experiments/verify_benchmark_integrity.py
```
