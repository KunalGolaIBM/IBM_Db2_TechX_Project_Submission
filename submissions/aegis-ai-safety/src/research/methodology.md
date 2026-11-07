# Methodology

## System under evaluation

Pipeline stages:

1. **Ingest** — user research text and evidence documents (PDF/TXT/MD), chunked into
   passages and stored in Db2 with page/index provenance.
2. **Extraction** — LangChain/LLM extracts atomic claims with `original_claim`,
   `normalized_claim`, `claim_type`, and source spans where locatable.
3. **Retrieval** — Db2 lexical candidates (document-filtered `LIKE` prefilter), BM25
   ranking, top-K passages.
4. **Verification** — LangChain/LLM returns a classification, explanation,
   limitations, and cited passage IDs.
5. **Validation** — citations not present in the candidate set are discarded;
   definitive labels without a valid citation are downgraded to
   `INSUFFICIENT_EVIDENCE`.
6. **Persistence** — session, claims, results, evidence links, status, and provider
   label are written transactionally to Db2.

## Labels

| AEGIS | SciFact | Meaning |
| --- | --- | --- |
| `SUPPORTED` | SUPPORT | Evidence explicitly entails the claim |
| `CONTRADICTED` | CONTRADICT | Evidence explicitly conflicts |
| `INSUFFICIENT_EVIDENCE` | NEI | Evidence does not establish either way |
| `VERIFICATION_ERROR` | — | Operational failure, not a gold label |

NEI is mapped to insufficient evidence. A `VERIFICATION_ERROR` is excluded from
benchmark scoring and reported separately.

## Dataset

**SciFact** (Wadden et al., EMNLP 2020), 1,261 train / 450 validation / 300 test
claims, 5,183 corpus abstracts. License **CC BY-NC 2.0**; not redistributed here.
Download from the official repository or HuggingFace and record the revision.

## Metrics

- Macro F1 across SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE.
- Per-class precision, recall, F1, and support.
- Confusion matrix.
- False-positive analysis: definitive predictions on NEI claims.
- Retrieval Recall@1, Recall@5, Recall@10 using `cited_doc_ids`.
- Mean, median, and p95 verification latency.
- Invalid/fabricated citation rate (validator ablations).

## Baselines

1. **LLM without retrieval** — allowed to answer from parametric memory; expected to
   violate the evidence requirement.
2. **Retrieval only** — lexical similarity threshold; no judgment.
3. **AEGIS** — retrieval + grounded judgment + citation validation.

## Ablations

- Remove the citation validator.
- Replace BM25 with dense or hybrid retrieval.
- Vary K (1, 3, 5, 10).
- Vary model size/provider.
- Batched vs per-claim verification.

## Error analysis

Stratify failures by:

- numerical claims (unit/percentage mismatch);
- comparative and causal claims;
- paraphrase-heavy claims with low lexical overlap;
- multi-sentence evidence;
- claims whose evidence is absent from the supplied corpus;
- malformed model JSON.

## Numeric verification

A deterministic checker compares simple literal numeric expressions in a claim with
the passages the model cited. It covers percentages, BLEU, parameter counts, layer and
head counts, GPUs, days, and word counts. A clear conflict can override an inconsistent
model judgment; "not found" is never treated as contradiction. The checker does not
handle tables, equations, units, confidence intervals, or advanced statistics.

## Reporting and reproducibility

Each session stores claim/result/evidence provenance, relationship labels, numeric
analysis, model label, timestamps, and duration. JSON and Markdown reports can be
exported from the API/UI. Synthetic/paper demo outcomes are reported separately from
SciFact metrics; the evaluation view is empty until a real metrics file exists.

## Reproducibility requirements

- Record dataset revision and license acceptance.
- Record provider, model label, temperature, prompt version, top-K, and retrieval
  backend with every session.
- Keep synthetic demonstrations separate from benchmark runs.
- Report actual measured values only; never fabricate scores.
- Store per-claim outputs for re-scoring.

## Current status

The evaluation harness and manifest are implemented. **No SciFact run has been
executed**, so no benchmark result is reported. Synthetic demo outcomes are not
benchmark evidence.
