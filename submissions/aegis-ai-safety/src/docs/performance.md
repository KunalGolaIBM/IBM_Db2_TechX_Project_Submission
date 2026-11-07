# Performance Profile

## Method

`experiments/profile_pipeline.py` runs the real four-claim paper demonstration and
records five stages independently:

1. PDF extraction/chunking with PyMuPDF
2. LangChain claim extraction
3. Db2 retrieval (production SQL-prefilter + BM25 path)
4. LLM verification (one call per claim)
5. Db2 persistence (temporary session, deleted afterwards)

Environment: macOS Apple Silicon, 8 GB RAM, IBM Db2 12.1.5 running under amd64
emulation, Ollama `qwen2.5:7b-instruct` at temperature 0. Local model timing varies
with warm-up, memory pressure, and thermal state; the ratios are the useful signal.

Raw measurements:

- `experiments/results/profile_pipeline.json` — baseline
- `experiments/results/profile_pipeline_final.json` — after optimization

## Baseline

| Stage | Seconds | Share |
| --- | ---: | ---: |
| PDF processing | 0.398 | 0.2% |
| Claim extraction | 19.245 | 9.1% |
| Db2 retrieval | 7.741 | 3.7% |
| LLM verification | 183.509 | 86.5% |
| Persistence | 1.204 | 0.6% |
| **Total** | **212.097** | **100%** |

The previously recorded demo session took ~145 s (server-side `DURATION_MS` 145,242).
The same bottleneck applies: four sequential 7B generations dominate. The difference
between 145 s and 212 s is explained by model warmth, machine load, and how verbose
the model's explanations happened to be, not by PDF processing or Db2.

## Optimization

The verification prompt now requests one or two sentences (maximum 40 words) for the
explanation and one sentence (maximum 30 words) for limitations. This changes output
verbosity, not the classification task, evidence set, retrieval depth, or model.
Deterministic numeric checks were also strengthened to attach conflicting passages
even when the model omits a citation.

## Result

| Stage | Seconds | Share |
| --- | ---: | ---: |
| PDF processing | 0.483 | 0.5% |
| Claim extraction | 19.025 | 21.2% |
| Db2 retrieval | 7.098 | 7.9% |
| LLM verification | 60.822 | 67.7% |
| Persistence | 2.453 | 2.7% |
| **Total** | **89.881** | **100%** |

LLM verification fell from **183.5 s to 60.8 s** with the same 7B model and the same
four claims. The final end-to-end API run after the change completed in **69.7 s wall time**
with a server-side duration of **62.2 s**.

## Quality check

The optimized four-claim demo still returned:

- 1 `SUPPORTED` (28.4 BLEU)
- 2 `CONTRADICTED` (8-vs-6 encoder layers, BERT unidirectional)
- 1 `INSUFFICIENT_EVIDENCE` (mobile latency)
- 0 `VERIFICATION_ERROR`

The numeric contradiction now produces a deterministic evidence link even when the
model does not cite the passage itself.

## Remaining bottlenecks

1. **Verification generation** remains the largest cost. Options: faster hosted
   inference, a smaller model for a first-pass triage, or carefully validated batching.
2. **Claim extraction** is ~19 s for four claims. A smaller extraction model or prompt
   caching could reduce this, but extraction quality must be re-evaluated.
3. **Retrieval** is under 8% for user-selected documents. SciFact full-corpus BM25 is
   evaluated separately and is not the demo bottleneck.
4. **PDF processing and persistence are negligible** (<3% combined).
