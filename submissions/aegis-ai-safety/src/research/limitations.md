# Research Limitations

## Construct validity

- AEGIS measures whether a claim is supported by a supplied evidence corpus, not
  whether it is objectively true.
- `SUPPORTED` means the model found a passage it judged as entailment, plus a valid
  citation. It is not a formal proof.
- `INSUFFICIENT_EVIDENCE` can reflect retrieval failure, missing documents, weak
  model reasoning, or genuine gaps in the literature.

## Retrieval

- The initial retriever is lexical BM25 over Db2 passages. Paraphrase-heavy claims and
  synonym mismatches are likely to be under-retrieved.
- Vector/hybrid retrieval is future work. Embedding similarity alone must not be
  treated as factual support.
- The SQL prefilter caps candidates and uses `LIKE`; very large corpora need a better
  index or native Db2 text/vector search.

## Model dependence

- Classification quality depends on the configured provider and model.
- Small local models can produce terse explanations, malformed JSON, or inconsistent
  judgments. The pipeline retries explanation prose and rejects invalid citations, but
  it does not make a weak model reliable.
- Prompt changes can change both accuracy and abstention behavior. Prompt versions
  should be recorded with evaluation runs.

## Numerical checks

- The deterministic checker covers only simple literal expressions: percentages,
  BLEU, parameter counts, layer/head/GPU/day/word counts.
- It does not parse tables, equations, confidence intervals, p-values, units, or
  advanced statistics.
- A numeric conflict is treated as contradiction only when the cited evidence supplies
  a different value for the same simple quantity and no cited value matches. This
  rule is intentionally narrow; it can still be wrong if entity context is ambiguous.

## Dataset and benchmark

- SciFact is CC BY-NC 2.0 and is not bundled. It is a claim-verification benchmark,
  not a direct test of AEGIS's PDF extraction, retrieval over user documents, or
  numerical checks.
- SciFact labels are SUPPORT / CONTRADICT / NEI; mapping NEI to
  `INSUFFICIENT_EVIDENCE` is an explicit design choice.
- No SciFact run has been executed. No benchmark scores are reported.

## Human factors

- The interface is designed for researcher review but has not undergone a controlled
  user study.
- Human-review status is stored but there is no review workflow or inter-annotator
  agreement analysis yet.

## Generalization

- Prompts and tokenization are English-centric.
- The demo uses two ML papers; performance on other domains, paper layouts, or
  non-English sources is unknown.
- Scanned PDFs require OCR, which is not implemented.
