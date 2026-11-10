# Keyword-leg overhead under RCAC on NEEDLE.POSTING: cause and fix (bm25 agent)

Date: 2026-11-09 ~20:55-21:30 CST. Db2 12.1.5.0, VECDB, RCAC active (row permission NEEDLE.POSTING_ROWS), 27 embargoed
advisories, AUTO_RUNSTATS unchanged (OFF). Time box 40 min. Full plans: `docs/evidence/explain/kw_rcac_before.exfmt.txt`,
`docs/evidence/explain/kw_rcac_after.exfmt.txt` (EXPLAIN PLAN of `SELECT ... FROM TABLE(NEEDLE.BM25_SEARCH(?, 100))`
as DB2INST1; under the permission every user shares one plan, docs/evidence/rcac_real.md).

## Cause (observed in the plan)

The suggested covering index already existed: `POSTING_PK_IX (TERM, ADV_ID) INCLUDE (TF, BM25_DL, ROW_BUCKET,
EMBARGO_UNTIL)`. Both plans read POSTING index-only (no FETCH of POSTING data pages). The cost came from the join order:

Before (plain join `QI JOIN NEEDLE.POSTING P ON P.TERM = QI.TERM`), total cost 5622.45:
```
NLJOIN(9) <- ^HSJOIN(12)
   outer: 962,330 NLJOIN(13) = FETCH USER_ACCESS (permission subquery) x IXSCAN(16) POSTING_PK_IX (all 1.9441e+06 entries)
   inner: 25 query terms (TBSCAN(17) <- SORT <- FILTER <- TERM_DF / recursive JSON_VALUE walk)
```
Db2 scanned the WHOLE posting index (1.94M entries, permission applied to each) and hash-joined it with ~25 query
terms, for every query. Before RCAC the same SQL probed POSTING_PK_IX once per term (NLJOIN, ~10.5 rows per probe;
docs/evidence/triage_explain.md).

## Fix (kept): LATERAL per-term probe, no DDL

`NEEDLE.BM25_SEARCH` (sql/03_triage_proc.sql) now reads POSTING through a correlated table expression:
```sql
FROM QI, CS,
     LATERAL (SELECT P1.ADV_ID, P1.TF, P1.BM25_DL FROM NEEDLE.POSTING P1 WHERE P1.TERM = QI.TERM) AS P
```
After, total cost 970.106:
```
NLJOIN(9)
   outer: 25 query terms (NLJOIN(10) = CORPUS_STATS x terms)
   inner: NLJOIN(29) = FETCH USER_ACCESS x IXSCAN(32) POSTING_PK_IX   (est. 5.2 rows per term probe, permission applied)
```
Same SQL semantics (inner join on TERM). No index was added, so nothing was added to sql/02_bm25.sql and no RUNSTATS
was needed. Second change in the same function: the keyword rank orders by `ROUND(KW_SCORE, 9) DESC, ADV_ID`
(and `Bm25Index.top` the same). Reason: with the new plan the per-term parts are summed in another order; two
advisories with equal scores then differed in the last bit and swapped places (`GHSA-32vr-5gcf-3pw2` /
`PYSEC-2026-462`, 25.305481024). Rounding makes the ADV_ID tie-break independent of the plan.

## Measurements (inside the codespace, python3 + ibm_db -> localhost:50000)

Same 30 queries as docs/evidence/triage_explain.md (`data/triage_cases.json`), 1 warm-up + 3 timed runs per query,
BM25_SEARCH top 10 and TRIAGE_MODE HYBRID (k = 10) at the router depth of each user (50 for NDL_SENIOR, 128 for NDL_P10).

| User | Call | before p50 / p95 ms | after p50 / p95 ms (final, with ROUND) |
|---|---|---|---|
| NDL_SENIOR | BM25_SEARCH top 10 | 244.8 / 321.9 | 27.2 / 66.7 |
| NDL_SENIOR | TRIAGE HYBRID, depth 50 | 256.4 / 325.3 | 34.4 / 85.2 |
| NDL_P10 | BM25_SEARCH top 10 | 136.4 / 152.0 | 17.3 / 23.1 |
| NDL_P10 | TRIAGE HYBRID, depth 128 | 153.6 / 170.2 | 35.8 / 42.3 |

(An intermediate run with LATERAL but without ROUND: NDL_SENIOR 26.1 / 65.3 and 33.1 / 79.5; NDL_P10 17.2 / 25.1 and
35.4 / 46.9.) For reference, before RCAC the keyword leg measured p50 32.11 / p95 88.30 ms as DB2INST1
(triage_explain.md); the codespace is shared, so run-to-run noise of this size is normal.

## Result equality and tests

- Before vs final, per user, 30 queries: BM25 top-10 ids + scores (rounded to 1e-9) differing = 0 (NDL_SENIOR),
  0 (NDL_P10); TRIAGE top-10 ids differing = 0 and 0. (Without ROUND: 1 of 30 differed for NDL_SENIOR, the tie swap above.)
- `pytest tests/test_bm25_parity.py tests/test_triage_rcac.py tests/test_triage_router.py tests/test_rcac.py
  tests/test_tokenize.py` (DB tests included) -> 60 passed (run twice: after LATERAL, and after ROUND).

Not done: per-user EXPLAIN_FROM_SECTION for the keyword leg (the plan is shared by all users under the permission; the
EXPLAIN PLAN above is as DB2INST1). The scratch function `NDL_DEV_BM25.BM25_SEARCH_LAT` (dev schema) remains.
