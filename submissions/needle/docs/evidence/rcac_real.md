# RCAC x DiskANN on real data (NEEDLE.ADV_DOC) — the headline experiment

Status: measured 2026-11-10 (UTC) on Db2 v12.1.5.0 (codespace container `db2`, database VECDB) by
`eval/rcac_sweep.py`, run inside the codespace (python3 + ibm_db 3.3.0, no tunnel). Every number in the tables is
generated from `eval/results/rcac_real_results.json` (+ `rcac_plancache.json`, `rcac_triage.json`,
`rcac_router_fit.json`) by `eval/rcac_report.py`; raw console logs and db2exfmt output are in `docs/evidence/rcac_raw/`.
Synthetic precursor: `docs/evidence/rcac_synthetic.md`.

## Question

Does row access control (CREATE PERMISSION) on a table with a DiskANN vector index change (a) whether Db2 uses the
vector index for `FETCH APPROX FIRST n ROWS ONLY`, and (b) recall@10 against an exact search over the rows the user
may see, as a function of the fraction of rows visible to the user? Does a per-user router restore recall?

## Setup (frozen)

- Corpus: `NEEDLE.ADV_DOC`, 26,210 OSV PyPI advisories (loaded by the data agent), `EMB VECTOR(768, FLOAT32) NOT NULL`
  (nomic-embed-text, `search_document: ` prefix), `CREATE VECTOR INDEX NEEDLE.ADV_DOC_VIX ... WITH DISTANCE COSINE`,
  RUNSTATS at 2026-11-10 01:31:23 UTC (SYSCAT.TABLES.STATS_TIME). `AUTO_RUNSTATS` set OFF before the runs; no DML on
  ADV_DOC during a run.
- Visibility: `ROW_BUCKET` 0..99 from a hash of CANON_ID (random with respect to content = best case for
  post-filtering). Users see `ROW_BUCKET < MAX_BUCKET`, so MAX_BUCKET is the visible percentage.
- Identities: real, separate Db2 users authenticated by the OS inside the container (`scripts/rcac_users.sh`):
  NDL_P10, NDL_P25, NDL_P50, NDL_P75 (sweep), NDL_SENIOR (100 %, sees embargo), NDL_JUNIOR (100 %, no embargo).
  Each measurement connects with that user's own password; `SESSION_USER` and `CURRENT USER` are recorded per user.
  No result is filtered in Python.
- Policy: `sql/04_rcac.sql` — permission `NEEDLE.ADV_DOC_ROWS`:
  `ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM NEEDLE.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER) AND (EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP OR (SELECT UA.SEES_EMBARGO ...) = 1)`,
  `ENFORCED FOR ALL ACCESS`, activated with `ALTER TABLE ... ACTIVATE ROW ACCESS CONTROL ACTIVATE COLUMN ACCESS CONTROL`.
  25 advisories embargoed (25 most recent non-withdrawn GHSA, by CANON_ID). USER_ACCESS has RUNSTATS.
- Queries: 170 pre-embedded queries (`eval/rcac_make_queries.py`, `search_query: ` prefix): the 20 fixed G1 triage
  queries (same as `docs/evidence/g1_vector_index.md`) + the 150 paraphrase queries of the eval set.
  Split by sha256(qid) parity: dev 81 / held-out 89. The router is fitted on dev only and reported on held-out only.
- k = 10, always a literal (`FETCH APPROX FIRST ? ROWS` never uses the index on 12.1.5). Query vector bound as
  `VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32)`. Each SQL shape is prepared once and warmed up with 2 executions that
  are not counted. Latency = client wall clock of execute + fetch inside the codespace, other agents active.
- Metrics per user and condition: recall@10 = |returned top-10 ∩ G| / |G| where G = `FETCH EXACT FIRST 10` **run as
  that user**; under-fill rate = share of queries returning fewer than 10 rows (counted as misses, never
  re-normalized); leaks = returned IDs outside the user's permission (checked against DB2INST1's ID → bucket/embargo
  map); p50/p95 ms. Oracle check: the user's EXACT equals DB2INST1's EXACT with the permission written as an explicit
  WHERE (`ROW_BUCKET < p AND not embargoed`).
- Plans: EXPLAIN PLAN as DB2INST1 for every SQL text; operators, `SRCHLSIZ` (DiskANN search list size L) and the
  vector IXSCAN row estimate are read from DB2INST1.EXPLAIN_ARGUMENT / EXPLAIN_STREAM, filter factors from
  EXPLAIN_PREDICATE. Runtime sections: `FLUSH PACKAGE CACHE DYNAMIC`, run the same statement as each user (both
  orders), read `MON_GET_PKG_CACHE_STMT`, format the executed section with `EXPLAIN_FROM_SECTION`.
- Mechanism control: the plain-WHERE baseline was run by DB2INST1 **before** row access control was activated (after
  activation DB2INST1's plans also carry the permission predicate, so later DB2INST1 numbers are not a clean control).

## Findings (observed facts; wording rules: "over-fetch by 1/FF", "constant observed optimizer estimate 0.495")

1. **The vector index is used under RCAC.** `FETCH APPROX FIRST 10` as any RCAC user runs an IXSCAN on
   `VECIDX NEEDLE.ADV_DOC_VIX` (EXPLAIN as DB2INST1 and EXPLAIN_FROM_SECTION of the section the users actually ran).
2. **One shared plan for every user (proven at run time).** After `FLUSH PACKAGE CACHE DYNAMIC`, the same statement
   run as NDL_P10, P25, P50, P75 and SENIOR left exactly one package-cache entry, whose NUM_EXECUTIONS grew by 10
   per user, in both user orders (forward executable id `...1110015942020530`, reverse `...1110015943844308`).
   ROWS_READ grew by the same 35,226 per 10 queries for every user (a table scan would read 262,100); rows returned
   per 10 queries were 28 / 53 / 90 / 100 / 100. The executed section (`rcac_raw/section_forward_0.txt`):
   NLJOIN(USER_ACCESS lookup) -> FILTER(embargo clause, FF 1) -> FETCH(`Q5.ROW_BUCKET < Q1.MAX_BUCKET`, FF 0.495)
   <- IXSCAN VECIDX ADV_DOC_VIX, estimated 21 rows.
3. **Over-fetch by 1/FF with one compile-time estimate.** The permission predicate gets the constant observed
   optimizer estimate FF = 0.495 for every user (also on the synthetic table, where USER_ACCESS had no statistics).
   The vector IXSCAN is sized at FETCH n / FF (21 rows for n = 10, DiskANN SRCHLSIZ 50), and the permission is applied
   to those candidates at FETCH. Predicted rows returned ≈ min(10, 21 · s): 2.1 at s = 0.10 and 5.3 at s = 0.25;
   measured 2.05 and 5.08. 36 of 170 NDL_P10 queries returned **zero** rows; every row that was returned was in the
   user's exact top-10 (precision among returned rows 1.0 at P10).
4. **RCAC is not the cause; it makes the estimate unavoidable and invisible to the application.** The same filter as a
   plain WHERE with the value hidden in a scalar subquery (DB2INST1, before activation) gives the same plan
   (est. 21) and the same numbers (P10 0.206 / 2.06 rows; P25 0.503 / 5.08). A literal `WHERE ROW_BUCKET < 10` is
   sized from statistics (FF 0.1179, SRCHLSIZ 90, est. 85 rows) and returns 7.77 rows, recall 0.682.
   Users above the assumed visibility gain: at 75 % RCAC under-fills 1 % of queries, the literal WHERE 31 %
   (est. 21 vs 14 candidates). This is a selectivity-estimation + filtered top-K interaction, not an RCAC defect.
5. **Plan switch to a table scan at large n/FF.** The optimizer keeps the vector index while the estimated candidate
   count n / FF stays at about 100–134 and switches to a table scan above that: no filter n = 100 IXSCAN (est. 100),
   n = 200 TBSCAN; literal 75 % n = 100 IXSCAN (est. 134), n = 200 TBSCAN; literal 50 % n = 50 IXSCAN (est. 101),
   n = 100 TBSCAN; literal 10 % n = 10 IXSCAN (est. 85), n = 25 TBSCAN; RCAC n = 50 IXSCAN (est. 102), n = 100 and
   200 TBSCAN. So `FETCH APPROX FIRST 100` under RCAC is an exact scan (recall 1.0, latency = EXACT), not ANN. With a
   literal filter, a 10 % user gets that automatic switch from n = 25; under the shared RCAC estimate the
   low-visibility users never get it until n = 100.
6. **SEARCH_LIST_SIZE fixes quality, not count.** The inline guideline `<IXSCAN TABLE='T' SEARCH_LIST_SIZE='200'/>`
   is applied without DB2_OPTPROFILE (SRCHLSIZ 200 in EXPLAIN; the vector IXSCAN estimate stays 21). P10: 0.206 /
   2.06 rows (unchanged); P50: precision among returned rows 0.946 -> 0.998, recall 0.848 -> 0.892; P75: recall
   0.952 -> 0.995. Only the FETCH depth changes the candidate count.
7. **Router restores recall and row count on held-out queries.** Rule written before the results were seen: highest
   dev recall, then lowest dev latency within 0.005 (`eval/rcac_router_fit.py`, 81 dev queries) -> T = 7,000 visible
   rows, m = 3.0. On the 89 held-out queries: P10 EXACT 1.000, P25 EXACT 1.000, P50 APPROX 100 / L 300 (runs as a
   table scan) 1.000, P75 APPROX 50 / L 150 0.988, SENIOR APPROX 50 / L 150 0.987; 10 of 10 rows for every query,
   0 EXACT fallbacks, 0 SQL0901N, 0 leaks. Plain APPROX 10 on the same held-out queries: 0.208 / 0.506 / 0.852 /
   0.947 / 0.948. At 26,210 rows EXACT is cheap (16 ms at 10 %, 146 ms at 100 %), so the case for the router is
   recall and row count, not speed.
8. **Security checks.** For all users and all 170 queries the user's EXACT top-10 equals DB2INST1's EXACT with the
   permission written as an explicit WHERE (170/170). No cell of the sweep returned an ID outside the user's
   permission (0 leaks). `pytest -m db tests/test_rcac.py tests/test_triage_rcac.py`: 24 passed
   (`rcac_raw/pytest_db.log`): distinct identities, embargoed IDs invisible to NDL_JUNIOR through ADV_DOC, crafted
   SQL (OR 1=1, CTE, UNION, self-join), POSTING, ADV_ALIAS, ADV_AFFECTED, the vector leg queried with the embargoed
   advisory's own embedding (APPROX and EXACT), TRIAGE in HYBRID / KW / VEC mode; junior cannot read USER_ACCESS or
   ADV_RAW, change USER_ACCESS, deactivate RCAC, disable the permission, drop the mask, update EMBARGO_UNTIL or
   `SET SESSION AUTHORIZATION`. Positive controls: NDL_SENIOR sees the embargoed rows and TRIAGE returns them.
   After the demo embargo below (27 embargoed rows) and the BM25 statistics fix, the full file set was re-run:
   `pytest tests/test_rcac.py tests/test_triage_rcac.py`: 35 passed (11 unit + 24 DB),
   `rcac_raw/pytest_all_after_demo_embargo.log`.
9. **TRIAGE inherits the effect.** The fused HYBRID statement uses IXSCAN VECIDX (est. 21) at P_DEPTH 10 and no vector
   index at P_DEPTH 100. `TRIAGE_MODE(..., 'VEC')`, k = 10, 20 G1 queries: NDL_P10 gets 2.2 rows at depth 10
   (20 of 20 queries under-filled) and 10 rows at depth 100.

## Correlated visibility (copy; `rcac_sweep.py correlated`, `eval/results/rcac_correlated.json`, `rcac_raw/correlated.log`)

Random buckets are the best case for over-fetch. Here users see whole topic clusters: spherical k-means (k = 100,
seed 7, 25 iterations, numpy) on the 26,210 ADV_DOC embeddings; clusters taken in id order, each cluster gets
COR_BUCKET = cumulative share of rows before it (0..99), so `COR_BUCKET < p` covers about p % of rows (measured
coverage 10.2 / 26.7 / 50.1 / 100 %; cluster sizes 34 / 192 / 1,111 min / median / max). Copy `NDL_DEV_RCAC.ADV_COR
(ADV_ID, COR_BUCKET, EMB NOT NULL)` in 10 committed INSERT ... SELECT batches, own vector index + RUNSTATS (58.7 s),
permission `COR_BUCKET < (SELECT MAX_BUCKET FROM NDL_DEV_RCAC.USER_ACCESS WHERE AUTHID = SESSION_USER)`, same 170
queries, recall vs each user's own EXACT. Router: the frozen config (T = 7,000, m = 3.0, fitted on the random-bucket
dev split), held-out queries only. Copy and mapping table dropped afterwards.

| User (visible rows) | APPROX 10 recall / rows / under-fill (170) | queries with recall 0 / (0,0.5) / [0.5,1) / 1 | queries with 0 / 1-9 / 10 rows | Router choice | Router held-out recall / rows / fallbacks / p50 | Random-bucket APPROX 10 recall (main sweep) |
|---|---|---|---|---|---|---|
| NDL_P10 (2,679) | 0.104 / 1.04 / 0.96 | 130 / 25 / 9 / 6 | 130 / 34 / 6 | EXACT 10 | 1.000 / 10 / 0 / 16.3 ms | 0.205 |
| NDL_P25 (6,989) | 0.231 / 2.31 / 0.94 | 72 / 69 / 18 / 11 | 72 / 87 / 11 | EXACT 10 | 1.000 / 10 / 0 / 36.4 ms | 0.502 |
| NDL_P50 (13,121) | 0.638 / 6.56 / 0.56 | 20 / 36 / 56 / 58 | 20 / 75 / 75 | APPROX 100, L 300 | 0.965 / 10 / 3 / 6.2 ms | 0.848 |
| NDL_SENIOR (26,210) | 0.949 / 10.00 / 0.00 | 1 / 0 / 43 / 126 | 0 / 0 / 170 | APPROX 50, L 150 | 0.984 / 10 / 1 / 4.8 ms | 0.950 |

Leaks: 0 in every cell. Plan (EXPLAIN as DB2INST1): APPROX 10 = IXSCAN VECIDX, SRCHLSIZ 50, est. 21; the
permission's filter factor is **0.49296** on this table (0.495 on ADV_DOC), so the estimate follows the filtered
column's distribution (COR_BUCKET is not uniform), not the entitlement table — consistent with the interpolation
hypothesis above. As expected with topic-correlated visibility, the picture is bimodal: for NDL_P10, 130 of 170
queries get 0 rows (their neighbourhood is invisible) and 6 get all 10; correlated visibility roughly halves APPROX 10
recall at 10–25 % compared with random buckets, while the router stays at 1.000 there because it chooses EXACT.

Observed plan difference: on ADV_COR the router's depth-100 text with the guideline (`SEARCH_LIST_SIZE='300'`) kept the
vector index (IXSCAN est. 203, SRCHLSIZ 203; depth 200 + L 600: est. 406, SRCHLSIZ 406), while without the guideline
depths 100 and 200 ran as table scans. On ADV_DOC the same depth-100 + L 300 text ran as a table scan. So at P50 the
router ran true ANN on ADV_COR (6.2 ms, recall 0.965, 3 EXACT fallbacks for queries under 10 rows) but an exact scan
on ADV_DOC (78.5 ms, recall 1.000). SRCHLSIZ showed n / FF (203, 406), not the guideline's L (300, 600).
Not run: other seeds, other k, the anti-correlated case.

## Demo case (applied after all measurements above were frozen)

`sql/04_rcac.sql` step 2b puts a SYNTHETIC demo embargo flag on the real advisory GHSA-5x8w-8jj5-q52h (Pillow FlashPix
heap overflow) and every row sharing its CANON_ID (also PYSEC-2026-4330), EMBARGO_UNTIL = now + 60 days
(2027-01-09-02.10.48), then `CALL NEEDLE.SYNC_POSTING_ACL` (P_UPDATED = 589; POSTING now holds 27 embargoed ADV_IDs,
ADV_DOC 27 embargoed rows; `rcac_raw/apply_04_step2b.log`). `eval/rcac_demo_case.py` runs the app's `triage()`
(HYBRID, k 10, depth 100) for "heap overflow in the image library's FlashPix JPEG decoder can lead to code execution,
no CVE yet" as each user (`docs/evidence/rcac_demo_case.txt`): NDL_JUNIOR sees 0 rows with that ADV_ID and TRIAGE does
not return it; NDL_SENIOR gets it at rank 1 (KW rank 3, vector rank 1) and PYSEC-2026-4330 at rank 2.

## Limits

- One corpus; one random visibility assignment for the main sweep (random buckets = best case for over-fetch) and one
  k-means correlated assignment on a copy (one seed); 170 queries (89 held-out). Latencies were measured while other
  agents used the instance.
- Section actuals were captured for 9 NDL_P10 executions only (3 queries x 3 L values); the other cells rest on
  estimated plans, the shared executable id and measured row counts.
- Mask: Db2 12.1.5.0 rejects `CREATE MASK` on the CLOB column DETAILS (`SQL0350N ... data type of the column is not
  supported. SQLSTATE=42962`); DETAILS is protected by the row permission alone and the mask covers SUMMARY.
- BM25 statistics: as first applied, TERM_DF and CORPUS_STATS (N, DF, AVGDL) were global and readable by the analyst
  users. The security review found this is a real leak, not a small side channel: global DF minus the DF of visible
  postings reconstructs the vocabulary of embargoed advisories (including GHSA/CVE IDs). Fix by the BM25 agent:
  statistics over public rows only (refreshed by NEEDLE.SYNC_POSTING_ACL) and REVOKE SELECT on TERM_DF and
  CORPUS_STATS from the analyst users. The RCAC sweep above does not read these tables.
- Activating RCAC changed DB2INST1's own plans (its queries now carry the permission predicate); numbers measured as
  DB2INST1 after 2026-11-10 ~01:47 UTC are not comparable with earlier ones.

## Additional controls

**Where does 0.495 come from? (`rcac_sweep.py ffsource`, `eval/results/rcac_ffsource.json`, `rcac_raw/ffsource.log`)**
The sweep users' MAX_BUCKET values were changed from 10/25/50/75 to 10/10/10/10, RUNSTATS on USER_ACCESS
(MAX_BUCKET COLCARD 5 -> 2, LOW2KEY/HIGH2KEY 25/75 -> 10/100), and the RCAC APPROX 10 statement was re-explained;
then the values were restored and RUNSTATS repeated.

| USER_ACCESS state | MAX_BUCKET COLCARD, LOW2KEY, HIGH2KEY | permission FF | vector IXSCAN est. rows | SRCHLSIZ |
|---|---|---|---|---|
| before (10/25/50/75) | 5, 25, 75 | 0.495 | 21 | 50 |
| changed (10/10/10/10) + RUNSTATS | 2, 10, 100 | 0.495 | 21 | 50 |
| restored + RUNSTATS | 5, 25, 75 | 0.495 | 21 | 50 |

The synthetic table gave the same 0.495 with no statistics on its access table at all. So the estimate does not come
from the entitlement table's statistics. Hypothesis (not proven): an interpolation on ROW_BUCKET (0..99) with an
assumed comparison value at the middle of the range, (50 − 0.5) / 100 = 0.495; the literal `ROW_BUCKET < 10` gives
0.1179 here (RUNSTATS WITH DISTRIBUTION) and 0.0953 = (10 − 0.5)/100 on the synthetic table. Not tested:
`SELECTIVITY` clause / DB2_SELECTIVITY (needs an instance restart).

**Section actuals (`rcac_sweep.py actuals`, `eval/results/rcac_actuals.json`, `rcac_raw/actuals_*.txt`).** Activity
event monitor `NDL_RCAC_ACT` + `WLM_SET_CONN_ENV(<NDL_P10 handle>, collectactdata WITH DETAILS, SECTION;
collectsectionactuals BASE)` on one NDL_P10 connection only; 3 queries x inline SEARCH_LIST_SIZE 50 / 200 / 1000;
`EXPLAIN_FROM_ACTIVITY` + db2exfmt for each of the 9 activities. Actual rows out of the vector IXSCAN
(`VECIDX NEEDLE.ADV_DOC_VIX`, operator 12, estimate 21): **21 in all 9 activities** at L = 50, 200 and 1000; actual
rows out of the FETCH that applies `ROW_BUCKET < MAX_BUCKET`: 1, 2, 2 per query (estimate 10.395), identical at every L.
This is direct runtime evidence of over-fetch by 1/FF: the index hands exactly n / 0.495 = 21 candidates to the
permission filter, and the search list size does not change that count. (Section explains do not print SRCHLSIZ; the
statement text of each activity carries the guideline, and EXPLAIN PLAN of the L = 200 text shows SRCHLSIZ 200.)

**Causal control: RCAC on, same 10 % set, permission written with a literal (`rcac_sweep.py litcopy`,
`eval/results/rcac_litcopy.json`, `rcac_raw/litcopy.log`).** Copy `NDL_DEV_RCAC.ADV_LIT (ADV_ID, ROW_BUCKET, EMB NOT NULL)`
of the 26,210 rows (INSERT ... SELECT in 10 committed batches), own vector index + RUNSTATS (66.5 s), SELECT granted to
NDL_P10 only, ACTIVATE ROW ACCESS CONTROL; NDL_P10 sees 2,621 rows (MAX(ROW_BUCKET) = 9); same 170 queries; recall
vs NDL_P10's own EXACT on the copy. The copy was dropped afterwards. (Different index build than ADV_DOC_VIX.)

| Permission on the copy (RCAC active) | APPROX 10 plan (EXPLAIN as DB2INST1) | FF | recall@10 | rows | under-fill |
|---|---|---|---|---|---|
| B: `ROW_BUCKET < 10` (literal) | IXSCAN VECIDX, SRCHLSIZ 102, est. 102 | 0.0989 | 0.765 | 8.66 | 0.38 |
| A: `SESSION_USER = 'NDL_P10' AND ROW_BUCKET < 10`, OR'ed with `SESSION_USER = 'DB2INST1'` | no vector index (TBSCAN) | 0.0438 | 1.000 (exact scan) | 10.00 | 0.00 |
| Reference: NEEDLE.ADV_DOC permission with the USER_ACCESS subquery (main sweep) | IXSCAN VECIDX, SRCHLSIZ 50, est. 21 | 0.495 | 0.205 | 2.05 | 1.00 |
| Reference: plain literal WHERE on ADV_DOC, no RCAC | IXSCAN VECIDX, SRCHLSIZ 90, est. 85 | 0.1179 | 0.682 | 7.77 | 0.62 |

With row access control still active and the same authorized set, writing the permission as a literal moves the
estimate to the true selectivity and under-fill shrinks to the literal-WHERE level (B), or the optimizer switches to an
exact table scan (A, a plan-selection outcome, not ANN recall). In B, APPROX 25 and 50 already ran as table scans
(recall 1.0, p50 16.8 / 19.2 ms). So the estimate, not RCAC or the size of the authorized set, sets the size of the
under-fill; with an accurate estimate 38 % of queries still under-fill (B). A literal per-user permission does not scale to many users (one permission per
user, OR'ed), which is why NEEDLE keeps the entitlement-table permission and routes outside the engine.

<!-- RESULTS: generated sections follow -->

## Generated tables (eval/rcac_report.py; "all" = all 170 queries unless the heading says held-out)

Db2 DB2 v12.1.5.0 | NEEDLE.ADV_DOC | k=10 | queries=170 (dev 81, heldout 89) | stats [['ADV_DOC', '26210', '2026-11-10 01:31:23.968119'], ['USER_ACCESS', '7', '2026-11-10 01:46:42.280438']] | auto_runstats=OFF

### Line-for-line: plain WHERE (DB2INST1, before RCAC) vs RCAC user, FETCH APPROX FIRST 10 (all queries)

| visible | WHERE literal: recall / rows / under-fill | plan (literal) | FF literal | WHERE subquery: recall / rows | plan (subquery) | RCAC user | RCAC: recall / rows / under-fill | RCAC plan (shared text) | FF permission | leaks |
|---|---|---|---|---|---|---|---|---|---|---|
| 10% (2616 rows) | 0.682 / 7.77 / 0.62 | IXSCAN VECIDX; L=90; est=85 | 0.1179 | 0.206 / 2.06 | IXSCAN VECIDX; L=50; est=21 | NDL_P10 | 0.205 / 2.05 / 1.00 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 25% (6570 rows) | 0.787 / 8.49 / 0.46 | IXSCAN VECIDX; L=60; est=39 | 0.2585 | 0.503 / 5.08 | IXSCAN VECIDX; L=50; est=21 | NDL_P25 | 0.502 / 5.08 / 0.97 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 50% (13001 rows) | 0.850 / 9.02 / 0.36 | IXSCAN VECIDX; L=50; est=21 | 0.4963 | 0.850 / 9.02 | IXSCAN VECIDX; L=50; est=21 | NDL_P50 | 0.848 / 9.00 / 0.36 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 75% (19632 rows) | 0.910 / 9.42 / 0.31 | IXSCAN VECIDX; L=50; est=14 | 0.7489 | 0.952 / 9.99 | IXSCAN VECIDX; L=50; est=21 | NDL_P75 | 0.952 / 9.99 / 0.01 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |
| 100% (26210 rows) | 0.950 / 10.00 / 0.00 | IXSCAN VECIDX; L=50; est=10 | n/a | n/a / n/a | n/a | NDL_SENIOR | 0.950 / 10.00 / 0.00 | IXSCAN VECIDX; L=50; est=21 | 0.495 | 0 |

### RCAC users: depth and search-list levers (recall / mean rows / under-fill rate / p50 ms; all queries)

| condition | plan as DB2INST1 | NDL_P10 | NDL_P25 | NDL_P50 | NDL_P75 | NDL_SENIOR |
|---|---|---|---|---|---|---|
| approx10 | IXSCAN VECIDX; L=50; est=21 | 0.205 / 2.0 / 1.00 / 2.1 | 0.502 / 5.1 / 0.97 / 2.1 | 0.848 / 9.0 / 0.36 / 2.1 | 0.952 / 10.0 / 0.01 / 3.0 | 0.950 / 10.0 / 0.00 / 2.4 |
| approx25 | IXSCAN VECIDX; L=68; est=51 | 0.493 / 5.2 / 0.94 / 3.3 | 0.857 / 12.8 / 0.21 / 2.6 | 0.953 / 23.5 / 0.00 / 2.7 | 0.973 / 25.0 / 0.00 / 3.9 | 0.971 / 25.0 / 0.00 / 3.1 |
| approx50 | IXSCAN VECIDX; L=102; est=102 | 0.729 / 10.3 / 0.44 / 3.5 | 0.944 / 25.8 / 0.00 / 3.5 | 0.978 / 48.1 / 0.00 / 3.7 | 0.984 / 50.0 / 0.00 / 4.7 | 0.978 / 50.0 / 0.00 / 4.6 |
| approx100 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 100.0 / 0.00 / 18.1 | 1.000 / 100.0 / 0.00 / 36.4 | 1.000 / 100.0 / 0.00 / 69.8 | 1.000 / 100.0 / 0.00 / 104.4 | 1.000 / 100.0 / 0.00 / 131.3 |
| approx200 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 200.0 / 0.00 / 17.9 | 1.000 / 200.0 / 0.00 / 37.1 | 1.000 / 200.0 / 0.00 / 67.8 | 1.000 / 200.0 / 0.00 / 112.8 | 1.000 / 200.0 / 0.00 / 140.6 |
| approx10_L50 | IXSCAN VECIDX; L=50; est=21 | 0.205 / 2.0 / 1.00 / 2.5 | 0.502 / 5.1 / 0.97 / 2.1 | 0.848 / 9.0 / 0.36 / 2.1 | 0.952 / 10.0 / 0.01 / 3.1 | 0.950 / 10.0 / 0.00 / 2.4 |
| approx25_L75 | IXSCAN VECIDX; L=75; est=51 | 0.497 / 5.2 / 0.93 / 4.0 | 0.872 / 12.8 / 0.19 / 2.7 | 0.959 / 23.5 / 0.00 / 2.8 | 0.974 / 25.0 / 0.00 / 3.4 | 0.971 / 25.0 / 0.00 / 4.1 |
| approx50_L150 | IXSCAN VECIDX; L=150; est=102 | 0.801 / 10.1 / 0.46 / 4.5 | 0.973 / 25.3 / 0.01 / 4.4 | 0.988 / 47.7 / 0.00 / 6.4 | 0.991 / 50.0 / 0.00 / 5.6 | 0.988 / 50.0 / 0.00 / 5.4 |
| approx100_L300 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 100.0 / 0.00 / 22.5 | 1.000 / 100.0 / 0.00 / 41.1 | 1.000 / 100.0 / 0.00 / 73.5 | 1.000 / 100.0 / 0.00 / 109.8 | 1.000 / 100.0 / 0.00 / 137.0 |
| approx200_L600 | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 200.0 / 0.00 / 21.9 | 1.000 / 200.0 / 0.00 / 42.0 | 1.000 / 200.0 / 0.00 / 72.7 | 1.000 / 200.0 / 0.00 / 123.7 | 1.000 / 200.0 / 0.00 / 134.8 |
| approx10_L200 | IXSCAN VECIDX; L=200; est=21 | 0.206 / 2.1 / 1.00 / 4.8 | 0.507 / 5.1 / 0.96 / 4.9 | 0.892 / 8.9 / 0.39 / 6.8 | 0.995 / 10.0 / 0.01 / 8.1 | 0.997 / 10.0 / 0.00 / 5.1 |
| exact | no vector index (TBSCAN); L=n/a; est=n/a | 1.000 / 10.0 / 0.00 / 16.6 | 1.000 / 10.0 / 0.00 / 36.2 | 1.000 / 10.0 / 0.00 / 66.8 | 1.000 / 10.0 / 0.00 / 109.8 | 1.000 / 10.0 / 0.00 / 145.8 |

### Oracle and identity checks

| user | SESSION_USER, CURRENT USER | visible rows | visible fraction | user EXACT == admin EXACT + explicit WHERE |
|---|---|---|---|---|
| NDL_P10 | ['NDL_P10', 'NDL_P10'] | 2616 | 0.0998 | 170 / 170 |
| NDL_P25 | ['NDL_P25', 'NDL_P25'] | 6570 | 0.2507 | 170 / 170 |
| NDL_P50 | ['NDL_P50', 'NDL_P50'] | 13001 | 0.496 | 170 / 170 |
| NDL_P75 | ['NDL_P75', 'NDL_P75'] | 19632 | 0.749 | 170 / 170 |
| NDL_SENIOR | ['NDL_SENIOR', 'NDL_SENIOR'] | 26210 | 1.0 | 170 / 170 |

### Router on the held-out split only (config fitted on dev: {'T': 7000, 'm': 3.0, 'depths': [10, 25, 50, 100, 200], 'guideline': True, 'fitted_on': 'dev split only (see router_fit)', 'evaluated_on': 'heldout split'})

| user | choice | recall@10 | mean rows | under-fill | EXACT fallbacks | errors | p50 ms | p95 ms | leaks | APPROX 10 on the same queries: recall / rows |
|---|---|---|---|---|---|---|---|---|---|---|
| NDL_P10 | EXACT 10 | 1.000 | 10.00 | 0.00 | 0 | 0 | 16.3 | 18.1 | 0 | 0.208 / 2.08 |
| NDL_P25 | EXACT 10 | 1.000 | 10.00 | 0.00 | 0 | 0 | 36.3 | 42.7 | 0 | 0.506 / 5.09 |
| NDL_P50 | APPROX 100, L=300 | 1.000 | 10.00 | 0.00 | 0 | 0 | 78.5 | 93.1 | 0 | 0.852 / 9.16 |
| NDL_P75 | APPROX 50, L=150 | 0.988 | 10.00 | 0.00 | 0 | 0 | 7.3 | 10.7 | 0 | 0.947 / 9.99 |
| NDL_SENIOR | APPROX 50, L=150 | 0.987 | 10.00 | 0.00 | 0 | 0 | 7.2 | 8.8 | 0 | 0.948 / 10.00 |

### Package cache after each user (FLUSH PACKAGE CACHE DYNAMIC before each order)

| order | after user | cache entries | executable_id (last 16 hex) | executions | +rows_read | +rows_returned |
|---|---|---|---|---|---|---|
| forward | NDL_P10 | 1 | 1110015942020530 | 10 (+10) | 35226 | 28 |
| forward | NDL_P25 | 1 | 1110015942020530 | 20 (+10) | 35226 | 53 |
| forward | NDL_P50 | 1 | 1110015942020530 | 30 (+10) | 35226 | 90 |
| forward | NDL_P75 | 1 | 1110015942020530 | 40 (+10) | 35226 | 100 |
| forward | NDL_SENIOR | 1 | 1110015942020530 | 50 (+10) | 35226 | 100 |
| forward | distinct executable ids | 1 | | | | |
| reverse | NDL_SENIOR | 1 | 1110015943844308 | 10 (+10) | 35226 | 100 |
| reverse | NDL_P75 | 1 | 1110015943844308 | 20 (+10) | 35226 | 100 |
| reverse | NDL_P50 | 1 | 1110015943844308 | 30 (+10) | 35226 | 90 |
| reverse | NDL_P25 | 1 | 1110015943844308 | 40 (+10) | 35226 | 53 |
| reverse | NDL_P10 | 1 | 1110015943844308 | 50 (+10) | 35226 | 28 |
| reverse | distinct executable ids | 1 | | | | |

### NEEDLE.TRIAGE_MODE(..., 'VEC') as each user, k = 10, 20 G1 queries

| user | depth 10: mean rows / queries < 10 | depth 100: mean rows / queries < 10 |
|---|---|---|
| NDL_P10 | 2.2 / 20 | 10.0 / 0 |
| NDL_P25 | 5.4 / 19 | 10.0 / 0 |
| NDL_P50 | 9.1 / 8 | 10.0 / 0 |
| NDL_P75 | 10.0 / 0 | 10.0 / 0 |
| NDL_SENIOR | 10.0 / 0 | 10.0 / 0 |

TRIAGE fused HYBRID statement, hybrid_depth10: IXSCAN VECIDX; L=50; est=21; operators ['1:RETURN', '2:TBSCAN', '3:SORT', '4:HSJOIN', '5:FILTER', '6:TBSCAN', '7:SORT', '8:FILTER', '9:GRPBY', '10:TBSCAN', '11:SORT', '12:HSJOIN', '13:NLJOIN', '14:FETCH', '15:IXSCAN', '16:IXSCAN', '17:NLJOIN', '18:NLJOIN', '19:TBSCAN', '20:TBSCAN', '21:TBSCAN', '22:TEMP', '23:TBSCAN', '24:SORT', '25:HSJOIN', '26:TBSCAN', '27:TBSCAN', '28:SORT', '29:TBSCAN', '30:TEMP', '31:UNION', '32:TBSCAN', '33:TBSCAN', '34:TBSCAN', '35:SORT', '36:TBSCAN', '37:SORT', '38:NLJOIN', '39:FETCH', '40:IXSCAN', '41:FETCH', '42:IXSCAN']

TRIAGE fused HYBRID statement, hybrid_depth100: no vector index (TBSCAN); L=n/a; est=n/a; operators ['1:RETURN', '2:TBSCAN', '3:SORT', '4:HSJOIN', '5:FILTER', '6:TBSCAN', '7:SORT', '8:FILTER', '9:GRPBY', '10:TBSCAN', '11:SORT', '12:HSJOIN', '13:NLJOIN', '14:FETCH', '15:IXSCAN', '16:IXSCAN', '17:NLJOIN', '18:NLJOIN', '19:TBSCAN', '20:TBSCAN', '21:TBSCAN', '22:TEMP', '23:TBSCAN', '24:SORT', '25:HSJOIN', '26:TBSCAN', '27:TBSCAN', '28:SORT', '29:TBSCAN', '30:TEMP', '31:UNION', '32:TBSCAN', '33:TBSCAN', '34:TBSCAN', '35:SORT', '36:TBSCAN', '37:SORT', '38:NLJOIN', '39:FETCH', '40:IXSCAN', '41:TBSCAN']

## Raw output

`docs/evidence/rcac_raw/`: real_baseline.log, real_rcac.log, real_router.log, plancache.log, triage_rcac.log, section_forward_0.txt / section_reverse_0.txt (EXPLAIN_FROM_SECTION + db2exfmt), apply_04_pre.log / apply_04_post.log (CLP output of sql/04_rcac.sql), pytest_db.log. JSON: eval/results/rcac_real_results.json, rcac_plancache.json, rcac_triage.json, rcac_router_fit.json, rcac_recall_vs_selectivity.json. Chart: eval/results/rcac_recall_vs_selectivity.png.
