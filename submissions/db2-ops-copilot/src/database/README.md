# Database setup — IBM Db2 Community Edition

> **Status:** scripts are authored, idempotent and reviewed but **never
> executed** — no Db2 instance exists on the development machine (portable
> constraint). Real execution happens in M3 on an infrastructure-enabled
> machine; see `HANDOFF.md`.

## Contents

| File | Purpose |
|---|---|
| `migrations/001_app_schema.sql` | `APP` schema: demo tables, extended `APP_AUDIT`, `DOCUMENT_METADATA`, `QUERY_EXECUTIONS` |
| `migrations/002_indexes.sql` | Indexes for incidents, audit, query-execution and document lookups |
| `migrations/003_readonly_user.sql` | Least-privilege GRANTs for the `db2ro` account |
| `migrations/004_vector_store.sql` | `COPILOT_KB` — vector table in the exact shape langchain-db2's `DB2VS` creates (verified against package source) |

## Prerequisites (M3 — infrastructure machine only)

1. Docker running with the official image: `icr.io/db2_community/db2`
   (tag ≥ 12.1.2 — `VECTOR` support required; verify with `db2level`).
2. Instance created with a locally generated password in the gitignored
   `.env` (`DB2_INSTANCE_PASSWORD`).
3. Port bound to `127.0.0.1` only. Never expose the Db2 port publicly.
4. Target database created (default `testdb`, see `DB2_DBNAME`).

## How to run (M3)

Connect as the instance owner (`db2inst1`) to the target database and apply
migrations **in numeric order**:

```
db2 -tvf database/migrations/001_app_schema.sql
db2 -tvf database/migrations/002_indexes.sql
db2 -tvf database/migrations/003_readonly_user.sql   # after substituting :ro_user
db2 -tvf database/migrations/004_vector_store.sql
```

All scripts are **idempotent**: object creation is guarded by SYSCAT
catalog checks inside anonymous blocks (`--#SET TERMINATOR @`), so re-running
a script is safe and never drops existing data. The only destructive
statements are the demo-seed `DELETE`s in 001, which touch synthetic data
only.

## Schema overview

```
APP
├── DEMO_SERVERS          synthetic fleet  (text-to-SQL demo target)
├── DEMO_INCIDENTS        synthetic incidents
├── APP_AUDIT             every copilot request: actor/session, operation,
│                         intent, question, generated SQL, status, latency,
│                         SANITIZED metadata JSON (append-only for db2ro)
├── DOCUMENT_METADATA     per-chunk bookkeeping for the knowledge base:
│                         source, title, URI, chunk ids, hash, timestamps
├── QUERY_EXECUTIONS      every executed/rejected query: SQL, validation and
│                         EXPLAIN outcome, status, rows, latency, SQLSTATE
└── COPILOT_KB            DB2VS vector table (langchain-db2 managed):
                          id CHAR(16) PK, text CLOB, metadata BLOB,
                          embedding VECTOR(768, FLOAT32)
```

## The DB2VS vector-store mechanism (verified, not invented)

`langchain-db2`'s `DB2VS` manages **its own table layout** (verified against
the package source — see `M2_REPO_AUDIT.md` §1):

- Constructor: `DB2VS(embedding_function, table_name, client=<ibm_db_dbi
  Connection>, distance_strategy=DistanceStrategy.COSINE, ...)` — it embeds
  one probe text to infer the dimension, then creates the table **if it does
  not exist** with exactly the DDL used in `004_vector_store.sql`.
- Because migration 004 pre-creates `APP.COPILOT_KB` with that exact DDL,
  the read-only application account never needs `CREATE TABLE`, and the
  package skips its internal creation step.
- `add_texts()` inserts (id hashed from the metadata `id` when present,
  `SYSTOOLS.JSON2BSON` for metadata); `similarity_search*()` ranks with
  `VECTOR_DISTANCE`; `delete(ids)` deletes; `get_pks()` lists ids.
- Distance metric is fixed per table at construction (we default to COSINE
  via `VECTOR_DISTANCE_STRATEGY`).

## Security notes

- The app runs as `db2ro`: SELECT on business tables, SELECT+INSERT on
  `APP_AUDIT` and `QUERY_EXECUTIONS` (append-only), SELECT on
  `DOCUMENT_METADATA`, SELECT+INSERT+DELETE on `COPILOT_KB`, nothing else.
  See `003_readonly_user.sql`.
- Generated SQL is validated by the sqlglot gate (`SELECT`-only, single
  statement, catalog deny-list) **and** executed under these grants — the
  grants are the real boundary.
- Passwords are generated locally and stored only in `.env` (gitignored).
  They never appear in source, scripts, logs, or commits.
- `METADATA` columns hold sanitized JSON only — the application strips
  credential-like values before insert (audit/query adapters).

## Rollback and recovery

There is no automated down-migration (Db2 has no `DROP ... IF EXISTS`
syntax for every object type, and destroying audit history is rarely the
goal). Recovery guidance instead:

| Situation | Action |
|---|---|
| Partial migration (script failed midway) | Fix the reported object, re-run the **same** script — guards make it idempotent. |
| Redefine an application table (schema change) | Drop it explicitly as the owner, then re-run from 001: `db2 -tx DROP TABLE APP.<name>` |
| Remove the whole application | As owner, in reverse dependency order: drop `COPILOT_KB`, `QUERY_EXECUTIONS`, `DOCUMENT_METADATA`, `APP_AUDIT`, `DEMO_INCIDENTS`, `DEMO_SERVERS`, then `DROP SCHEMA APP RESTRICT`, then revoke grants from `003` (`REVOKE ... FROM :ro_user`). |
| Bad audit/query rows | Append-only tables — correct with a new row; do not UPDATE/DELETE as `db2ro` (it has no such privilege by design). Owner may purge with an explicit DELETE for retention policy. |
| Vector table corrupted / dimension mismatch | `TRUNCATE TABLE APP.COPILOT_KB IMMEDIATE` (owner) and re-ingest the knowledge base (M3 ingestion pipeline). |

Before any destructive owner operation on a real deployment, take a backup
(`db2 backup database <db>`) — the demo dataset is disposable, production
audit history is not.
