# Notes for connector maintainers (observed on Db2 12.1.5.0 CE)

Thank you for the Db2 AI connectors (langchain-db2, ibm-db-haystack) and for the vector-index work in progress
(langchain-ai/langchain-ibm #342, deepset-ai/haystack-core-integrations #4086). We built NEEDLE on the same Db2
vector features and measured a few query shapes along the way. These notes share what we observed, in case it helps.

**Scope.** Db2 v12.1.5.0 Community Edition in a container (GitHub Codespace, 4 vCPU), database VECDB (32K pages).
Data: 26,210 OSV advisories, `VECTOR(768, FLOAT32)` from nomic-embed-text, COSINE distance. Libraries:
langchain-db2 1.0.0, ibm-db-haystack 1.0.0. PR heads read on 2026-11-09: langchain-ibm #342 `6ba3466`,
haystack-core-integrations #4086 `be86f6a` and #4217 `510a8fe`. Each number was measured once on this setup and
may differ on other builds, data sizes or configurations. Latency is wall-clock from python3 + ibm_db in the same
codespace (no network tunnel), unless a line says otherwise.

**Reproduce.** `scripts/connector_findings.sh <setup|f1|f2|f3f4|tempspace|writes|cleanup>` runs
`scripts/connector_findings.py` inside the codespace (password on stdin). The raw output of every step, with
EXPLAIN operator tables and db2exfmt access plans, is in `docs/evidence/connector_<step>.txt`. The tables are
copies of the same 26,210 vectors in schema NDL_CONN. The setup evidence was recorded with one
`INSERT ... SELECT` per copy; the script now copies in committed 2,000-row batches (same rows).

| # | Db2 behavior | What we observed | Suggested change |
|---|---|---|---|
| 1 | A nullable vector column makes the optimizer use exact search unless the query adds `IS NOT NULL` | Nullable copy: table scan, 71.2 ms. With `IS NOT NULL`: vector index, 2.4 ms | Create the column `NOT NULL` (as #4086 does) or add `embedding IS NOT NULL` |
| 2 | `FETCH APPROX FIRST ? ROWS ONLY` (k as a parameter marker) does not use the vector index | Parameter marker: table scan, 93.2 ms. Literal 10: vector index, 2.4 ms | Write a validated integer k as a literal; keep the vector bound |
| 3 | A metadata filter applied after `FETCH FIRST k` returns fewer than k rows | DB2VS, filter keeping 10 % of rows: 1.07 rows per query on average, recall@10 0.107 | Push the filter into SQL, e.g. `JSON_VALUE(metadata FORMAT BSON, ...)` |
| 4 | `WHERE` + `FETCH APPROX FIRST k` can return fewer than k rows; a deeper request lets the optimizer choose | depth 10: 7.6 rows, recall 0.663. depth 100: 10 rows, recall 1.000, 13 ms (exact filtered scan) | Request depth ≈ k / selectivity and keep the first k |
| 5 | `TRUNCATE` leaves a table with a vector index inaccessible until the index is dropped | `TRUNCATE TABLE ... IMMEDIATE`: SQL1477N; table readable again after `DROP INDEX` | In `clear_table()`, use `DELETE` or drop and recreate the index |
| 6 | `SYSTOOLS.BSON2JSON(metadata)` over a full scan holds system temporary space until the transaction ends | +26.8 MB of TEMPSPACE1 per DB2VS search; about 300 searches on one connection reached about 8 GB (SQL0968C) | Apply `BSON2JSON` to the top-k rows only, and/or commit after each search |
| 7 | Without `APPROX` or `EXACT`, the optimizer chooses index or scan by cost | Plain `FETCH FIRST 20` on an indexed NOT NULL copy: vector index (approximate) | Write `FETCH EXACT` or `FETCH APPROX` explicitly |

---

## 1. Nullable vector column: exact search unless the query adds `IS NOT NULL`

**Db2 documentation.** Db2 12.1 FETCH clause: "the optimizer chooses an EXACT search instead of using the index
if the key is a nullable vector." and "A VECTOR index can still be used if a NOT NULL predicate is included in
the query for the vector column." CREATE VECTOR INDEX: "A VECTOR index must be created on a non-nullable VECTOR
column to allow the optimizer to choose the index during a query."

**Connector context.** langchain-db2 1.0.0 creates `embedding vector({dim}, FLOAT32)` without `NOT NULL`
(`langchain_db2/db2vs.py:118`). langchain-ibm #342 adds `create_index()` and keeps that column definition.
ibm-db-haystack 1.0.0 also creates a nullable column (`document_store.py:277`) and adds `embedding IS NOT NULL`
to every search (`document_store.py:914`). haystack-core-integrations #4086 makes the column `NOT NULL` when
`create_vector_index=True`. Both approaches are consistent with the documentation lines above.

**What we observed.** We made two copies of the same 26,210 vectors and ran
`CREATE VECTOR INDEX ... WITH DISTANCE COSINE` on each. The index also builds on the nullable column (78.5 s;
67.8 s on the NOT NULL copy). Query: `SELECT ADV_ID FROM t [WHERE EMB IS NOT NULL] ORDER BY VECTOR_DISTANCE(EMB,
VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) FETCH APPROX FIRST 10 ROWS ONLY`, run for 20 query vectors.

| Table / predicate | Plan operators | Vector index | Cost | APPROX median | EXACT median | APPROX vs EXACT overlap@10 |
|---|---|---|---|---|---|---|
| nullable, no predicate | RETURN, TBSCAN, SORT, TBSCAN | not used | 3049.0 | 71.2 ms | 70.8 ms | 1.000 |
| nullable, `EMB IS NOT NULL` | RETURN, TBSCAN, SORT, FETCH, IXSCAN | used | 515.7 | 2.4 ms | 71.0 ms | 0.955 |
| NOT NULL, no predicate | RETURN, TBSCAN, SORT, FETCH, IXSCAN | used | 501.8 | 2.3 ms | 71.3 ms | 0.960 |
| NOT NULL, `EMB IS NOT NULL` | RETURN, TBSCAN, SORT, FETCH, IXSCAN | used | 501.8 | 2.3 ms | 71.5 ms | 0.960 |

- Statistics. After `RUNSTATS ON TABLE t FOR INDEXES ALL` (the statement #342 runs), the catalog showed
  CARD = 26,210. The plans were identical to those after `RUNSTATS ... WITH DISTRIBUTION AND INDEXES ALL`.
- On this build the redundant `IS NOT NULL` on a NOT NULL column left the plan unchanged, so either form works.

**Reproduce.** `scripts/connector_findings.sh setup` then `f1`. Evidence: `docs/evidence/connector_setup.txt`,
`docs/evidence/connector_f1.txt`.

**Suggested change.** When an index is intended, declare `embedding vector({dim}, FLOAT32) NOT NULL` in
`_create_table` (as #4086 does for Haystack), or add `WHERE embedding IS NOT NULL` to the search statement.

## 2. k as a parameter marker: the vector index is not used

**Db2 documentation.** Db2 12.1 FETCH clause: "Use of the fetch-clause with a constant for fetch-row-count that
is not greater than the maximum large integer [...] influences query optimization of the subselect or
fullselect." We did not find a sentence about parameter markers. The table below is what we measured.

**Connector context.** ibm-db-haystack 1.0.0 ends its search with `ORDER BY score ASC FETCH FIRST ? ROWS ONLY`
(`document_store.py:926`). #4086 creates the index and keeps this clause. On this build,
`FETCH APPROX FIRST ? ROWS ONLY` also falls back to a scan.

**What we observed.** Variants a, b, c2, d and e ran on the NOT NULL copy (vector index, full RUNSTATS).
Variants c1 and f ran on the nullable copy.

| Variant | Plan operators | Vector index | Cost |
|---|---|---|---|
| a) `FETCH APPROX FIRST 10 ROWS ONLY` | RETURN, TBSCAN, SORT, FETCH, IXSCAN | used | 501.8 |
| b) `FETCH APPROX FIRST ? ROWS ONLY` | RETURN, TBSCAN, SORT, FILTER, TBSCAN, SORT, TBSCAN | not used | 3059.2 |
| c1) Haystack 1.0.0 shape: nullable, `WHERE EMB IS NOT NULL ... FETCH FIRST ?` | RETURN, FILTER, TBSCAN, SORT, TBSCAN | not used | 3058.1 |
| c2) #4086 shape: NOT NULL, no predicate, `FETCH FIRST ?` | RETURN, TBSCAN, SORT, FILTER, TBSCAN, SORT, TBSCAN | not used | 3059.4 |
| d) c2 with `FETCH APPROX FIRST ?` | same as c2 | not used | 3059.4 |
| e) c2 with `FETCH APPROX FIRST 10` and `ORDER BY score` (alias) | RETURN, TBSCAN, SORT, FETCH, IXSCAN | used | 501.8 |
| f) c1 with `FETCH APPROX FIRST 10` (nullable + `IS NOT NULL`) | RETURN, TBSCAN, SORT, FETCH, IXSCAN | used | 515.7 |

Timing over 20 query vectors:
- a) median 2.4 ms (p95 2.6 ms).
- b) with `?` bound to 10: median 93.2 ms (p95 101.0 ms), 10 rows, the same results as an exact search.

The Haystack shapes were reproduced on our tables with `ADV_ID, EMB, score` in the select list; we left out the
`content` and `meta` columns.

**Reproduce.** `scripts/connector_findings.sh f2`. Evidence: `docs/evidence/connector_f2.txt`.

**Suggested change.** When a vector index exists, emit `FETCH APPROX FIRST {int(top_k)} ROWS ONLY`: validate
`top_k` as an integer and write it as a literal. Keep the query vector as a bound parameter.

## 3. Metadata filter applied after `FETCH FIRST k`: fewer than k rows

**Db2 behavior.** A `FETCH FIRST k` returns the k nearest rows of the whole table. A filter applied afterwards
keeps only the matching subset of those k rows. A predicate in the `WHERE` clause is applied before the fetch.

**Connector context.** langchain-db2 1.0.0 `similarity_search_by_vector_with_relevance_scores` runs
`ORDER BY distance FETCH FIRST {k} ROWS ONLY` (`db2vs.py:601-610`). It then applies `filter` in Python with
`metadata.get(key) in value` (`db2vs.py:621-633`). The MMR path does the same after `fetch_k` (`db2vs.py:666-713`).
ibm-db-haystack 1.0.0 translates filters into a SQL `WHERE` clause instead.

**What we observed.** We let `DB2VS.__init__` create the table, so the DDL came from the library
(`embedding vector(768, FLOAT32)`, nullable). We filled it with the same 26,210 rows; metadata is
`{adv_id, kind, row_bucket}`. We ran 150 query vectors with k = 10 and `filter={"row_bucket": [0..9]}`, which
keeps 2,621 rows (10 %). The reference is the exact filtered top-10 (`FETCH EXACT FIRST`) on the same vectors.

| Call | Rows returned, mean (min-max) | Queries with < 10 rows | Queries with 0 rows | recall@10 | Median latency |
|---|---|---|---|---|---|
| `similarity_search_by_vector(k=10, filter=...)` | 1.07 (0-6) | 150 / 150 | 66 / 150 | 0.107 | 266 ms |
| same with k=100, first 10 kept | 8.33 (1-10) | 69 / 150 | 0 | 0.833 | 269 ms |
| k=10, no filter (check of the copied table) | 10 | 0 | 0 | 0.997 (1.000 counting distance ties) | 263 ms |
| SQL: `WHERE JSON_VALUE(metadata FORMAT BSON, '$.row_bucket' RETURNING INTEGER) < 10 ... FETCH EXACT FIRST 10` | 10 | 0 of 5 probe queries | 0 | 1.0 (5 queries) | 237-290 ms through the tunnel |

Histogram of rows returned by the first call: 0: 66, 1: 35, 2: 32, 3: 11, 4: 3, 5: 2, 6: 1. The library's search
statement (captured from the cursor) plans as RETURN, TBSCAN, SORT, TBSCAN, with no vector index use, on the
library-created nullable column.

**Reproduce.** `scripts/connector_findings.sh f3f4`. Evidence: `docs/evidence/connector_f3f4.txt`,
`eval/results/db2vs_baseline.json` (per-query numbers), `docs/evidence/connector_f3_sql_filter_probe.txt`.

**Suggested change.** Translate `filter` into a SQL predicate. `JSON_VALUE(metadata FORMAT BSON, '$.key' ...)`
reads the stored BSON directly (verified above). Validate field names as #4217 does for Haystack.

## 4. `WHERE` + `FETCH APPROX FIRST k`: fewer than k rows, and how depth changes the plan

**Db2 documentation.** Db2 12.1 FETCH clause: "If a suitable vector index exists, then the Db2 query optimizer
considers the cost of using the index." We did not find a sentence about filtered approximate search returning
fewer rows. The table below is what we measured.

**Connector context.** This applies to a connector that adds `APPROX` to a search that also carries a `WHERE`
filter, for example Haystack filters or a filter pushed down as suggested in note 3.

**What we observed.** Same 150 queries, filter `ROW_BUCKET < 10` (10 %), on the NOT NULL copy with its index.
Reference: the exact filtered top-10.

| Statement | Plan | Rows returned, mean (min) | Queries with < 10 | recall@10 | Median latency |
|---|---|---|---|---|---|
| `WHERE ... FETCH APPROX FIRST 10` | IXSCAN on the vector index, cost 1806.0 | 7.60 (0) | 89 / 150 | 0.663 | 5.2 ms |
| `WHERE ... FETCH APPROX FIRST 100`, first 10 kept | TBSCAN (exact filtered scan), cost 3051.0 | 10 (10) | 0 | 1.000 | 13.4 ms |
| `WHERE ... FETCH APPROX FIRST 200`, first 10 kept | TBSCAN, cost 3051.0 | 10 (10) | 0 | 1.000 | 12.7 ms |
| `FETCH APPROX FIRST 100` in a subquery, `WHERE` outside, first 10 kept | IXSCAN, cost 2075.3 | 8.40 (0) | 67 / 150 | 0.706 | 5.2 ms |
| same with depth 200 | TBSCAN, cost 3073.0 | 9.95 (7) | 4 / 150 | 0.995 | 130.8 ms |

At depth 100 and 200 with the filter in the `WHERE` clause, the optimizer chose an exact filtered scan. That
scan reads the 10 % of rows that match, and it returned the exact top-10 in about 13 ms. No statement raised an
error in these runs, at depth 100 or 200.

**Reproduce.** `scripts/connector_findings.sh f3f4`. Evidence: `docs/evidence/connector_f3f4.txt`
(EXPLAIN of every statement).

**Suggested change.** When a filter is present, request depth ≈ k / selectivity in the `WHERE` form and keep the
first k rows. Db2 then picks the index or the filtered scan by cost.

## 5. `TRUNCATE` on a table with a vector index

**Db2 documentation.** CREATE VECTOR INDEX: "TRUNCATE leaves the table inaccessible until all vector indexes are
dropped." and "LOAD cannot be run against a table with a vector index."

**Connector context.** langchain-db2 1.0.0 `clear_table()` runs `TRUNCATE TABLE {table_name} IMMEDIATE`
(`db2vs.py:202`). #342 adds `create_index()` / `drop_index()` on the same table. ibm-db-haystack 1.0.0
`delete_all_documents()` uses `DELETE FROM` (`document_store.py:549`).

**What we observed.** We used a 2,000-row table with a vector index (build 5.0 s) and
`RUNSTATS ... FOR INDEXES ALL`.
- `INSERT`, `UPDATE` of the vector, and `DELETE` of one row each succeeded.
- `TRUNCATE TABLE ... IMMEDIATE` returned `SQL1477N For table "NDL_CONN.F5_WRITES" an object "41" in table space
  "2" cannot be accessed.`
- A following `SELECT COUNT(*)` and `INSERT` returned the same SQL1477N.
- After `DROP INDEX`, `SELECT COUNT(*)` returned 0, so the truncate had taken effect.

**Reproduce.** `scripts/connector_findings.sh writes`. Evidence: `docs/evidence/connector_writes.txt`.

**Suggested change.** In `clear_table()`, use `DELETE FROM` when the table has a vector index. Alternatively,
drop the index before `TRUNCATE` and recreate it afterwards.

## 6. `SYSTOOLS.BSON2JSON(metadata)` over a full scan holds temporary space until the transaction ends

**Db2 behavior.** We did not find a documentation line for this; it is observed behavior only.

**Connector context.** The DB2VS search statement selects `SYSTOOLS.BSON2JSON(metadata)` in the same query block
as the full scan and sort (`db2vs.py:601-610`). The search methods do not commit. `ibm_db_dbi` connections start
with autocommit off (we read `0` from the connection). ibm-db-haystack 1.0.0 selects
`SYSTOOLS.BSON2JSON(meta)` in its search statement as well (`document_store.py:921`); we did not measure Haystack.

**What we observed.** TEMPSPACE1 (SMS) container size was measured with `du`, 8 DB2VS searches (k = 10) on one
connection:
- start: 8,704 bytes;
- after search 1: 26,847,744 bytes;
- after search 8: 214,721,024 bytes (+26.8 MB per search, about 1 KB per row);
- after `commit()`: 8,704 bytes.

| Same statement, 4 executions in one transaction | Temporary space added |
|---|---|
| as executed by DB2VS (`id, text, SYSTOOLS.BSON2JSON(metadata), distance`) | +107,356,160 bytes |
| `metadata` returned as the raw BLOB | +0 |
| `id, distance` only | +0 |
| `BSON2JSON` applied in an outer query over the `FETCH FIRST 10` subquery | +0 |

In our first F3 run, about 300 DB2VS searches on one connection grew a temporary file to about 8 GB. Db2 then
returned `SQL0968C The file system is full`; db2diag recorded the write at offset 8,036,626,432. The space was
released when the connection ended.

**Reproduce.** `scripts/connector_findings.sh tempspace`. Evidence: `docs/evidence/connector_tempspace.txt`,
`docs/evidence/connector_f3f4_run1_disk_full.txt`, `docs/evidence/connector_f3f4_run1_db2diag.txt`.

**Suggested change.** Apply `BSON2JSON` to the top-k rows only: wrap the `ORDER BY ... FETCH FIRST k` query in an
outer `SELECT` (measured +0 above). Also commit, or document that callers should commit, after each search.

## 7. `FETCH FIRST` without `APPROX` or `EXACT`: the optimizer chooses

**Db2 documentation.** Db2 12.1 FETCH clause: "When a query omits both the APPROX and EXACT options, Db2
determines the search method automatically: If a suitable vector index exists, then the Db2 query optimizer
considers the cost of using the index. If the cost of using the index is lower than that of running an exact
search, Db2 uses the index."

**Connector context.** DB2VS writes `FETCH FIRST {k} ROWS ONLY` with a literal k (`db2vs.py:609`); the code
comment at `db2vs.py:611-613` anticipates `APPROX`. On today's nullable column this plans as an exact scan. If
the column becomes `NOT NULL` and an index exists (notes 1 and #342), the same statement can use the index.

**What we observed** (NOT NULL copy with its index, 768-dim, k = 20):

| Statement | Plan | Cost |
|---|---|---|
| `ORDER BY distance FETCH FIRST 20 ROWS ONLY` | RETURN, TBSCAN, SORT, FETCH, IXSCAN (vector index) | 640.9 |
| same with `FETCH EXACT FIRST 20` | RETURN, TBSCAN, SORT, TBSCAN | 3049.2 |
| `WHERE ROW_BUCKET < 10 ... FETCH FIRST 20 ROWS ONLY` | RETURN, TBSCAN, SORT, TBSCAN | 3050.9 |

We met this in our own harness. Run 2 of step f3f4 used plain `FETCH FIRST` for its unfiltered reference, and it
agreed with an exact search on 0.951 of the top-10 (`docs/evidence/connector_f3f4_run2_plain_fetch_gt.txt`).
With `FETCH EXACT` (run 3) the agreement was 0.997, or 1.000 counting distance ties.

**Suggested change.** Write `FETCH EXACT FIRST` where exact results are intended and `FETCH APPROX FIRST` where
the index is intended.

---

## Other observations

- **Inlined query vector.** DB2VS writes the vector into the SQL text (`db2vs.py:605`). 450 searches produced 300
  distinct statement texts. Each new vector is a new statement to compile, and the package cache held 229 DB2VS
  entries after our runs. The bound ground-truth statement used 2 entries for 150 executions. Binding the vector
  as `VECTOR(CAST(? AS CLOB(100K)), dim, FLOAT32)` (as ibm-db-haystack does) gives one reusable statement.
- **Embedding call per search.** `get_embedding_dimension()` embeds the probe text on every search
  (`db2vs.py:599`), every `add_texts` (`db2vs.py:471`) and every MMR call (`db2vs.py:664`). A counting stub saw
  exactly 1 extra embedding call per search. Caching the dimension at construction would remove that model call.
- **Index builds and the notify log.** We ran CREATE VECTOR INDEX 4 times; no new ADM13500E entries were logged
  (count 10 before and after each build). The builds logged ADM5530W entries (NOT LOGGED INITIALLY commit) for
  internal `SYSIBM.AIJ…`, `ACV…` and `AMD…` tables.
- **SQL0901N at `FETCH APPROX FIRST 100`.** Another part of our project saw this on its own table for one query
  vector (`docs/evidence/eval_sql0901n_fetch_approx.md`). It did not occur on these copies, which have separate
  index builds, for the 150 queries at depth 100 or 200.

We have not opened issues or pull requests for any of these notes.
