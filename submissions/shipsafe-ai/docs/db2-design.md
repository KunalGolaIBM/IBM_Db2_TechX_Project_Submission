# IBM Db2 design

ShipSafe keeps everything in one Db2 12.1 schema (`SHIPSAFE` by default): relational records, two
vector stores and SQL PL procedures. Full DDL: [db2-schema.sql](db2-schema.sql). Grants for a DML-only
runtime user: [db2-least-privilege.sql](db2-least-privilege.sql).

## Objects

| Kind | Objects |
|---|---|
| IDE activity | `GUARD_EVENTS` (every check: IDE, tool, verdict, rules, duration), `FIX_ATTEMPTS` (model, rounds, verified, issues before/after, diff as CLOB) |
| Assessments | `PROJECTS`, `ASSESSMENTS`, `TOOL_RUNS`, `FINDINGS` (evidence as CLOB JSON), `DEPENDENCIES`, `ASSESSMENT_DIFFS` |
| Knowledge | `KNOWLEDGE_DOCS`, `POLICY_VECTORS` (LangChain `DB2VS`), `MEMORY_VECTORS` (Haystack `IBMDb2DocumentStore`) |
| Access | `API_TOKENS` (SHA-256 only), `AUDIT_LOG` (append-only) |
| Views | `V_RISK_TREND` (`LAG` for the change since the previous run, `ROW_NUMBER` for recency), `V_PROJECT_POSTURE` (latest run per project) |
| Procedures | `SP_PROJECT_RISK`, `SP_GUARD_SUMMARY`, `SP_PURGE_HISTORY` |
| Indexes | 10, e.g. `IDX_GUARD_TS (TS DESC)`, `IDX_GUARD_PROJ (PROJECT, TS DESC)`, `IDX_FND_FP (FINGERPRINT)` |
| Integrity | Foreign keys with `ON DELETE CASCADE`; `CHECK` on verdicts, roles and the verified flag; `UNIQUE` token hashes |

Objects are created only when missing, so `shipsafe setup` is safe to re-run, and the runtime can use a
user without DDL rights.

## Vectors

Both vector tables use `VECTOR(384, FLOAT32)` filled by IBM Granite embeddings (`granite-embedding:30m`),
and both rank inside Db2 with `VECTOR_DISTANCE(..., COSINE)`:

```sql
-- the shape of the similarity query DB2VS issues for a policy citation
SELECT ID, TEXT, METADATA, VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS D
FROM POLICY_VECTORS ORDER BY D FETCH FIRST ? ROWS ONLY;
```

Project memory stores project, kind, tags, author and timestamp as BSON metadata and filters on them in
the same query, so recall for one project never sees another project's decisions.

## Stored procedures

```sql
CALL SHIPSAFE.SP_PROJECT_RISK('prj_123', ?, ?, ?, ?);   -- score, delta, trend ('new'|'improving'|'worsening'|'steady'|'unknown'), runs
CALL SHIPSAFE.SP_GUARD_SUMMARY(1794400000000);          -- result set: CLIENT, CHECKS, BLOCKED, WARNED, ISSUES_CAUGHT, VERIFIED_FIXES
CALL SHIPSAFE.SP_PURGE_HISTORY(90, ?, ?);               -- assessments and events deleted; SIGNAL 75001 if days < 1
```

Lessons from running them through `ibm_db`:
- Call procedures schema-qualified. Routine resolution uses `CURRENT PATH`, not `CURRENT SCHEMA`.
- Never leave an OUT parameter NULL. The CLI driver fails with CLI0110E, so the procedures return 0 and
  use the trend label to say whether a value is meaningful.

## SQL validation without execution

The SQL assistant calls `ibm_db.prepare(conn, sql, {SQL_ATTR_DEFERRED_PREPARE: 0})`. With deferred prepare
off, Db2 compiles the statement immediately and returns SQL0104N (syntax), SQL0204N (unknown object) or
SQL0206N (unknown column), or a description of the result columns. The statement is freed and the
transaction rolled back, so it never runs. For unknown names, the closest table or column names come
from the catalog, read with SQLAlchemy's inspector over `ibm_db_sa`.

## Transactions and connections

- Autocommit is off. An assessment (project `MERGE`, inventory, assessment, tool runs, findings) is saved
  in one transaction; a failure rolls everything back (covered by a test).
- Every value is bound with `?`, including `OFFSET ? ROWS FETCH FIRST ? ROWS ONLY`.
- The API uses a connection pool that pings before reuse and replaces broken connections; the MCP server
  keeps one connection behind a lock, drops it when a Db2 call fails and reconnects on the next call.
- Connection strings set `CONNECTTIMEOUT=10`, and local hosts use `127.0.0.1` (see getting-started).

## Frameworks on Db2

| Library | Used for |
|---|---|
| `ibm_db` / `ibm_db_dbi` | All tables, transactions, procedures, PREPARE validation |
| `ibm_db_sa` + SQLAlchemy 2 | Catalog inspection: tables, columns, keys, indexes, views |
| `langchain-db2` | `DB2VS` vector store for policies |
| `ibm-db-haystack` | `IBMDb2DocumentStore` + `IBMDb2EmbeddingRetriever` for project memory |
