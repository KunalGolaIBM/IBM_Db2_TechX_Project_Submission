# NEEDLE references (verified)

Owner: SOURCES agent. Verified date for every entry in sections 1 to 7: **2026-11-09** (fetched in this session).
Rule: an entry is listed as verified only if the page was fetched in this session and it states the fact noted.
Pages that failed, were blocked, or were not re-fetched are in section 8 (UNVERIFIED).
Format: title — URL — fact it supports — verified date.

Counts: **75 verified** URLs (sections 1 to 7), **42 unverified** URLs plus 3 topics with no source found (section 8).

---

## 1. IBM Db2 12.1.x documentation

### 1.1 VECTOR type and functions
1. Vector values — https://www.ibm.com/docs/en/db2/12.1.x?topic=list-vector-values — Coordinate types INT8 and REAL/FLOAT32. Row-organized dimension 1 to 8168 (FLOAT32) or 1 to 32672 (INT8); column-organized 1 to 8148 / 1 to 32592. "The only DEFAULT value allowed is NULL, consequently a NOT NULL vector column cannot be added to an existing table." Vectors cannot be compared (no ORDER BY / GROUP BY / keys on the column). The page contradicts itself on LOAD ("LOAD and INGEST operations do not support vectors" vs "The LOAD command supports the VECTOR data type in Db2 12.1.3 and later"). — 2026-11-09
2. VECTOR_DISTANCE — https://www.ibm.com/docs/en/db2/12.1.x?topic=functions-vector-distance — Signature `VECTOR_DISTANCE(vector1, vector2, metric)`, result DOUBLE. Metrics: COSINE, EUCLIDEAN, EUCLIDEAN_SQUARED, DOT, HAMMING, MANHATTAN. "The result is the null value when either VECTOR argument is NULL." Both vectors must have the same coordinate type and dimension. — 2026-11-09
3. VECTOR_SERIALIZE — https://www.ibm.com/docs/en/db2/12.1.x?topic=functions-vector-serialize — Converts a vector to a string; optional `RETURNING VARCHAR(n)` / `CLOB(n)`. Default result: FLOAT32 with D ≤ 2041 returns VARCHAR of length D×16+1 (768 dims → VARCHAR(12289)). Example `SELECT VECTOR_SERIALIZE(RVECTOR) as VECTOR FROM VECTOR_TB FETCH FIRST 1 ROWS ONLY`. — 2026-11-09

### 1.2 Vector index
4. Vector indexes (overview) — https://www.ibm.com/docs/en/db2/12.1.x?topic=indexes-vector — "Vector index support is available in Db2 12.1.5 and later on LinuxAMD64 platforms." Implementation "inspired by DiskANN". Db2 "defaults to approximate search if a suitable index exists". Search stages include an insert journal check; query speed degrades as the journal grows, so the index must be recreated periodically. No text on WHERE predicates, filters or row permissions. — 2026-11-09
5. ANN index implementation — https://www.ibm.com/docs/en/db2/12.1.x?topic=indexes-ann-index-implementation — Graph table with one row per vector (node ID, RID to base table, neighbors) plus a Product Quantization compressed-vectors table. Lists "You can filter the search space significantly with other predicates" as a case where an index may not be needed. No text on pre-filter, post-filter or fewer than k rows. — 2026-11-09
6. CREATE VECTOR INDEX — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-create-vector-index — Linux AMD64 only, 12.1.5+, not DPF, not pureScale. Row-organized, non-partitioned tables only. One vector column; FLOAT32 or INT8; COSINE requires FLOAT32. `WITH DISTANCE` COSINE, EUCLIDEAN or EUCLIDEAN_SQUARED. Column should be NOT NULL for the optimizer to choose the index (a NOT NULL predicate can substitute). Index used only if the query metric matches. Key must fit one quarter of a page: FLOAT32 max dims 4K→256, 8K→512, **16K→1024**, 32K→2048 (so 768-dim FLOAT32 needs at least a 16K page). LOAD on the table fails (SQL6104N). REORG of any index on the table fails (SQL0270N reason code 137). TRUNCATE makes the table inaccessible (SQL1477N) until vector indexes are dropped. Tuning clauses: BUILD_MEM_BUDGET, BUILD_LIST_SIZE, BUILD_PARALLELISM, MAX_NODE_DEGREE, PCT_COMP_VECT_SIZE, PCT_NODES_TO_CACHE. No read-only restriction is stated. — 2026-11-09
7. fetch-clause (APPROX / EXACT) — https://www.ibm.com/docs/en/db2/12.1.x?topic=subselect-fetch-clause — APPROX and EXACT are mutually exclusive. With neither keyword, the optimizer costs the index and uses it if cheaper. Without statistics "such as those collected by RUNSTATS", "Db2 resorts to EXACT search, even when a valid index is present." Metric must exactly match `WITH DISTANCE`. For nullable vector columns the optimizer chooses EXACT "even when the query includes the APPROX clause"; "A VECTOR index can still be used if a NOT NULL predicate is included in the query for the vector column." COSINE + APPROX normalizes query vectors. Silent on parameter markers and on other WHERE predicates. — 2026-11-09
8. Db2 12.1.5 highlights — https://www.ibm.com/docs/en/db2/12.1.x?topic=1215-highlights-db2 — Vector indexes use "a graph-based Approximate Nearest Neighbor (ANN) algorithm inspired by DiskANN". Also: API-key auth extended to OpenAI-compatible LLM providers. No restrictions listed on this page. — 2026-11-09

### 1.3 Statistics and plans
9. RUNSTATS — https://www.ibm.com/docs/en/db2/12.1.x?topic=commands-runstats — `RUNSTATS ON TABLE ... AND INDEXES ALL` form (example `RUNSTATS ON TABLE employee AND INDEXES ALL TABLESAMPLE SYSTEM(1.5)`). The page has no vector-specific text. — 2026-11-09
10. EXPLAIN statement — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-explain — `EXPLAIN PLAN SELECTION | ALL | PLAN [WITH SNAPSHOT] FOR explainable-sql-statement`. "The explain tables must be created by the user before invocation"; falls back to SYSTOOLS schema tables. Example 4 fails with SQLSTATE 42704 if tables are missing. — 2026-11-09
11. db2exfmt — https://www.ibm.com/docs/en/db2/12.1.x?topic=commands-db2exfmt-explain-table-format — Options `-d` database, `-1` defaults (`-e % -n % -s % -v % -w -1 -# 0`), `-o` output file, `-g` graph, `-w -1` latest explain. — 2026-11-09

### 1.4 RCAC
12. CREATE PERMISSION — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-create-permission — `FOR ROWS WHERE search-condition ENFORCED FOR ALL ACCESS ENABLE`; default is DISABLE. Requires SECADM. "An enabled row permission does not take effect until the ALTER TABLE statement with the ACTIVATE ROW ACCESS CONTROL clause is used". Example uses `VERIFY_ROLE_FOR_USER(SESSION_USER,'CSR') = 1`. — 2026-11-09
13. CREATE MASK — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-create-mask — `CREATE [OR REPLACE] MASK name ON table [AS corr] FOR COLUMN col RETURN case-expression ENABLE`. Requires SECADM. Takes effect only after `ALTER TABLE ... ACTIVATE COLUMN ACCESS CONTROL`. — 2026-11-09
14. ALTER TABLE — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-alter-table — ACTIVATE ROW ACCESS CONTROL: "A default row permission is implicitly created and allows no access to any rows of the table" unless a SECADM-created permission allows it. SECADM needed to activate or deactivate. Syntax includes ADD PERIOD BUSINESS_TIME. — 2026-11-09
15. Row permissions (ExampleHMO scenario) — https://www.ibm.com/docs/en/db2/12.1.x?topic=control-row-permissions — Worked example `CREATE PERMISSION ROW_ACCESS ON PATIENT ... ENFORCED FOR ALL ACCESS ENABLE;` then `ALTER TABLE PATIENT ACTIVATE ROW ACCESS CONTROL;`. — 2026-11-09
16. RCAC scenario index (ExampleHMO) — https://www.ibm.com/docs/en/db2/12.1.x?topic=rcac-scenario-examplehmo-using-row-column-access-control — Found in search results only; see section 8. (Not counted as verified.)
17. SESSION_USER — https://www.ibm.com/docs/en/db2/12.1.x?topic=registers-session-user — "the current runtime authorization ID that is being used for the current session"; initial value equals SYSTEM_USER; changed by SET SESSION AUTHORIZATION; synonym for USER. — 2026-11-09

### 1.5 Application-period temporal tables
18. Application-period temporal tables — https://www.ibm.com/docs/en/db2/12.1.x?topic=tables-application-period-temporal — "a table that stores the in effect aspect of application data". — 2026-11-09
19. Creating an application-period temporal table — https://www.ibm.com/docs/en/db2/12.1.x?topic=aptt-creating — Example `policy_info` with `bus_start DATE NOT NULL, bus_end DATE NOT NULL, PERIOD BUSINESS_TIME(bus_start, bus_end), PRIMARY KEY(policy_id, BUSINESS_TIME WITHOUT OVERLAPS)`. — 2026-11-09
20. Querying application-period temporal data — https://www.ibm.com/docs/en/db2/12.1.x?topic=aptt-querying — `FOR BUSINESS_TIME AS OF '2008-07-15'`, `FROM ... TO ...`, `BETWEEN ... AND ...`. "The begin-column of a period is inclusive, while the end-column is exclusive." — 2026-11-09

### 1.6 JSON, XML and SQL PL
21. JSON_TABLE (12.1) — https://www.ibm.com/docs/en/db2/12.1.x?topic=functions-json-table — Grammar: `JSON_TABLE(JSON-expression [FORMAT JSON | FORMAT BSON], 'strict $' COLUMNS(col-def, ...) [ERROR ON ERROR])`. The row path appears in the diagram only as the literal `'strict $'`. Column default path is `'$.'` + column name. No NESTED, no ordinality. Example: `FROM EMPLOYEE_TABLE E JSON_TABLE(E.jsondoc, 'strict $' COLUMNS("id" INTEGER, ...) ERROR ON ERROR) AS U` (the page omits the comma between `E` and `JSON_TABLE`). Untyped parameter markers give SQLSTATE 42815. See the finding in `research/sources_findings.md`. — 2026-11-09
22. JSON_TABLE (11.5) — https://www.ibm.com/docs/en/db2/11.5.x?topic=functions-json-table — Same grammar and same example as 12.1; same "one or more rows" sentence. — 2026-11-09
23. JSON_VALUE — https://www.ibm.com/docs/en/db2/12.1.x?topic=functions-json-value — `JSON_VALUE(expr, sql-json-path-expression [RETURNING type] [... ON EMPTY] [... ON ERROR])`. The path is "An expression that returns a value that is a built-in character string data type". Cannot be schema-qualified. Example `JSON_VALUE('{"id":"987"}', 'strict $.id' RETURNING INTEGER)`. Array subscripts are not documented. — 2026-11-09
24. XMLTABLE — https://www.ibm.com/docs/en/db2/12.1.x?topic=functions-xmltable — `XMLTABLE('$po/PurchaseOrder/item' PASSING P.PORDER AS "po" COLUMNS ... PATH '...') AS U` returns one row per repeating element. — 2026-11-09
25. DECLARE CURSOR — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-declare-cursor — `WITH RETURN [TO CALLER | TO CLIENT]` returns a result set from a procedure; `FOR statement-name` uses a prepared statement, which must be prepared before OPEN. — 2026-11-09
26. OPEN — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-open — `OPEN cursor USING var-or-expression, ...`: "each parameter marker in the statement is effectively replaced by its corresponding host variable." — 2026-11-09
27. PREPARE — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-prepare — `PREPARE stmt FROM host-variable | expression`; typed markers `CAST(? AS data-type)`; untyped `?` needs derivable type (else SQLSTATE 42610). — 2026-11-09
28. Returning result sets from SQL procedures — https://www.ibm.com/docs/en/db2/12.1.x?topic=procedures-returning-result-sets-from-sql — `DYNAMIC RESULT SETS 1`, `DECLARE c CURSOR WITH RETURN FOR ...`, `OPEN c;` and leave it open, or the result set is not returned. — 2026-11-09
29. DECLARE GLOBAL TEMPORARY TABLE — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-declare-global-temporary-table — "A user temporary table space must exist before a declared temporary table can be declared (SQLSTATE 42727)." Qualifier must be SESSION (SQLSTATE 428EK). `ON COMMIT PRESERVE ROWS`, `NOT LOGGED`, `WITH REPLACE`. — 2026-11-09
30. MERGE — https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-merge — `MERGE INTO archive ar USING (SELECT ...) ac ON (...) WHEN MATCHED THEN UPDATE SET ... WHEN NOT MATCHED THEN INSERT (...) VALUES (...)`. No RCAC note on the page. — 2026-11-09

---

## 2. IBM blogs and community

31. Vector Indexes in Db2 – An early preview (Garcia-Arellano, Hoggard, Stojanovski; URL dated 2025-10-04, posted 10/06/25) — https://community.ibm.com/community/user/blogs/christian-garcia-arellano/2025/10/04/vector-indexes-in-db2-an-early-preview — EAP example `CREATE VECTOR INDEX SIFT_EUCLIDEAN ON SIFT_BASE (EMBEDDING) WITH DISTANCE EUCLIDEAN;` + RUNSTATS + `FETCH APPROX FIRST 10 ROWS ONLY`. EAP limits: "A table with a vector index becomes read-only", no new indexes after the vector index, offline Z-lock build, Euclidean only, non-nullable column, AVX2. Suggests ordinary indexes on filter columns to shrink the vector set. Comment (05/21/26): feature ships in 12.1.5. — 2026-11-09
32. Vector Indexes in Db2 – Understanding the search accuracy vs speed tradeoffs (Garcia-Arellano et al., 2026-02-09) — https://community.ibm.com/community/user/blogs/christian-garcia-arellano/2026/02/09/vector-indexes-in-db2-understanding-the-search-acc — SEARCH_LIST_SIZE L default 50, SEARCH_BEAM_WIDTH W default 2. Guideline `/* <OPTGUIDELINES> <IXSCAN TABLE='VD1' SEARCH_LIST_SIZE='100'/> </OPTGUIDELINES> */`. 10M × 768-dim FLOAT32: L=10 ≈ 68% recall, L=50 ≈ 90%, L=100 ≈ 97%. No text on filters. — 2026-11-09
33. Vector Indexes in Db2 – Mastering Vector Index Performance (Garcia-Arellano, Hoggard, Stojanovski; 2026-06-19) — https://community.ibm.com/community/user/blogs/zach-hoggard/2026/06/19/vector-indexes-in-db2-mastering-vector-index-perfo — PCT_COMP_VECT_SIZE 5% → 15%: +8% query performance, recall change under 1%. BUILD_PARALLELISM AUTOMATIC uses up to 50% of cores; BUILD_MEM_BUDGET default 1 GB from UTIL_HEAP. Dedicated tablespace/bufferpool for `COMPRESSED VECTORS IN`. No text on filters. — 2026-11-09
34. Db2 12.1.3 Vector Features for AI Builders (Shaikh Quader, 2025-11-18) — https://community.ibm.com/community/user/blogs/shaikh-quader/2025/11/18/db2-12113-vector-features-for-ai-builders — 12.1.3 (Mod Pack 3): "The LOAD command now supports VECTOR columns"; VECTOR in SQL functions and procedures; ADMIN_MOVE_TABLE, db2move, external tables handle vectors; native LangChain and LlamaIndex packages. — 2026-11-09
35. Persistent AI Agent Memory on Db2 12.1.5 VECTOR — mnemos Quick Start (Jason Perlow, 2026-07-07) — https://community.ibm.com/community/user/blogs/jason-perlow/2026/07/07/persistent-ai-agent-memory-on-db2-1215-vector-mnem — Practitioner report: `USING HNSW` / `USING DISKANN` return SQL0104N on 12.1.5; SEARCH_LIST_SIZE knobs also reported as SQL0104N on the tested build (form used not shown). Query uses `embedding IS NOT NULL`. No EXPLAIN shown. Garcia-Arellano replied offering help. Secondary source only. — 2026-11-09
36. IBM Db2 12.1.5 is Here — My Personal Highlights (Iqbal Goralwalla, Triton, 2026-07-20) — https://www.triton.co.uk/ibm-db2-12-1-5-is-here-my-personal-highlights/ — "12.1.5 fixes that with DiskANN-powered vector indexes"; index need not stay fully in memory. Third-party. — 2026-11-09
37. Using dynamic SQL inside SQL PL (Serge Rielau, 2020-03-09) — https://community.ibm.com/community/user/viewdocument/using-dynamic-sql-inside-sql-pl?CommunityKey=ea909850-39ea-4ac4-9512-8e2eb37ea09a&tab=librarydocuments — Pattern: `DECLARE stmt STATEMENT; DECLARE cur CURSOR FOR stmt; ... PREPARE stmt FROM text; OPEN cur USING 15;`. — 2026-11-09
38. Problems using JSON_TABLE on Db2 v11.5 (community thread, 2023-06) — https://community.ibm.com/community/user/discussion/problems-using-json-table-on-db2-v115 — `nested path 'strict $.array[*]'` fails with SQL0104N; Mark Barinstein: LUW "doesn't support the `nested path` json expression", has "never seen any example" where `SYSIBM.JSON_TABLE` returns multiple rows, calls the doc sentence "a mistake". No working fix in thread. — 2026-11-09

---

## 3. Filtered ANN research and vendor docs

39. Filtered-DiskANN: Graph Algorithms for Approximate Nearest Neighbor Search with Filters — Crossref record https://api.crossref.org/works/10.1145/3543507.3583552 — Gollapudi, Karia, Sivashankar, Krishnaswamy, Begwani, Raz, Lin, Zhang, Mahapatro, Srinivasan, Singh, Simhadri; Proceedings of the ACM Web Conference 2023, pp. 3406–3416. Cite DOI 10.1145/3543507.3583552. (Metadata only; paper text not read, ACM page 403.) — 2026-11-09
40. ACORN: Performant and Predicate-Agnostic Search Over Vector Embeddings and Structured Data — https://arxiv.org/abs/2403.04871 — Patel, Kraft, Guestrin, Zaharia; existing hybrid methods "suffer from poor performance or support a severely restricted set of search predicates." — 2026-11-09
41. ACORN venue — https://api.crossref.org/works/10.1145/3654923 — Proceedings of the ACM on Management of Data, vol. 2, issue 3, 2024 (the SIGMOD 2024 journal track). Cite DOI 10.1145/3654923. — 2026-11-09
42. ACORN code — https://github.com/stanford-futuredata/ACORN — README: "ACORN is an index for state-of-the-art search over vector embeddings and structured data (SIGMOD '24)". — 2026-11-09
43. DiskANN: Fast Accurate Billion-point Nearest Neighbor Search on a Single Node — https://papers.nips.cc/paper/2019/hash/09853c7fb1d3f8ee67a61b6bf4a7f8e6-Abstract.html — Subramanya, Devvrit, Simhadri, Krishnaswamy, Kadekodi; NeurIPS 2019; indexes "a billion point database on a single workstation with just 64GB RAM" plus SSD. — 2026-11-09
44. microsoft/DiskANN — https://github.com/microsoft/DiskANN — Reference implementation; links the Filtered-DiskANN paper PDF and the NeurIPS'19 paper. — 2026-11-09
45. pgvector README — https://github.com/pgvector/pgvector — "With approximate indexes, filtering is applied after the index is scanned." "If a condition matches 10% of rows, with HNSW and the default `hnsw.ef_search` of 40, only 4 rows will match on average." Iterative index scans since 0.8.0 (`hnsw.iterative_scan` strict_order / relaxed_order; `hnsw.max_scan_tuples` default 20,000). — 2026-11-09
46. Filtering in Vector Search: When to Use What (Qdrant) — https://qdrant.tech/articles/vector-search-filtering/ — Post-filtering: "If many of the top results fail, you get fewer results than you asked for." Pre-filtering is exact but expensive. Combined filters: matching points "may not be connected in the graph, and recall drops." Filterable HNSW adds per-field edges. — 2026-11-09
47. Weaviate filtering concepts — https://docs.weaviate.io/weaviate/concepts/filtering — Post-filtering: "there is a chance that the original vector search does not contain any match at all." ACORN strategy: non-matching objects "are ignored in distance calculations"; useful "when the filter has low correlation with the query vector." — 2026-11-09
48. VECTOR_SEARCH (Transact-SQL), Microsoft — https://learn.microsoft.com/sql/t-sql/functions/vector-search-transact-sql — Closest relational-DB analogue. Earlier DiskANN index versions: "Post-filtering only ... If none of the 10 rows ... have the `accepted` column equal to 1, the result is empty." Latest version: "Iterative filtering: Predicates in the WHERE clause are applied during the vector search process". Shows that the post-filter failure is real in a shipping DiskANN-based SQL engine. — 2026-11-09

---

## 4. Retrieval

49. The Probabilistic Relevance Framework: BM25 and Beyond — Crossref record https://api.crossref.org/works/10.1561/1500000019 — Robertson and Zaragoza, Foundations and Trends in Information Retrieval, 2009. Cite DOI 10.1561/1500000019. Note: a search snippet of the publisher page gives vol. 3 no. 4 pp. 333–389, while the Crossref record returned different volume/page metadata; cite by DOI and year only. — 2026-11-09
50. Reciprocal rank fusion outperforms Condorcet and individual rank learning methods — Crossref record https://api.crossref.org/works/10.1145/1571941.1572114 — Cormack, Clarke, Buettcher; SIGIR 2009 proceedings, pp. 758–759. Cite DOI 10.1145/1571941.1572114. — 2026-11-09
51. Elasticsearch reciprocal rank fusion — https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion — Formula `score += 1.0 / ( k + rank( result(q), d ) )`, rank starts at 1, `rank_constant` "Defaults to `60`"; links the Cormack SIGIR'09 PDF. Use this for the k=60 convention. — 2026-11-09
52. nomic-embed-text-v1.5 model card — https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 — Prompt "must include a task instruction prefix": `search_query`, `search_document`, `clustering`, `classification`. Output 768 dims; Matryoshka 512/256/128/64. 8192-token sequence length. Apache-2.0. — 2026-11-09
53. Ollama library: nomic-embed-text — https://ollama.com/library/nomic-embed-text — Tags 274MB; tag table lists a "2K context window" (differs from the HF 8192); quick start uses `POST /api/embed`. The page does not state dims or prefixes. — 2026-11-09

---

## 5. Data and standards

54. OSV schema 1.9.2 — https://ossf.github.io/osv-schema/ — `aliases`: IDs of the same vulnerability in other databases. `withdrawn`: RFC3339 timestamp; missing means not withdrawn. `affected[].package` requires `ecosystem` and `name` (optional `purl`). `ranges[].type` SEMVER / ECOSYSTEM / GIT; events `introduced` / `fixed` / `last_affected` / `limit`, one key per event, at least one `introduced`. "A version is considered affected if it lies within any one of the ranges or is listed in the versions list." PyPI `name` is PEP 503-normalized. — 2026-11-09
55. OSV.dev data sources and dumps — https://google.github.io/osv.dev/data/ — `gs://osv-vulnerabilities/<ECOSYSTEM>/all.zip`; HTTP form https://storage.googleapis.com/osv-vulnerabilities/PyPI/all.zip; `all.zip` includes withdrawn records. Licenses are per source: GitHub Advisory Database CC-BY 4.0; PyPI Advisory Database (pypa/advisory-database, the PYSEC source) CC-BY 4.0; PSF Advisory Database CC-BY 4.0; OpenSSF Malicious Packages (MAL-*) Apache 2.0. No single OSV-wide license is stated; attribute each source. — 2026-11-09
56. PEP 503 — https://peps.python.org/pep-0503/ — Normalized name: lowercase, runs of `.`, `-`, `_` → single `-`: `re.sub(r"[-_.]+", "-", name).lower()`. — 2026-11-09
57. PEP 440 — https://peps.python.org/pep-0440/ — Public version scheme `[N!]N(.N)*[{a|b|rc}N][.postN][.devN]`; alternative spellings must be normalized. Status Final; canonical spec now on the PyPA specs page. — 2026-11-09
58. CycloneDX specification overview — https://cyclonedx.org/specification/overview/ — SBOM standard, current version 1.7, published as ECMA-424. — 2026-11-09
59. SPDX overview — https://spdx.dev/about/overview/ — "an open standard for communicating software bill of material information"; ISO/IEC 5962:2021. — 2026-11-09
60. OSV record PYSEC-2020-96 — https://osv.dev/vulnerability/PYSEC-2020-96 — Aliases CVE-2020-1747 and GHSA-6757-jp84-gxfx; PyPI/pyyaml ECOSYSTEM range introduced 5.1, fixed 5.3.1; enumerated versions 5.1 … 5.3; no severity field on the record. — 2026-11-09

---

## 6. Frameworks and connectors

61. LangChain BaseRetriever reference — https://reference.langchain.com/python/langchain-core/retrievers/BaseRetriever — Subclasses "should implement the `_get_relevant_documents` method"; retrievers are Runnables (`invoke`, `ainvoke`, `batch`, `abatch`). — 2026-11-09
62. langchain-db2 on PyPI — https://pypi.org/project/langchain-db2/ — 1.0.0, released 2025-10-30; author IBM; MIT; source `langchain-ai/langchain-ibm` under `libs/langchain-db2`. README does not mention vector indexes or metadata filters. — 2026-11-09
63. langchain-ibm PR #342 — https://github.com/langchain-ai/langchain-ibm/pull/342 — "feat(langchain-db2): DiskANN vector index support — create_index(), drop_index(), tablespace param", opened 2026-09-21 (open at time of writing). Adds vector index creation to the LangChain Db2 integration; `create_index()` runs RUNSTATS after creation. — 2026-11-09
64. ibm-db-haystack on PyPI (JSON API) — https://pypi.org/pypi/ibm-db-haystack/json — 1.0.0, uploaded 2026-10-19; summary "Haystack integration for IBM Db2"; Apache-2.0; deepset GmbH. — 2026-11-09
65. haystack-core-integrations `integrations/ibm_db` — https://github.com/deepset-ai/haystack-core-integrations/tree/main/integrations/ibm_db — Source of `ibm-db-haystack` (src, tests, docker-compose.yml, pyproject.toml). — 2026-11-09
66. Haystack PR #4086 — https://github.com/deepset-ai/haystack-core-integrations/pull/4086 — "feat(ibm_db): add CREATE VECTOR INDEX support for Db2 12.1.5+" by GeetikaChughIBM, opened 2026-10-11, open draft. Creates the index and makes `embedding` NOT NULL only when `create_vector_index=True` on new tables. APPROX and `FETCH FIRST ? ROWS` are not mentioned. — 2026-11-09
67. Haystack PR #4217 — https://github.com/deepset-ai/haystack-core-integrations/pull/4217 — "fix: validate filter field names in MariaDB and IBM Db2 document stores" by camgrimsec, opened 2026-11-08, draft (CLA). Db2 part: "raise FilterError for invalid field names before any SQL is built." — 2026-11-09
68. ibm_db on PyPI — https://pypi.org/project/ibm_db/ — 3.3.0, released 2026-08-11; Apache 2.0; Python 3.9 to 3.14; Windows wheels "include clidriver"; DLL fallback `os.add_dll_directory()`. Source https://github.com/ibmdb/python-ibmdb. — 2026-11-09
69. Ollama `/api/embed` — https://docs.ollama.com/api/embed — POST; required `model`, `input` (string or array); optional `truncate` (default true), `dimensions`, `keep_alive`; response `embeddings` (array of arrays). No statement on L2 normalization. — 2026-11-09
70. Streamlit `st.dataframe` — https://docs.streamlit.io/develop/api-reference/data/st.dataframe — "Display a dataframe as an interactive table"; `column_config`, `hide_index`, `on_select` ("ignore" / "rerun" / callback), `selection_mode` (default "multi-row"), `height`, `width`; `use_container_width` deprecated. Page version 1.67.0. — 2026-11-09

---

## 7. Visual references (layout only; no logos, icons, colors or copy)

71. osv.dev record page — https://osv.dev/vulnerability/PYSEC-2020-96 — Copy: ID header with aliases list and Published/Modified timestamps; "Affected packages" block with range events (Introduced / Fixed) and version chips; plain references list; explicit empty state ("[none]") when a field is missing. — 2026-11-09
72. GitHub Advisory Database list — https://github.com/advisories?query=ecosystem%3Apip — Copy: compact two-line rows (title + severity label on line 1, ID/package/ecosystem/date on line 2), about 25 rows per page, left facet for reviewed/unreviewed/malware and ecosystem counts, severity and CWE filters, sort by newest/updated. — 2026-11-09
73. Snyk vulnerability DB package page — https://security.snyk.io/package/pip/pyyaml — Copy: single-letter severity counters (C/H/M/L) shown even when zero; version table (version, published, per-version severity counters); clear "no known issues in latest version" empty state. — 2026-11-09
74. Socket scans docs — https://docs.socket.dev/docs/scans — Copy: alert columns Severity (Critical/High/Medium/Low), Alert Type, Scope (direct/transitive), and a dependencies tab with version detected and alert counts. — 2026-11-09
75. Carbon Design System: Data table — https://carbondesignsystem.com/components/data-table/usage/ — Copy: row heights 24px (xs, dense) to 64px (xl, 2-line only); optional zebra stripes; toolbar for search/filters; expandable rows for slow or secondary data; sortable headers. — 2026-11-09
76. Carbon Design System: Tag — https://carbondesignsystem.com/components/tag/usage/ — Copy: read-only tags for severity/category, dismissible tags for active filters, small size in dense rows, titles under 20 characters, different colors per category. — 2026-11-09
77. Carbon Design System: Notification — https://carbondesignsystem.com/components/notification/usage/ — Copy: inline notification for persistent states (for example "RCAC active: 37% of corpus visible"), toast only for brief non-critical feedback; status set info (blue) / success (green) / warning (yellow) / error (red); callout only info or warning. — 2026-11-09

Note on numbering: entry 16 is listed for navigation but is unverified; the verified count (75) excludes it and counts entry 60/71 (the same osv.dev page) once.

---

## 8. UNVERIFIED (not fetched successfully, or not re-fetched this session)

Failed or blocked this session:
- https://dl.acm.org/doi/10.1145/3543507.3583552 — HTTP 403. Use the Crossref record (entry 39).
- https://dl.acm.org/doi/10.1145/3654923 — HTTP 403. Use the Crossref record (entry 41).
- https://www.nowpublishers.com/article/Details/INR-019 and https://nowpublishers.com/article/Details/INR-019 — HTTP 403.
- https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf → http://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf — PDF fetched but text not extractable (no PDF tool). The k=60 value is verified only through Elastic (entry 51).
- https://harsha-simhadri.org/pubs/Filtered-DiskANN23.pdf — PDF fetched but text not extractable. Paper content (not metadata) is unverified.
- https://www.microsoft.com/en-us/research/publication/filtered-diskann-graph-algorithms-for-approximate-nearest-neighbor-search-with-filters/ — HTTP 404.
- https://dblp.org/rec/conf/sigir/CormackCB09.html, https://dblp.org/rec/conf/www/GollapudiKSKSSS23.html — bot block.
- https://ir.webis.de/anthology/2009.ftir_journal-ir0anthology0volumeA3A4.0/ — HTTP 404.
- https://socket.dev/pypi/package/pyyaml — HTTP 403.
- https://pypi.org/project/ibm-db-haystack/ — HTML did not render (JSON API used instead, entry 64).

Not found in IBM docs this session:
- A Db2 12.1 LUW RCAC overview page (search showed https://www.ibm.com/docs/en/db2/12.1.x?topic=rcac-scenario-examplehmo-using-row-column-access-control; not fetched).
- An IBM docs reference page for vector-index optimization guidelines (`IXSCAN ... SEARCH_LIST_SIZE`). Only the Feb 2026 blog (entry 32) documents it.
- Any Db2 12.1 documentation for `SYSTOOLS.JSON_TABLE`.
- Any IBM source on WHERE predicates, filters or RCAC combined with a vector index.

From the ChatGPT build pack, not re-fetched this session (treat as UNVERIFIED until fetched):
- https://ibmdb2techxsummit.glbajajgroup.ac.in/ (and /submit, /resources)
- https://ibm-db2hack-2026.devpost.com/ (and /resources, /rules)
- https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission (and docs/faq.md, docs/judging-criteria.md, docs/submission-guide.md, PR template)
- https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-create-table
- https://www.ibm.com/docs/en/db2/12.1.x?topic=functions-vector
- https://www.ibm.com/docs/en/db2/12.1.x?topic=expressions-olap-specification
- https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-create-bufferpool
- https://www.ibm.com/docs/en/db2/12.1.x?topic=statements-create-tablespace
- https://www.ibm.com/docs/en/db2/12.1.x?topic=sql-xml-limits
- https://www.ibm.com/docs/en/db2/12.1.x?topic=deployments-db2-community-edition-docker
- https://docs.haystack.deepset.ai/docs/custom-components
- https://docs.haystack.deepset.ai/reference/integrations-ibm-db
- https://github.com/deepset-ai/haystack-core-integrations/issues/4049
- https://docs.langchain.com/oss/python/integrations/vectorstores/db2
- https://github.com/IBM/db2-sqlglot-plugin
- https://osv.dev/docs/
- https://learn.snyk.io/lesson/intro-to-snyk-ui/
- https://socket.dev/alerts
- https://linear.app/changelog/2026-03-12-ui-refresh
- https://grafana.com/docs/grafana/latest/visualizations/explore/get-started-with-explore/
- https://github.com/deepset-ai/haystack (repo root)
