# SQL0901N on `FETCH APPROX FIRST n ROWS ONLY` for one query vector (eval agent)

Observed 2026-11-10 ~01:38-01:46 UTC, Db2 v12.1.5.0 (`special_85816`), database VECDB,
table NEEDLE.ADV_DOC (26,210 rows, `EMB VECTOR(768, FLOAT32) NOT NULL`),
vector index NEEDLE.ADV_DOC_VIX (INDEXTYPE `VANN`, `WITH DISTANCE COSINE`), RUNSTATS done at 01:31:23 UTC.
Client: python3 + ibm_db inside the codespace, localhost:50000, user DB2INST1.

## Where it showed up
Full eval run `20261110T013825Z` (eval/results/20261110T013825Z.json, log docs/evidence/eval_20261110T013825Z.log):
query `paraphrase:GHSA-v4f4-23wc-99mh` failed in two retrievers that both run an APPROX leg with depth 100:

- `triage` (NEEDLE.TRIAGE_MODE 'HYBRID', depth 100): `SQL0901N ... (Reason "Fetched nodes unexpectedly unsorted.".) SQLCODE=-901`
- `rrf_client` (eval's own `FETCH APPROX FIRST 100 ROWS ONLY` leg): same SQL0901N reason.

The other 449 queries ran without error in both retrievers.

## Reproduction (same query vector, from data/eval_qvecs.json.gz)
Statement (vector bound as a parameter, k as a literal):

```sql
SELECT ADV_ID, VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) AS DIST
FROM NEEDLE.ADV_DOC ORDER BY DIST FETCH APPROX FIRST <k> ROWS ONLY
```

Output (verbatim):

```
APPROX FIRST 100: ERROR SQL0901N  The SQL statement or command failed because of a database system error. (Reason "Fetched nodes unexpectedly unsorted.".) SQLCODE=-901
APPROX FIRST 100: ERROR SQL0901N  The SQL statement or command failed because of a database system error. (Reason "Fetched nodes unexpectedly unsorted.".) SQLCODE=-901
APPROX FIRST 100: ERROR SQL0901N  The SQL statement or command failed because of a database system error. (Reason "Fetched nodes unexpectedly unsorted.".) SQLCODE=-901
APPROX FIRST 10: OK rows=10 top1=MAL-2026-18225
APPROX FIRST 20: OK rows=20 top1=MAL-2026-18225
APPROX FIRST 50: OK rows=50 top1=MAL-2024-12270
APPROX FIRST 99: ERROR SQL0901N  The SQL statement or command failed because of a database system error. (Reason "Fetched nodes unexpectedly unsorted.".) SQLCODE=-901
APPROX FIRST 200: OK rows=200 top1=MAL-2024-12270
EXACT FIRST 100: OK rows=100 top1=MAL-2024-12270
```

Facts:
- The error is deterministic for this vector at k = 99 and k = 100 (3 of 3 tries at k = 100); k = 10, 20, 50, 200 succeed.
- EXACT with the same vector and k = 100 succeeds.
- Side observation: APPROX FIRST 10 and 20 return a different top-1 (`MAL-2026-18225`) than EXACT (`MAL-2024-12270`).

Not done / unknown: db2diag.log was not inspected; whether other vectors hit the error at other k values is UNKNOWN
(only depths 10 and 100 were run for all 450 eval queries; 1 of 450 failed at depth 100, 0 of 450 at depth 10).
Consequence for NEEDLE: TRIAGE with the default depth 100 returns an error for this query instead of results.

## Repro script (run inside the codespace from the eval bundle dir, DB2_* env vars set, password from stdin)

```python
import gzip, json, os, sys
import ibm_db_dbi

QID = sys.argv[1] if len(sys.argv) > 1 else "paraphrase:GHSA-v4f4-23wc-99mh"
with gzip.open("data/eval_qvecs.json.gz", "rt", encoding="utf-8") as f:
    vec = json.load(f)["vectors"][QID]
vt = json.dumps(vec, separators=(",", ":"))
e = os.environ
conn = ibm_db_dbi.connect(f"DATABASE={e['DB2_DATABASE']};HOSTNAME={e['DB2_HOST']};PORT={e['DB2_PORT']};"
                          f"PROTOCOL=TCPIP;UID={e['DB2_USER']};PWD={e['DB2_PASSWORD']};", "", "")
try:
    for mode, k in [("APPROX", 100), ("APPROX", 100), ("APPROX", 100), ("APPROX", 10), ("APPROX", 20),
                    ("APPROX", 50), ("APPROX", 99), ("APPROX", 200), ("EXACT", 100)]:
        sql = ("SELECT ADV_ID, VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) AS DIST "
               f"FROM NEEDLE.ADV_DOC ORDER BY DIST FETCH {mode} FIRST {int(k)} ROWS ONLY")
        cur = conn.cursor()
        try:
            cur.execute(sql, (vt,))
            rows = cur.fetchall()
            print(f"{mode} FIRST {k}: OK rows={len(rows)} top1={rows[0][0] if rows else None}")
        except Exception as ex:
            msg = str(ex); i = msg.find("SQL0901N")
            print(f"{mode} FIRST {k}: ERROR {msg[i:i + 160] if i >= 0 else msg[:160]}")
        finally:
            cur.close()
finally:
    conn.close()
```
The query vector is `nomic-embed-text` (Ollama digest 0a109f422b47...) of
`"search_query: " + <query text of paraphrase:GHSA-v4f4-23wc-99mh in eval/queries/paraphrase.jsonl>`.
