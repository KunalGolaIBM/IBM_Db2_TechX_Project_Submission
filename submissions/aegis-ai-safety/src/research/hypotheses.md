# Hypotheses

These are research hypotheses to test. No hypothesis is confirmed by the synthetic
demo, and no benchmark has been executed.

## H1 — Evidence-linked verification reduces unwarranted acceptance

If a definitive `SUPPORTED` label requires a validated retrieved passage, then
researchers reviewing AI-generated claims will accept fewer unsupported statements than
when reading the text without a verification aid.

**Test:** controlled user study with claim-level tasks; measure unsupported-claim
acceptance and time-to-judgment with and without AEGIS.

## H2 — Lexical retrieval recall bounds verification coverage

Verification can only be as good as the retrieved evidence. Lexical BM25 with document
filters will have lower Recall@K than a strong dense retriever on paraphrase-heavy
SciFact claims, and this gap will translate into more `INSUFFICIENT_EVIDENCE` outcomes.

**Test:** compare BM25, dense, and hybrid retrieval at K = 1, 5, 10 on SciFact; measure
downstream macro F1 with the same verifier.

## H3 — Evidence guardrails reduce fabricated citations

Post-validating cited passage IDs and downgrading definitive classifications without a
valid citation will reduce fabricated-evidence rates without materially reducing
supported-claim recall.

**Test:** ablate the validator on model outputs; measure invalid-citation rate,
macro F1, and the supported/insufficient confusion.

## H4 — Model scale affects calibration more than retrieval

Larger instruction-tuned models will improve explanation quality and classification
F1, but retrieval quality will remain the dominant constraint on `SUPPORTED` recall for
claims whose evidence is not lexically similar.

**Test:** factorial comparison of model sizes (small local vs hosted) × retrieval
backends, with fixed prompts and evidence.

## H5 — Latency vs verify-all claims

Verifying every claim with one LLM call per claim scales linearly and may be
unacceptable for long documents. Candidate pruning or batching should reduce latency
without a significant macro-F1 loss.

**Test:** measure latency percentiles and F1 for per-claim, batched, and
retrieval-thresholded strategies.

## Non-hypotheses

- AEGIS cannot determine objective truth.
- AEGIS does not assume that a high retrieval score implies support.
- AEGIS does not treat missing evidence as a negative label.
