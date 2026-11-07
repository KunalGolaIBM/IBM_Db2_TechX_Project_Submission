# Research Questions

AEGIS investigates whether claim-level, evidence-linked verification can make
AI-generated research text easier to audit without overstating certainty.

## RQ1 — Evidence grounding

Can an LLM verifier that is restricted to retrieved passages produce claim-level
judgments with a measurable reduction in unsupported definitive labels compared with
an unconstrained LLM baseline?

## RQ2 — Retrieval sufficiency

How much does lexical retrieval quality limit downstream verification? Specifically,
how does BM25 Recall@K on SciFact relate to `SUPPORTED` recall and
`INSUFFICIENT_EVIDENCE` rates?

## RQ3 — Citation validation

Do post-hoc validation of cited passage IDs and the mandatory-evidence guardrail
reduce fabricated citations, and at what cost to supported-claim recall?

## RQ4 — Numerical consistency

Can deterministic numeric comparisons catch simple value conflicts (layers, heads,
percentages, parameter counts, BLEU) that a model either misses or explains
inconsistently, without introducing false contradictions?

## RQ5 — Review efficiency

Does the claim-level evidence inspector reduce the time researchers need to assess an
AI-generated summary, compared with reading the source PDFs unaided?

## RQ6 — Model dependence

How do classification accuracy and explanation quality vary between a small local
model and a larger hosted model under identical prompts, retrieval, and guardrails?

## Measurement principles

- Separate retrieval evaluation from classification evaluation.
- Report macro F1 and per-class precision/recall, not only accuracy.
- Report abstention (`INSUFFICIENT_EVIDENCE`) explicitly.
- Treat `VERIFICATION_ERROR` as an operational outcome, not a gold label.
- Never use SciFact labels as inputs to the verifier.
- Do not claim statistical significance from an inadequately sized sample.
