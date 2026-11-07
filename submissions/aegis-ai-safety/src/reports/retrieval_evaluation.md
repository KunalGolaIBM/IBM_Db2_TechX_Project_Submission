# Retrieval Quality Evaluation

## Method

Retrieval was evaluated separately from classification. No labels were used as
retrieval filters.

- **Controlled suite:** 30 claims with a documented gold paper among the three uploaded
  papers (supported, contradicted, and numerical cases). The ten insufficient-evidence
  cases have no gold paper and are excluded from paper-level recall.
- **SciFact:** first 100 claims by benchmark ID (label-agnostic); gold
  `cited_doc_ids` mapped to internal Db2 document IDs; predictions from the completed
  run.
- Retrieval uses full-corpus BM25 over passages loaded from Db2. The production API
  uses a document-filtered SQL prefilter + BM25 for user-selected documents.

Raw data: `reports/retrieval_quality.json`

## Controlled 30-case result

| Metric | Result |
| --- | ---: |
| Recall@1 | 0.800 (24/30) |
| Recall@3 | 0.967 (29/30) |
| Recall@5 | 0.967 (29/30) |
| Mean latency | 2.56 ms |
| Min / max latency | 1.42 / 3.98 ms |

Top-1 misses/wrong-paper cases: 6. Most misses still had the correct paper in the
top 3 (C01, C02, N03, N04, N07). C10 (a BERT convolutional-network claim) did not
retrieve the BERT paper in the top 5—the expected paper was a BERT paper, but the
claim wording is dominated by “convolutional neural network.”

## SciFact 100-claim result

| Metric | Result |
| --- | ---: |
| Recall@1 | 0.550 |
| Recall@3 | 0.670 |
| Recall@5 | 0.760 |
| Recall@10 | 0.770 |
| Mean retrieval latency | 153.6 ms |

Retrieval is the practical ceiling: 23% of claims do not have a gold document in the
top 10, and only 55% have it at rank 1.

## False matches and observations

- The controlled suite shows exact wording and closely related terminology retrieve
  well; the BERT convolution claim is a clear terminology mismatch.
- SciFact abstracts contain paraphrases and synonyms that reduce lexical recall.
- No native Db2 vector retrieval is implemented. No external vector database was
  substituted. The loading interface and full-corpus BM25 index keep the path open for
  a future Db2 vector backend.
- The production SQL prefilter was not benchmarked as a separate retrieval mode in this
  run; the evaluation index loads all dataset passages from Db2 and ranks in memory.

## Recommendation

Before optimizing retrieval, preserve the measured BM25 baseline. The next credible
step is a Db2-native vector or hybrid retriever tested on the same claim set, with
Recall@1/3/5 and false-match analysis reported separately.
