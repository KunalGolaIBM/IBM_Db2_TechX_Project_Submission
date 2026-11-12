# IBM Db2 deep dive

Everything NSIN stores, searches, measures and protects lives in **one IBM Db2 12.1 database**. This page walks through every Db2 feature in use and where to find it in the code.

## 1. How the app connects

| Layer | Library | Used for | Code |
|---|---|---|---|
| ORM | `ibm_db_sa` (SQLAlchemy dialect) | All application reads and writes, transactions | `src/backend/app/database/db2_adapter.py` (`get_session_factory`) |
| Native driver | `ibm_db` | Health probe, `server_info()`, parameterised `prepare`/`execute` with explicit commit/rollback | `db2_adapter.py` (`test_connection`, `execute_query`, `execute_non_query`) |
| Haystack | `ibm-db-haystack` | `IBMDb2DocumentStore` + `IBMDb2EmbeddingRetriever` for protocol passages | `src/backend/app/ai/haystack/rag_pipeline.py` |
| CrewAI | `crewai-tools` `DB2VectorSearchTool` | Agent-side vector search over the same passages | `src/backend/app/ai/crewai/crew.py` |
| LangChain | `langchain-db2` `DB2VS` | Incident vector store for related reports | `src/backend/app/ai/semantic/db2_vector_store.py` |

Db2 is the **only** database. If it is unreachable, the backend refuses to start. There is no silent fallback.

## 2. Schema
The full DDL, exported with `db2look`, is in [`db/db2_schema.sql`](../db/db2_schema.sql). The core design:
- **12 relational tables:**
  - users, trusted contacts and responders;
  - incidents, with an **append-only** `incident_status_history`, plus location events;
  - child journeys, elder check-ins and assistance requests;
  - community hazards, AI analyses (one per incident, upserted) and `audit_events`.
- **2 vector tables:**
  - `NSIN_PROTOCOL_PASSAGES`, managed by `ibm-db-haystack`: `id VARCHAR(512)`, `content CLOB(2M)`, BSON `meta`, `embedding VECTOR(768, FLOAT32)`;
  - `INCIDENT_EMBEDDINGS`, managed by `langchain-db2`: `VECTOR(768, FLOAT32)` plus JSON metadata.
- **Integrity:** primary, foreign and unique keys; identity columns; reference codes derived from the identity value inside the same transaction, so they never collide.
- **Indexes tuned to the queries that run most:**
  - `(status, priority)` for responder queues;
  - `created_at` for analytics windows;
  - `(incident_id, status, created_at)` for the first-acknowledgement CTE;
  - audit lookups.

## 3. Feature by feature

### 3.1 Vector search: `VECTOR` + `VECTOR_DISTANCE`
Protocol passages and incident reports are embedded with IBM `granite-embedding:278m` (768 dimensions) and searched by cosine distance inside Db2:
```sql
SELECT id, content, SYSTOOLS.BSON2JSON(meta) AS meta,
       VECTOR_DISTANCE(embedding, VECTOR(CAST(? AS CLOB(100000)), 768, FLOAT32), COSINE) AS score
FROM NSIN_PROTOCOL_PASSAGES
WHERE JSON_VALUE(SYSTOOLS.BSON2JSON(meta), '$.audience' RETURNING VARCHAR(1000)) = ?
ORDER BY score ASC FETCH FIRST ? ROWS ONLY
```
(Issued by `IBMDb2EmbeddingRetriever`; the metadata filter comes from our Haystack filter.)

### 3.2 JSON metadata in Db2
Passage metadata (category, audience, source, updated date) is stored as **BSON** and filtered with `JSON_VALUE(SYSTOOLS.BSON2JSON(meta), …)`. `GET /ai/guidance?category=elder_care&audience=seniors` becomes a Db2 predicate, not a Python loop.

### 3.3 Analytics in SQL
`src/backend/app/analytics/insights.py` computes the community dashboard entirely in Db2:
```sql
WITH first_ack AS (
  SELECT incident_id, MIN(created_at) AS ack_at
  FROM incident_status_history WHERE status = 'acknowledged' GROUP BY incident_id)
SELECT i.priority, COUNT(*) AS incidents, COUNT(a.ack_at) AS acknowledged,
       MEDIAN(DOUBLE(SECONDS_BETWEEN(a.ack_at, i.created_at))) AS median_ack_s,
       PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY DOUBLE(SECONDS_BETWEEN(a.ack_at, i.created_at))) AS p90_ack_s
FROM incidents i LEFT JOIN first_ack a ON a.incident_id = i.id
WHERE i.created_at >= :since
GROUP BY i.priority
```
Plus `RANK() OVER (ORDER BY COUNT(*) DESC)` for hotspots, `HOUR()` for the hourly pattern, and a `CASE` on per-priority SOP targets for live SLA breaches.

### 3.4 Transactions
- **An SOS is atomic:** the incident row, the GPS location event, the first status entry and the audit row commit together.
- **Every status change** writes the incident update, a history row and an audit row in one transaction.
- **Overdue child journeys** are flagged by a single set-based `UPDATE … WHERE status='active' AND expected_arrival_time < ?`.

### 3.5 Catalog-driven DDL
`SYSCAT.TABLES` is queried with `TABSCHEMA = CURRENT SCHEMA` to decide what to create, so a least-privilege login never attempts DDL. The tests read `SYSCAT.COLUMNS` to assert that the `VECTOR` columns exist.

### 3.6 Security inside Db2
Role `NSIN_APP` has data access only; `audit_events` is insert/read only. See [SECURITY.md](SECURITY.md#2-least-privilege-in-ibm-db2).

## 4. Db2-specific lessons learned (and fixed)
Running every test on a real Db2 surfaced issues that a SQLite-based test suite would have hidden. They're listed in [TESTING.md](TESTING.md#bugs-these-tests-caught-that-sqlite-would-have-hidden): duplicate indexes (`SQL0605W`), `IS 1` boolean syntax (`SQL0104N`), schema resolution for restricted logins, a reserved column name, and lock waits from an uncommitted connection.

## 5. Try it yourself
```bash
docker exec -it <db2-container> su - db2inst1 -c "db2 connect to TESTDB && \
  db2 \"SELECT VARCHAR(TABNAME,30) AS TAB, VARCHAR(COLNAME,20) AS COL, TYPENAME FROM SYSCAT.COLUMNS WHERE TYPENAME='VECTOR'\""
```
