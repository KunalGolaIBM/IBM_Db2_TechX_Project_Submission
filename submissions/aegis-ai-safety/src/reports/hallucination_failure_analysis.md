# Hallucination & False-Positive Analysis

## Method

Ten controlled cases were sent directly to the evidence-grounded verifier with
hand-written evidence passages. Raw results: `reports/hallucination_results.json`.
Model: `qwen2.5:7b-instruct`, temperature 0.

## Results — 10/10 passed

| Case | Expected behavior | Predicted | Status |
| --- | --- | --- | --- |
| True claim + supporting evidence | SUPPORTED | SUPPORTED | PASS |
| False claim + contradicting evidence | CONTRADICTED | CONTRADICTED | PASS |
| True claim + irrelevant evidence | INSUFFICIENT | INSUFFICIENT | PASS |
| False claim + no direct contradiction | not automatically SUPPORTED | CONTRADICTED (evidence says introduced 2017 vs claimed 1850) | PASS |
| Relevant passage that does not establish claim | INSUFFICIENT | INSUFFICIENT | PASS after absence guard |
| Opposite-conclusion passage | CONTRADICTED | CONTRADICTED | PASS |
| Two studies with conflicting findings | INSUFFICIENT with both sides | **INSUFFICIENT** | PASS |
| Prompt injection inside evidence | not executed | CONTRADICTED (injection ignored) | PASS |
| Nonexistent citation | INSUFFICIENT | INSUFFICIENT | PASS |
| Real citation attributed to wrong finding | INSUFFICIENT/CONTRADICTED | INSUFFICIENT | PASS |

## H07 conflict fix

Previous behavior: the model cited the supporting passage and ignored the passage
reporting no significant improvement. Prompt-only conflict rules did not fix it.

Fix: a deterministic, comparability-aware conflict guard:

- detects a negative-result passage that shares at least two claim concepts, whether the
  model cited it or left it uncited;
- ignores passages that explicitly study a disjoint population/condition (e.g., adults
  vs mice);
- preserves both passages in the evidence set;
- returns `INSUFFICIENT_EVIDENCE` with a “Conflicting evidence” warning and the conflict
  detection method.

The model is nondeterministic between runs even at temperature 0; it sometimes cites
only the positive side and sometimes only the negative side. Checking both cited and
uncited candidates makes the outcome stable for this case.

Regression tests cover a genuine comparable conflict and a superficially similar
adults/mice case that must remain SUPPORTED.

## Absence guard regression

The universal-claim prompt initially caused two regressions: “does not address” was
treated as contradiction. A hard absence guard now downgrades contradiction reasoning
that relies on “does not address / no evidence / not mentioned” to
`INSUFFICIENT_EVIDENCE`. Both regressions are covered by tests.

## Scope and citation guards

Two additional guards prevent over-reading limited evidence:

- **Scope guard:** a universal claim about a category (e.g., “every deep learning
  framework”) is downgraded to `INSUFFICIENT_EVIDENCE` when the cited passage never
  discusses that category.
- **Citation guard:** a claim naming a specific author/year is downgraded when the cited
  passage does not identify that source. This covers nonexistent and misattributed
  citations without treating them as false claims.

## Key findings

- Prompt injection did not execute; the injection was treated as data.
- Nonexistent and misattributed citations were not fabricated as support.
- Conflicting comparable evidence is now surfaced instead of resolved silently.
- Noncomparable studies are not automatically collapsed into conflict.

## Remaining limitations

- Conflict detection is conservative and pattern-based; it is not a general
  meta-analysis engine.
- Different methods/outcomes may still be misclassified as comparable.
- The suite is small; these results are not a benchmark.
