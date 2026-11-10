# NEEDLE.TRIAGE: plans, BM25 parity, latency (bm25 agent)

Date: 2026-11-09, 19:30-19:50 CST. Db2 v12.1.5.0 CE (`special_85816`), database VECDB, Codespace container `db2`.
Data at measurement time: `NEEDLE.ADV_DOC` 26,210 rows with `ADV_DOC_VIX` (INDEXTYPE `VANN`, COSINE);
`NEEDLE.POSTING` 1,944,102 rows; `NEEDLE.TERM_DF` 184,278 terms; `CORPUS_STATS` N = 26,210, AVGDL = 131.6643.
No RCAC permission was active yet. Plans and latency must be re-measured after the rcac agent adds the row permissions.

Objects: `sql/02_bm25.sql`, `sql/03_triage_proc.sql`. Full `db2exfmt` output: `docs/evidence/explain/*.exfmt.txt`.
EXPLAIN method: `db2 "EXPLAIN PLAN FOR <statement with ? markers>"` then `db2exfmt -d VECDB -1` (as db2inst1 in the container).

## 1. Vector leg: which form uses the vector index

| Variant (file) | Statement shape | Plan (bottom-up) |
|---|---|---|
| v1 `v1_proc_leg` | bare `SELECT ... ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)),768,FLOAT32), COSINE) FETCH APPROX FIRST 100 ROWS ONLY` | `IXSCAN (VECIDX NEEDLE.ADV_DOC_VIX)` -> `FETCH ADV_DOC` -> `SORT` -> `TBSCAN` -> `RETURN`; total cost 2076.57 |
| v2 `v2_alias` | same, `ORDER BY <alias>` | identical to v1 (cost 2076.57) |
| v3 `v3_param_fetch` | `FETCH APPROX FIRST ? ROWS ONLY` | `TBSCAN ADV_DOC` (26,210 rows) -> `SORT` -> `FILTER` -> `SORT`; **no vector index**; cost 3401.55 |
| v4 `v4_cte_fusion` | vector leg as a CTE inside the fusion statement | vector CTE still `IXSCAN (VECIDX ADV_DOC_VIX)` (operator 33) |
| v6 `v6_final_hybrid` | the statement NEEDLE.TRIAGE_MODE builds for HYBRID (k = 10, depth = 100) | see tree below; vector leg `IXSCAN (VECIDX ADV_DOC_VIX)` (operator 10) |

Conclusions (observed): a bound query vector is fine; a parameter marker in `FETCH APPROX FIRST` disables the
vector index (confirms the known 12.1.5 behaviour); `FETCH APPROX` is honoured inside a CTE that is joined, so no
temporary table is needed.

v1 (bare vector leg):
```
            100 TBSCAN (2) <- 100 SORT (3) <- 100 FETCH (4) cost 2076.47
                                           /------+------\
                                   100 IXSCAN (5)     26210 TABLE: NEEDLE.ADV_DOC
                                         |
                                 26210 VECIDX: NEEDLE.ADV_DOC_VIX
```

v6 (final HYBRID statement, one statement):
```
RETURN(1) <- 10 TBSCAN(2) <- 10 SORT(3) <- 100 >HSJOIN<(4)  [full outer hash join = the RRF fusion]
  left : 100 TBSCAN(5) <- SORT(6) <- TBSCAN(7) <- SORT(8) <- FETCH(9) <- IXSCAN(10) <- VECIDX NEEDLE.ADV_DOC_VIX
  right: 75 FILTER(11) <- TBSCAN(12) <- SORT(13) <- FILTER(14) <- GRPBY(15) <- TBSCAN(16) <- SORT(17) <- NLJOIN(18)
           NLJOIN(18) outer: NLJOIN(19) = CORPUS_STATS (IXSCAN on its PK) x 64 query terms
                              (SORT(23) <- HSJOIN^(24) = TBSCAN TERM_DF (184,278 rows) x TEMP(27)/UNION(28)/GENROW
                               = the recursive JSON_VALUE walk of the query-term array)
           NLJOIN(18) inner: IXSCAN(31) NEEDLE.POSTING_PK_IX  (index-only: TF, BM25_DL, ROW_BUCKET, EMBARGO_UNTIL
                              are INCLUDE columns; no FETCH of POSTING data pages)
total cost 3217.14
```

Keyword leg alone (`v7_final_keyword_leg`, NEEDLE.BM25_SEARCH): same right-hand subtree, total cost 1140.54.
(These plans are from before RCAC was active. Under the POSTING row permission the plain join became a full scan of
POSTING_PK_IX; BM25_SEARCH now uses a LATERAL per-term probe: docs/evidence/rcac_posting_overhead.md.)
`TERM_DF` is read with a full `TBSCAN` (184 pages) + hash join for every query, because the optimizer estimates
~103 query terms. Negative result: a variant with a correlated scalar subquery for DF (`NDL_DEV_BM25.BM25_SEARCH_IX`)
was decorrelated back to the same TBSCAN + HSJOIN (estimated cost 591.0 vs 1140.5) and measured the same latency
(30 queries x 3 runs, depth 100: median 37.51 vs 37.87 ms, p95 87.29 vs 90.48 ms, identical top-100 on 30/30).
The keyword-leg cost is the posting aggregation for common terms (e.g. `code` df 16,230), not the TERM_DF scan.
Dropping very common terms would be faster but would break rank_bm25 parity, so it was not done.

## 2. Query-term expansion inside Db2 (one JSON parameter)

- ISO `JSON_TABLE(..., 'strict $[*]' ...)`: `SQL0104N An unexpected token "strict $[*]" ... Expected tokens may include:
  "strict $"`. Db2 12.1.5 JSON_TABLE takes only the row path `'strict $'`, so it cannot expand an array.
- `JSON_VALUE(doc, 'strict $[0]')` on a root-level array returned NULL. Wrapping as `{"t":[...]}` and walking
  `'strict $.t[' || i || ']'` in a recursive CTE (`NULL ON ERROR` ends the walk) works, including non-ASCII terms and
  the empty array. This is what `NEEDLE.BM25_SEARCH` uses (same pattern as `sql/99_validation.sql` V3).
- Legacy `SYSTOOLS.JSON_TABLE(SYSTOOLS.JSON2BSON(...), 't', 's:128')` was tried and **rejected**: it does not clear its
  output buffer between rows. For `["yaml","parsing","library","lets","attackers","run","code","loading","untrusted","files"]`
  it returned `letsary`, `runackers`, `codeckers`, `loadingrs`, `filessted`. Such terms silently match nothing.
  With it, the SQL BM25 top-10 differed from rank_bm25 on 29 of 30 queries; with the ISO walk, 0 of 30.

## 3. BM25 parity with rank_bm25

Definition (identical in SQL and `src/needle/bm25.py`): rank_bm25 `BM25Okapi`, k1 = 1.2, b = 0.75, epsilon = 0.25,
IDF `ln(N - df + 0.5) - ln(df + 0.5)`, negative IDF replaced by `epsilon * mean(raw IDF over the vocabulary)`
(the mean is `CORPUS_STATS.AVG_IDF`, computed in Db2). **No IDF formula difference.** Conventions: query terms are
de-duplicated; at most 64 query terms, lowest DF first; ranking by score DESC then ADV_ID ASC; score > 0 only.

| Check | Command | Result |
|---|---|---|
| Db2 statistics vs Python | `scripts/load_postings_in_codespace.sh` (check step) | postings 1,944,102 = 1,944,102; vocab 184,278 = 184,278; N 26,210 = 26,210; AVGDL equal; AVG_IDF 9.179734939733331 vs 9.179734939740372 (diff 7e-12, summation order) -> `CHECK MATCH` |
| unit + real corpus, no DB | `pytest tests/test_tokenize.py tests/test_bm25_parity.py -m "not db"` | 9 passed |
| SQL vs rank_bm25 (through the tunnel) | `pytest tests/test_bm25_parity.py tests/test_tokenize.py` | 10 passed (includes `test_sql_bm25_matches_rank_bm25`, 25 queries) |
| SQL vs rank_bm25 (in codespace) | `scripts/triage_check.py prepare` -> `triage_check_in_codespace.py --dbi-check` -> `triage_check.py compare` | 30 queries: exact_top10 = 30, mismatch = 0 (ids in order, scores within 1e-9) |
| NEEDLE.TRIAGE vs TRIAGE_MODE('HYBRID') | same run | 30/30 identical |
| TRIAGE_MODE('KW') order vs BM25_SEARCH | same run | 30/30 identical |
| Python wrapper (ibm_db_dbi callproc) vs ibm_db CALL | same run | 5/5 identical id lists |

Query set: 15 hand-written queries, 10 seeded-random advisory summaries (seed 20261109), 5 vague paraphrases
(`scripts/triage_check.py`). The small hand-made corpus in the unit test exercises the epsilon floor.

## 4. Latency (k = 10, depth = 100, 30 queries x 3 timed runs after 1 warm-up run each)

Measured inside the codespace (python3 + ibm_db -> localhost:50000), so it excludes the PC tunnel and the embedding:

| Call | median ms | p95 ms | max ms |
|---|---|---|---|
| `NEEDLE.TRIAGE` (HYBRID) | 37.57 | 93.21 | 96.32 |
| `TRIAGE_MODE` HYBRID | 38.13 | 91.59 | 95.67 |
| `TRIAGE_MODE` KW | 31.51 | 84.96 | 94.37 |
| `TRIAGE_MODE` VEC | 5.81 | 7.17 | 19.17 |
| `BM25_SEARCH` top 10 | 32.11 | 88.30 | 99.53 |

The keyword leg dominates. An earlier run of the same single-statement form measured 31.90 / 69.74 ms (median / p95),
so run-to-run noise on the shared codespace is visible. The rejected temporary-table variant (vector leg fetched into a
DGTT, then fused) measured 37.57 / 62.35 ms for HYBRID.

End to end from the PC (`PYTHONPATH=src python -m needle.triage "<vague yaml query>" --k 5`, 3 runs, through the SSH
tunnel): embed 2051 / 2046 / 2066 ms (Ollama), DB call 338 / 301 / 290 ms. Same top-5 in all 3 runs.

## 5. Design decisions

- One statement per call, no temporary table: every row is read from `ADV_DOC` / `POSTING` inside the caller's
  statement, so the caller's RCAC row permission (SESSION_USER) applies to both legs. A temporary-table version was
  built, measured and replaced. `tests/test_triage_rcac.py` attacks TRIAGE as NDL_JUNIOR with each forbidden
  advisory's own vector and summary (HYBRID, KW, VEC) plus a positive control; it skips until the RCAC objects exist
  (current result: `SKIPPED ... NEEDLE.USER_ACCESS does not exist yet`).
- Only validated INTEGERs (k, depth, both 1..1000) are concatenated into SQL; the vector and the terms are parameters.
- RANK() OVER uses ADV_ID as tie-break in both legs and in the final ORDER BY, so output is deterministic.
- SUPERSEDED (review C1, fixed 2026-11-09 ~20:15 CST, evidence `docs/evidence/fix_c1_h2.txt`): the statistics were
  first computed over all rows, and with SELECT on TERM_DF any analyst could subtract visible postings and recover
  the embargoed vocabulary (IDs included). Now TERM_DF / CORPUS_STATS cover PUBLIC rows only (no active embargo),
  are recomputed by NEEDLE.SYNC_POSTING_ACL, and no analyst has SELECT on them (BM25_SEARCH reads them with its
  definer's authority). Approximation: embargoed advisories are scored with public-corpus statistics; a term that
  occurs only in embargoed advisories gets DF = 0, and only for a caller whose RCAC row can see such a posting.
  Bucket-limited sweep users (NDL_P10..P75) still get DF over public rows outside their buckets (not a
  confidentiality boundary in this demo). The parity numbers in section 3 were measured before the fix; after the
  fix, `test_sql_bm25_matches_rank_bm25` runs as NDL_JUNIOR against rank_bm25 over the public corpus: PASSED.

## 6. Prior art

IBM `db2-ai-cookbook`, recipe `03-hybrid-search/sql-fusion-local-models` (checked with `gh api` on 2026-11-09):
keyword leg = Db2 Text Search (OpenSearch-backed BM25, `CONTAINS`/`SCORE`), vector leg = Db2 vectors, fused with a
gated, max-normalized weighted sum (its README says the fusion is not RRF and argues that RRF lets a guessing leg inject
noise; its README, last checked 2026-07-29, reports search failing because Text Search was not configured).
In this container Db2 Text Search is also not configured (`docs/evidence/text_search_probe.md`). NEEDLE's difference:
BM25 in plain SQL with exact rank_bm25 parity (no Text Search dependency), RRF fusion in one statement with the
vector index proven by EXPLAIN, and both legs under the caller's RCAC. RRF itself is not a contribution. The cookbook's
RRF critique is worth testing in the eval (exact-ID queries vs paraphrases).
