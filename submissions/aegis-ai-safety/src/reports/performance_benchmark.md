# Performance Benchmark

## Environment

- macOS Apple Silicon, 8 GB RAM
- Python 3.11.9, FastAPI 0.162.0
- IBM Db2 12.1.5 under amd64 emulation
- Ollama `qwen2.5:7b-instruct`, temperature 0
- 4-claim real-paper demo; three papers for broader tests

## Stage profile — four-claim demo

Measured with `experiments/profile_pipeline.py`. Raw:
`experiments/results/profile_pipeline.json` (baseline) and
`experiments/results/profile_pipeline_final.json` (optimized).

| Stage | Baseline | Optimized |
| --- | ---: | ---: |
| PDF extraction/chunking | 0.398 s | 0.483 s |
| Claim extraction | 19.245 s | 19.025 s |
| Db2 retrieval | 7.741 s | 7.098 s |
| **LLM verification** | **183.509 s** | **60.822 s** |
| Persistence | 1.204 s | 2.453 s |
| **Total** | **212.097 s** | **89.881 s** |

The earlier demonstration recorded 145 s server-side. The 212 s profile was slower
because of model warmth/load and verbose explanations; the bottleneck was the same:
sequential 7B generation per claim.

## Detailed sub-stage measurements

For the 26-page LoRA PDF (91 passages):

| Sub-stage | Time |
| --- | ---: |
| PyMuPDF page text extraction | 0.414 s |
| Passage segmentation/offsets | 0.007 s |
| Db2 document + 91 passage insertion | 4.341 s |

For the SciFact corpus (5,183 abstracts → 9,242 passages) the one-time Db2 import
took **15.45 s**.

## API and evaluation

- Final four-claim API run: **69.7 s wall**, **62.2 s server-side**.
- SciFact 100-claim evaluation: mean **24.93 s/claim**, median **22.36 s**, p95
  **43.61 s**; total measured claim processing **2,499.9 s** plus index load.
- Controlled 40-case suite: mean **26.38 s/claim**, total **1,055 s**.
- Retrieval averages **284 ms/claim** on SciFact and **2.56 ms** on the small
  controlled paper set; the model dominates.

## Why the demonstration was slow

1. One sequential 7B generation per claim.
2. Verbose explanation/limitation output increased generation tokens.
3. Local 7B inference on an 8 GB machine is memory-bandwidth-bound; embeddings and
   retrieval were not the bottleneck.
4. PDF parsing, segmentation, Db2 persistence, and API serialization were each under
   3% of the four-claim runtime.

## Optimization and quality

The model, evidence depth, and classification task were unchanged. The explanation was
constrained to short output, and the deterministic numeric checks were strengthened.
The four-claim demo remained **1 SUPPORTED / 2 CONTRADICTED / 1 INSUFFICIENT**, with no
errors; the 8-vs-6 layer conflict is now deterministically linked.

## Not measured reliably

- CPU utilization of the Ollama runner: process sampling while the Python client was
  blocked showed no useful signal; the runner runs outside the API process.
- RSS memory of the model runner: not available through the Python process.
- Cold model-loading overhead: the model was kept warm between runs; cold-start variance
  is visible in the 145 s vs 212 s observations but was not isolated.
- Concurrent verification throughput: not tested; one request at a time.
- Network/API response generation beyond the wall-vs-server difference.

These gaps are reported rather than estimated.
