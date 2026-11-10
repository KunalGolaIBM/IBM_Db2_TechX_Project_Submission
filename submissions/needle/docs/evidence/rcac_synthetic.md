# RCAC x DiskANN, synthetic early answer (Step A)

Measured 2026-11-10 01:20–01:45 UTC on Db2 v12.1.5.0 (codespace container `db2`, database VECDB), by
`eval/rcac_sweep.py` run inside the codespace with python3 + ibm_db 3.3.0 (no tunnel). All numbers below are
copied from `eval/results/rcac_synthetic_results.json` and the raw logs in `docs/evidence/rcac_raw/`.
Real-data results: `docs/evidence/rcac_real.md`.

## Setup

- Table `NDL_DEV_RCAC.VEC_SYN (ID INT PK, ROW_BUCKET SMALLINT NOT NULL, CLUSTER_ID SMALLINT NOT NULL, EMB VECTOR(768, FLOAT32) NOT NULL)`.
- 30,000 unit vectors: 300 Gaussian clusters (centre + N(0, 0.6²/768) noise, renormalized), seed 7.
  ROW_BUCKET uniform 0..99, independent of the cluster (random visibility = best case for post-filtering).
  Insert: 30,000 rows in 16.4 s (`execute_many`, 500 per batch).
- `CREATE VECTOR INDEX NDL_DEV_RCAC.VEC_SYN_VIX ON ... (EMB) WITH DISTANCE COSINE` built in 96.7 s, then
  `RUNSTATS ... WITH DISTRIBUTION AND INDEXES ALL`.
- 50 query vectors from the same clusters (not in the table). k = 10, written as a literal; query vector bound as
  `VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32)`.
- Users: Linux users `ndl_senior, ndl_junior, ndl_p10, ndl_p25, ndl_p50, ndl_p75` inside the container
  (`scripts/rcac_users.sh`; passwords generated at run time, stored only in `needle/.env`). Each sweep user connects
  with its own credentials; `SESSION_USER` is that user. Grants: CONNECT and SELECT on the table only.
- Entitlements `NDL_DEV_RCAC.USER_ACCESS(AUTHID, MAX_BUCKET, SEES_EMBARGO)`: P10=10, P25=25, P50=50, P75=75,
  SENIOR=100 (MAX_BUCKET = visible percent). No statistics were collected on this small table.
- Permission (the contract form):
  `CREATE PERMISSION NDL_DEV_RCAC.VEC_SYN_ROWS ON NDL_DEV_RCAC.VEC_SYN FOR ROWS WHERE ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM NDL_DEV_RCAC.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER) ENFORCED FOR ALL ACCESS ENABLE`,
  then `ALTER TABLE ... ACTIVATE ROW ACCESS CONTROL` (SYSCAT.TABLES.CONTROL = 'R').
- Recall@10 = |APPROX top-10 ∩ EXACT top-10| / 10, where EXACT is `FETCH EXACT FIRST 10` run **as the same
  user** (RCAC applies). The user's EXACT matched a numpy exact top-10 over `ROW_BUCKET < MAX_BUCKET` for every
  query and user (agreement 1.0). Rows returned < 10 count as misses.

## Answer (a): is the vector index used?

Yes, at 30,000 rows, with and without RCAC (EXPLAIN as DB2INST1; the full db2exfmt output is in `rcac_raw/explain_*.txt`):

| Statement | Plan (top to bottom) | DiskANN SRCHLSIZ | Vector IXSCAN est. rows | Filter factor of the filter |
|---|---|---|---|---|
| APPROX 10, no filter | RETURN, TBSCAN, SORT, FETCH, IXSCAN `VECIDX VEC_SYN_VIX` | 50 | – | – |
| EXACT 10, no filter | RETURN, TBSCAN, SORT, TBSCAN (table) | – | – | – |
| APPROX 10, `WHERE ROW_BUCKET < 10` (literal) | same as APPROX, predicate sargable at FETCH | 105 | 105 | 0.0952849 |
| APPROX 10, `WHERE ROW_BUCKET < 25` (literal) | same | 61 | – | 0.247594 |
| APPROX 10, `WHERE ROW_BUCKET < 50` (literal) | same | 50 | – | 0.48825 |
| APPROX 10, `WHERE ROW_BUCKET < (SELECT MAX_BUCKET ... AUTHID = 'NDL_P10')` | NLJOIN(USER_ACCESS lookup, FETCH <- IXSCAN VECIDX) | 50 | 21 | 0.495 |
| **APPROX 10 under RCAC** (as DB2INST1, permission active) | NLJOIN(FETCH <- IXSCAN on USER_ACCESS PK, FETCH <- IXSCAN `VECIDX VEC_SYN_VIX`) | 50 | **21** | **0.495** |
| APPROX 41 under RCAC | same | 89 | – | 0.495 |
| APPROX 80 under RCAC | same | 162 | – | 0.495 |
| EXACT 10 under RCAC | TBSCAN of VEC_SYN (no vector index) | – | – | 0.495 |

db2exfmt "Statement With FGAC Applied" shows the permission rewritten into the query
(`Q3.ROW_BUCKET < (SELECT Q1.MAX_BUCKET FROM NDL_DEV_RCAC.USER_ACCESS AS Q1 WHERE (Q1.AUTHID = USER))`).
The predicate `(Q2.ROW_BUCKET < Q1.MAX_BUCKET)` is applied at the FETCH above the vector IXSCAN, with filter
factor 0.495; it does not depend on which user runs the statement (the value comes from a subquery at run time).
Plain-language reading: Db2 sizes the DiskANN scan for an "average" user who sees about half the table
(IXSCAN est. 21 rows = 10 / 0.495) and then removes the rows the actual user may not see. This is **consistent
with post-filtering**; there is no IBM document that states it. db2exfmt also warns `EXP0020W Statistics have
not been collected for table "NDL_DEV_RCAC"."USER_ACCESS"`.

Plan sharing across users: not proven on this table. After the sweep, `MON_GET_PKG_CACHE_STMT` held no entry for
these statements (only the monitor query itself), so `EXPLAIN_FROM_SECTION` could not be run; the real-data run
flushes the cache and captures sections immediately (`docs/evidence/rcac_real.md`).

## Answer (b): recall@10 and rows returned vs visible fraction (50 queries)

RCAC users, same SQL text for every user (`FETCH APPROX FIRST 10`):

| User | Visible rows | APPROX 10 recall@10 | rows returned (mean) | queries with < 10 rows | APPROX p50 ms | EXACT p50 ms |
|---|---|---|---|---|---|---|
| NDL_P10 | 2,996 (9.99 %) | **0.226** | **2.26** | **50 / 50** | 5.53 | 18.70 |
| NDL_P25 | 7,505 (25.0 %) | **0.556** | **5.56** | **49 / 50** | 5.30 | 41.79 |
| NDL_P50 | 14,909 (49.7 %) | 0.882 | 9.34 | 14 / 50 | 3.88 | 82.11 |
| NDL_P75 | 22,375 (74.6 %) | 0.950 | 10.00 | 0 / 50 | 4.56 | 126.65 |
| NDL_SENIOR | 30,000 (100 %) | 0.974 | 10.00 | 0 / 50 | 3.80 | 167.80 |

Same filter as a plain WHERE, run by DB2INST1 with RCAC deactivated (mechanism control):

| Filter | APPROX 10 recall, literal `ROW_BUCKET < p` | rows | < 10 rows | APPROX 10 recall, subquery form | rows |
|---|---|---|---|---|---|
| p = 10 | 0.894 | 9.02 | 22 / 50 | 0.226 | 2.26 |
| p = 25 | 0.846 | 9.02 | 22 / 50 | 0.556 | 5.56 |
| p = 50 | 0.882 | 9.34 | 14 / 50 | 0.882 | 9.34 |
| p = 75 | 0.942 | 9.72 | 10 / 50 | 0.950 | 10.00 |
| none | 0.974 | 10.00 | 0 / 50 | 0.974 | 10.00 |

The RCAC numbers equal the subquery-WHERE numbers query for query (same index, same plan shape). A literal filter
lets the optimizer size the scan from the real filter factor (SRCHLSIZ 105 at 10 %), so it under-fills far less;
it still under-fills sometimes, because the scan returns about k / filter-factor candidates and the expected number
of visible rows among them is about k.

## Levers

**Search list size (inline guideline) does not fix under-fill.** `/* <OPTGUIDELINES><IXSCAN TABLE='T' SEARCH_LIST_SIZE='200'/></OPTGUIDELINES> */`
is applied without setting DB2_OPTPROFILE (registry shows only DB2COMM and DB2SYSTEM): db2exfmt shows `SRCHLSIZ 200`
under RCAC, but the vector IXSCAN estimate stays 21 rows. As NDL_P10, rows returned for queries 1–5 were
4, 5, 0, 1, 2 with L = 200 and 4, 4, 2, 1, 2 with L = 1000 (`run-as` output). L changes how wide the graph search is,
not how many candidates reach the permission filter.

**Depth (FETCH APPROX FIRST n, keep the 10 nearest) does.** Recall@10 / mean rows returned / queries with < 10 rows:

| User | n = 10 | n = 20 | n = 50 | n = 100 | n = 200 |
|---|---|---|---|---|---|
| NDL_P10 | 0.226 / 2.26 / 50 | 0.410 / 4.10 / 50 | 0.874 / 10.04 / 24 | 1.000 / 100 / 0 (p50 20.0 ms) | 1.000 / 200 / 0 (p50 20.5 ms) |
| NDL_P25 | 0.556 / 5.56 / 49 | 0.846 / 10.28 / 22 | 0.998 / 25.54 / 0 | 1.000 / 100 / 0 (p50 44.7 ms) | 1.000 / 200 / 0 |
| NDL_P50 | 0.882 / 9.34 / 14 | 0.962 / 19.04 / 0 | 1.000 / 48.40 / 0 | 1.000 / 100 / 0 (p50 83.4 ms) | 1.000 / 200 / 0 |

Caution: from n = 100 the APPROX latency equals the EXACT latency of that user (P10 20.0 vs 18.7 ms, P50 83.4 vs
82.1 ms) and every query returns exactly n rows. That pattern is what an exact table scan produces; the plans at
n = 100 were not explained on this table, so recall 1.0 at n >= 100 must not be read as ANN recall. The real-data
sweep explained every depth and confirms it: under RCAC, n = 50 still uses the vector index (est. 102 candidates) and
n = 100 / 200 run as table scans (`docs/evidence/rcac_real.md`, finding 5).

## Router (first version, synthetic)

`src/needle/rcac.py`, first configuration (since replaced by the real-data version: fixed depths, guideline,
EXACT fallback, thresholds fitted on a dev split): EXACT when visible rows <= 2,000 or fraction < 0.15, else APPROX
with depth = ceil(10 x 2.0 / fraction). Visible rows = `COUNT(*)` as the user (RCAC applies), total = SYSCAT.TABLES.CARD.

| User | Router choice | recall@10 | rows returned >= 10 | p50 ms |
|---|---|---|---|---|
| NDL_P10 | EXACT 10 | 1.000 | 50 / 50 | 19.24 |
| NDL_P25 | APPROX 80 | 1.000 | 50 / 50 | 11.30 |
| NDL_P50 | APPROX 41 | 0.996 | 50 / 50 | 5.53 |
| NDL_P75 | APPROX 27 | 0.988 | 50 / 50 | 5.06 |
| NDL_SENIOR | APPROX 20 | 0.988 | 50 / 50 | 3.05 |

These thresholds were chosen before the run, not fitted, but they were evaluated on the same 50 queries; the
real-data router is fitted on dev queries and reported on held-out queries only.

## Limits of this synthetic run

- One random seed, random (uncorrelated) visibility; 50 queries; latency measured while other agents used the
  same Db2 instance.
- Clustered Gaussian vectors are not real embeddings; the real-data run is the headline.

## Raw output

`docs/evidence/rcac_raw/sweep_where.log`, `sweep_rcac.log` (console lines quoted below),
`explain_norcac_{0,1,2,lit25,lit50,subq10}.txt`, `explain_rcac_{approx10,approx41,approx80,exact10,sls200}.txt` (db2exfmt).

```
[where]  10%  exact ms=18.73  approx10 literal recall=0.894 rows=9.02  subq recall=0.226 rows=2.26
[where]  25%  exact ms=41.54  approx10 literal recall=0.846 rows=9.02  subq recall=0.556 rows=5.56
[where]  50%  exact ms=77.19  approx10 literal recall=0.882 rows=9.34  subq recall=0.882 rows=9.34
[where]  75%  exact ms=111.43  approx10 literal recall=0.942 rows=9.72  subq recall=0.95 rows=10.0
[where] 100%  exact ms=148.54  approx10 literal recall=0.974 rows=10.0  subq recall=0.974 rows=10.0
[rcac] NDL_P10    visible=2996/30000 exact ms=18.7 agree_np=1.0  approx10 recall=0.226 rows=2.26 lt_k=50  router=EXACT/10 recall=1.0 ms=19.24
[rcac] NDL_P25    visible=7505/30000 exact ms=41.79 agree_np=1.0  approx10 recall=0.556 rows=5.56 lt_k=49  router=APPROX/80 recall=1.0 ms=11.3
[rcac] NDL_P50    visible=14909/30000 exact ms=82.11 agree_np=1.0  approx10 recall=0.882 rows=9.34 lt_k=14  router=APPROX/41 recall=0.996 ms=5.53
[rcac] NDL_P75    visible=22375/30000 exact ms=126.65 agree_np=1.0  approx10 recall=0.95 rows=10.0 lt_k=0  router=APPROX/27 recall=0.988 ms=5.06
[rcac] NDL_SENIOR visible=30000/30000 exact ms=167.8 agree_np=1.0  approx10 recall=0.974 rows=10.0 lt_k=0  router=APPROX/20 recall=0.988 ms=3.05
```

Reproduce (inside the codespace, credentials on stdin only):
`grep -E '^(DB2_|NDL_)' .env | gh codespace ssh -c $CS -- 'cd ~/ndl_rcac && E=$(cat); for c in "synth-load --n 30000 --drop --index" "synth-rcac setup" "sweep where" "synth-rcac activate" "sweep rcac"; do printf "%s\n" "$E" | python3 rcac_sweep.py $c; done'`
(the `sweep` commands now use the current router configuration, so the router rows would differ from the table above).
