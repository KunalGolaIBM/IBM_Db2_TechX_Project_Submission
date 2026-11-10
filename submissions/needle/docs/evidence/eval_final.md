# NEEDLE retrieval evaluation: final canonical run

**CANONICAL run `20261110T024304Z`** (eval/results/20261110T024304Z.json). Supersedes: `20261110T022457Z`.

## Configuration (from the run JSON)

- Session user: `NDL_SENIOR`; RCAC active: ADV_AFFECTED=yes, ADV_ALIAS=yes, ADV_DOC=yes, CORPUS_STATS=no, POSTING=yes, TERM_DF=no
- Rows visible to the user in NEEDLE.ADV_DOC: 26210; embargoed rows visible: 27
- TRIAGE depth from the RCAC router: 50 (approx-index; router APPROX 50; visible 26210/26210). Depth that answered, TRIAGE: {'50': 449, '128': 1}; BM25 (KW): {'50': 450}
- Db2: [['DB2 v12.1.5.0', 'special_85816']] (server_info ['DB2/LINUXX8664', '12.01.0500'])
- k = 10; queries: named n=150 sha256 `afe33c07bf506c5553763fb2a119cfaf376809483f681ac4fff277fdc83ee8fb`, masked n=150 sha256 `412cf5e0630e37bd155d7156a218be054a06d51a15dfa7e589280a61623e610b`, paraphrase n=150 sha256 `f6e25b109378809f0203d52e8824d4d6c7bae7a3d81443ee2e5478f4f811e3dc`
- Dataset data/docs.jsonl sha256 `b66b2af561c75e0432b9c5dcb36f7f430f5ee51201ae0961cf8610d7786ea127`; slices built from the same docs: True
- Query embeddings: nomic-embed-text digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`, prefix `search_query: `, vectors file `eval_qvecs.json.gz` sha256 `f8cfb9098eb1f2ab951d8549bbe7a4c4ddd23cd1a37fcb79780b86f346bf4328` (embedding p50/p95 12.0/13.8 ms on the PC)
- Client: codespace-localhost (python 3.14.2); eval code sha256 `b643b249fdaacba5a7533079b62a7a50605a4b12902fe32fa5c3e244292bf5b8`
- EXPLAIN (vector index ADV_DOC_VIX in plan): exact=False, approx=True. Note: EXPLAIN as the eval user failed (ibm_db_dbi::ProgrammingError: Statement Execute Failed: [IBM][CLI Driver][DB2/LINUXX8664] SQL0551N  The statement failed because the authorization ID does not h); explained as db2inst1 (same statement text; the RCAC row permission applies to every user, so the plan carries the same predicate)
- Queries whose ground truth includes an embargoed advisory: 0 (only-embargoed ground truth: 0)
- Gate: triage named recall@10 = 0.9933 (min 0.8) -> passed

## Relevance (ground truth = all adv_ids sharing the query's canon_id)

recall@k = share of queries with at least one correct advisory in the top k. MRR@10 = mean 1/rank of the first correct advisory. Latency = one retrieval call inside the codespace over localhost:50000, query embedding excluded.

| Retriever | Slice | n | R@1 | R@3 | R@10 | MRR@10 | p50 ms | p95 ms | errors |
|---|---|---|---|---|---|---|---|---|---|
| Hybrid TRIAGE (router depth) | named | 150 | 0.940 | 0.987 | 0.993 | 0.964 | 36.8 | 63.3 | 0 |
| Hybrid TRIAGE (router depth) | masked | 150 | 0.993 | 1.000 | 1.000 | 0.997 | 90.3 | 134.0 | 0 |
| Hybrid TRIAGE (router depth) | paraphrase | 150 | 0.227 | 0.360 | 0.453 | 0.295 | 52.4 | 86.7 | 0 |
| BM25 only (TRIAGE_MODE KW) | named | 150 | 0.933 | 0.980 | 0.993 | 0.955 | 29.9 | 52.4 | 0 |
| BM25 only (TRIAGE_MODE KW) | masked | 150 | 1.000 | 1.000 | 1.000 | 1.000 | 74.5 | 108.6 | 0 |
| BM25 only (TRIAGE_MODE KW) | paraphrase | 150 | 0.213 | 0.233 | 0.340 | 0.241 | 42.9 | 75.6 | 0 |
| Vector APPROX (FETCH APPROX FIRST 10) | named | 150 | 0.940 | 0.980 | 0.993 | 0.960 | 3.0 | 4.2 | 0 |
| Vector APPROX (FETCH APPROX FIRST 10) | masked | 150 | 0.960 | 0.987 | 0.993 | 0.972 | 2.9 | 3.8 | 0 |
| Vector APPROX (FETCH APPROX FIRST 10) | paraphrase | 150 | 0.180 | 0.253 | 0.360 | 0.225 | 2.7 | 3.3 | 0 |
| Vector EXACT | named | 150 | 0.940 | 0.980 | 0.993 | 0.960 | 73.2 | 76.6 | 0 |
| Vector EXACT | masked | 150 | 0.967 | 0.993 | 1.000 | 0.979 | 73.3 | 75.5 | 0 |
| Vector EXACT | paraphrase | 150 | 0.180 | 0.267 | 0.367 | 0.230 | 72.9 | 76.4 | 0 |

## ANN fidelity (a different metric family: APPROX top-10 vs EXACT top-10, same vector, same user)

| Pair | Slice | n | mean overlap@10 | min | identical lists |
|---|---|---|---|---|---|
| approx_vs_exact | all | 450 | 0.97 | 0.1 | 0.8378 |
| approx_vs_exact | named | 150 | 0.9873 | 0.8 | 0.9133 |
| approx_vs_exact | masked | 150 | 0.9787 | 0.2 | 0.88 |
| approx_vs_exact | paraphrase | 150 | 0.944 | 0.1 | 0.72 |

## Change vs run `20261110T022457Z` (previous canonical: NDL_SENIOR, RCAC active, router depth, BM25_SEARCH before the per-term LATERAL rewrite)

| Retriever | Slice | R@1 pre -> final | R@3 pre -> final | R@10 pre -> final | MRR pre -> final | identical top-10 lists | p50 ms pre -> final | p95 ms pre -> final |
|---|---|---|---|---|---|---|---|---|
| Hybrid TRIAGE (router depth) | named | 0.940 -> 0.940 | 0.987 -> 0.987 | 0.993 -> 0.993 | 0.964 -> 0.964 | 150/150 | 261.2 -> 36.8 | 325.6 -> 63.3 |
| Hybrid TRIAGE (router depth) | masked | 0.993 -> 0.993 | 1.000 -> 1.000 | 1.000 -> 1.000 | 0.997 -> 0.997 | 150/150 | 307.4 -> 90.3 | 379.0 -> 134.0 |
| Hybrid TRIAGE (router depth) | paraphrase | 0.227 -> 0.227 | 0.360 -> 0.360 | 0.453 -> 0.453 | 0.295 -> 0.295 | 150/150 | 280.9 -> 52.4 | 399.8 -> 86.7 |
| BM25 only (TRIAGE_MODE KW) | named | 0.933 -> 0.933 | 0.980 -> 0.980 | 0.993 -> 0.993 | 0.955 -> 0.955 | 150/150 | 244.2 -> 29.9 | 291.6 -> 52.4 |
| BM25 only (TRIAGE_MODE KW) | masked | 1.000 -> 1.000 | 1.000 -> 1.000 | 1.000 -> 1.000 | 1.000 -> 1.000 | 150/150 | 277.7 -> 74.5 | 339.9 -> 108.6 |
| BM25 only (TRIAGE_MODE KW) | paraphrase | 0.213 -> 0.213 | 0.233 -> 0.233 | 0.340 -> 0.340 | 0.241 -> 0.241 | 150/150 | 273.9 -> 42.9 | 411.5 -> 75.6 |
| Vector APPROX (FETCH APPROX FIRST 10) | named | 0.940 -> 0.940 | 0.980 -> 0.980 | 0.993 -> 0.993 | 0.960 -> 0.960 | 150/150 | 2.8 -> 3.0 | 4.5 -> 4.2 |
| Vector APPROX (FETCH APPROX FIRST 10) | masked | 0.960 -> 0.960 | 0.987 -> 0.987 | 0.993 -> 0.993 | 0.972 -> 0.972 | 150/150 | 2.8 -> 2.9 | 3.2 -> 3.8 |
| Vector APPROX (FETCH APPROX FIRST 10) | paraphrase | 0.180 -> 0.180 | 0.253 -> 0.253 | 0.360 -> 0.360 | 0.225 -> 0.225 | 150/150 | 3.0 -> 2.7 | 5.8 -> 3.3 |
| Vector EXACT | named | 0.940 -> 0.940 | 0.980 -> 0.980 | 0.993 -> 0.993 | 0.960 -> 0.960 | 150/150 | 73.6 -> 73.2 | 78.7 -> 76.6 |
| Vector EXACT | masked | 0.967 -> 0.967 | 0.993 -> 0.993 | 1.000 -> 1.000 | 0.979 -> 0.979 | 150/150 | 73.9 -> 73.3 | 85.5 -> 75.5 |
| Vector EXACT | paraphrase | 0.180 -> 0.180 | 0.267 -> 0.267 | 0.367 -> 0.367 | 0.230 -> 0.230 | 150/150 | 80.3 -> 72.9 | 90.0 -> 76.4 |

**Changes vs `20261110T022457Z` (BM25_SEARCH per-term LATERAL rewrite, tie-break = score rounded to 9 decimals
+ ADV_ID).** Relevance did not change. All four retrievers return identical top-10 lists for 150/150 queries in
every slice, so every R@1/R@3/R@10/MRR@10 value is identical; the new tie-break reordered no top-10 list in this
query set. Latency (p50 per slice, client inside the codespace): BM25 only fell from 244.2-277.7 ms to 29.9-74.5 ms
and TRIAGE from 261.2-307.4 ms to 36.8-90.3 ms. Pooled over 450 queries, BM25 p50/p95 is 43.4/98.3 ms and TRIAGE
53.5/118.4 ms. The vector legs did not change (APPROX p50 2.7-3.0 ms, EXACT 72.9-73.3 ms). The masked slice is still
the slowest keyword case (BM25 p50 74.5 ms, TRIAGE 90.3 ms). The query `paraphrase:GHSA-v4f4-23wc-99mh` still raises
SQL0901N inside TRIAGE at depths 50 and 64 and is answered at depth 128 by the fallback in `needle.triage`
(eval_sql0901n_fetch_approx.md).

**Reading the numbers.** Named and masked queries are text copied from a correct advisory (verbatim summary;
summary + details with package names and ids removed), so they are upper bounds. The paraphrase slice (synthetic, no
6-word run shared with the source) is the realistic case. There, hybrid TRIAGE reaches R@10 0.453 vs 0.360 for vector
APPROX and 0.340 for BM25 only.

## History

- `20261110T013825Z` (DB2INST1, no RCAC): superseded; BM25_SEARCH/TRIAGE were recreated at 01:41:05 UTC after this run, so its BM25 and hybrid numbers describe an earlier implementation.
- `20261110T014804Z` (DB2INST1, no RCAC, TRIAGE depth 100): superseded by the RCAC configuration.
- `20261110T022457Z` (NDL_SENIOR, RCAC, router depth, BM25_SEARCH before the LATERAL rewrite): superseded by this run. Its note on the change from `20261110T014804Z`:

> **What changed vs the pre-RCAC run.** Relevance is unchanged except one query. TRIAGE paraphrase R@1 went from
> 0.233 to 0.227 and MRR@10 from 0.302 to 0.295; every other R@1/R@3/R@10/MRR value is identical. Both vector legs
> return identical top-10 lists for all 450 queries: NDL_SENIOR sees all 26,210 rows, so the row permission removes
> nothing. BM25 lists differ for 2-9 queries per slice (public-only TERM_DF/CORPUS_STATS) without changing any hit
> metric. TRIAGE lists differ for most queries (118/89/29 identical per slice) because the router depth is 50 instead of
> 100. No query has an embargoed advisory in its ground truth (0 of 450), so the embargo rules do not affect these
> numbers. Latency changed substantially. BM25-only p50 rose from 31.2-76.4 ms to 244.2-277.7 ms, and TRIAGE p50 from
> 39.5-96.0 ms to 261.2-307.4 ms. APPROX (2.8-3.0 ms) and EXACT (73.6-80.3 ms) stayed. The cause was not profiled
> (UNKNOWN); the keyword leg reads NEEDLE.POSTING, which now has an active row permission. One query
> (`paraphrase:GHSA-v4f4-23wc-99mh`) raised SQL0901N inside TRIAGE at depths 50 and 64. `needle.triage` answered it
> through its fallback at depth 128 (926 ms); see eval_sql0901n_fetch_approx.md.


## Charts

eval/results/recall_by_slice.png, recall_at1_by_slice.png, latency_by_retriever.png (+ _dark variants), rendered from `20261110T024304Z.json` by `python eval/run_eval.py --charts-from eval/results/20261110T024304Z.json`.

## Reproduce

```
python eval/build_queries.py --verify
python eval/run_eval.py --embed-only --qvecs-out data/eval_qvecs.json.gz        # on the PC (Ollama)
# inside the codespace, DB2_USER=NDL_SENIOR, DB2_PASSWORD from stdin, DB2_HOST=localhost:
python3 eval/run_eval.py --qvecs-in data/eval_qvecs.json.gz --where codespace-localhost --no-charts \
    --retrievers triage,bm25,approx,exact --canonical
```
