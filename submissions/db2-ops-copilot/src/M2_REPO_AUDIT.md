# M2 Repository Audit — baseline `a00d4e9` (M1 merge)

**Auditor:** M2 engineering pass (read-only inspection before implementation)
**Date:** 31 October 2026
**Baseline commit:** `a00d4e92c556d87295a1a7d8332e590d2f1164ad` (branch `main`, clean tree, 103 tracked files)
**Offline baseline verified before any change:** 100 backend tests pass; frontend production build passes.

Scope: identify incomplete real adapters, stubs, and schema/API gaps that M2
must close — **without** installing Docker, Ollama, Db2 or any AI model, and
without executing migrations against a real database.

## 1. External API verification (per task §6 — no package installation)

The `langchain-db2` DB2VS contract was verified against the **official package
source and worked-example notebook** fetched over HTTPS (no pip install, no
container):

- Source: `langchain-ai/langchain-ibm` repo, `libs/langchain-db2/langchain_db2/db2vs.py`
- Worked example: `libs/langchain-db2/docs/db2.ipynb`

Verified facts (full table inline):

| Fact | Value |
|---|---|
| Import | `from langchain_db2.db2vs import DB2VS` |
| Constructor | `DB2VS(embedding_function, table_name, client=ibm_db_dbi.Connection, distance_strategy=DistanceStrategy.*, query=..., text_field="text")` |
| Client type | an existing `ibm_db_dbi.Connection` (or `connection_args` dict) |
| Auto-DDL | constructor auto-creates the table if absent: `id CHAR(16) PRIMARY KEY NOT NULL, <text> CLOB, metadata BLOB, embedding VECTOR(<dim>, FLOAT32)` |
| Dimension inference | one probe embedding at construction (`query` param) |
| Add | `add_texts(texts, metadatas=None, ids=None)` — ids are SHA-256-hashed to 16 uppercase hex chars |
| Search | `similarity_search(query, k, filter)`, `similarity_search_with_score(...)` → `(Document, distance)` where **lower distance = closer** |
| Filter format | `{"key": ["value", ...]}` — values must be **lists** (direct membership test against decoded metadata) |
| Delete | `delete(ids)` — accepts raw or already-hashed ids |
| Helpers | module functions `drop_table(client, table_name)`, `clear_table(client, table_name)`; method `get_pks()` |
| Destructive caveat | `from_texts()`/`from_documents()` call `drop_table()` first — adapter must use constructor + `add_texts` for incremental inserts |
| Distance strategies | `langchain_community.vectorstores.utils.DistanceStrategy` — `COSINE`, `DOT_PRODUCT`, `EUCLIDEAN_DISTANCE` |

**Conclusion:** the contract is fully verifiable from source; no unresolved
API contract remains. Implementation will use exactly these signatures.

## 2. Findings by area

### M2.1 — Db2 database adapter (`backend/app/adapters/db/db2_db.py`)
| # | Severity | Finding |
|---|---|---|
| D1 | High | `fetch_schema()` introspects schema `DB2_RO_USER.upper()` — but application tables live in schema **APP**. Against a real Db2 the introspection would return zero application tables. Needs a configurable app schema (new `DB2_APP_SCHEMA` setting, default `APP`). |
| D2 | Medium | No SQLSTATE-based error classification: every failure becomes one generic `AdapterUnavailableError`; permission errors vs connectivity errors are indistinguishable to operators. |
| D3 | Medium | `SET CURRENT QUERY TIMEOUT` failure is swallowed silently (`pass`) — timeout enforcement at the DB layer could be silently absent. Must log a warning and surface enforcement status. |
| D4 | Low | No transaction management API (commit/rollback helpers) despite requirement; reads are implicitly fine (connection-per-call) but audit/execution writes need explicit semantics. |
| D5 | Low | `execute_readonly` does not state its contract w.r.t. the validation gate (callers must validate first). M2.6 requires explicit layering. |

### M2.2 — Migrations (`database/migrations/`)
| # | Severity | Finding |
|---|---|---|
| M1 | High | `APP_AUDIT` missing required M2 columns: actor/session reference, operation type, sanitized metadata. |
| M2 | High | `DOCUMENT_METADATA` table absent. |
| M3 | High | `QUERY_EXECUTIONS` table absent. |
| M4 | Medium | `KB_CHUNKS` was a hand-invented vector layout. With the verified DB2VS contract, the vector table must match DB2VS's own DDL exactly (`id CHAR(16)`, `text CLOB`, `metadata BLOB`, `embedding VECTOR(dim, FLOAT32)`); otherwise the package's `_create_table` would diverge from our schema. KB_CHUNKS must be replaced by a DB2VS-shaped table (pre-created by migration so read-only user needs no CREATE privilege). |
| M5 | Medium | Not idempotent (bare `CREATE TABLE`/`CREATE SCHEMA` fail on re-run); no rollback/recovery guidance in SQL. |

### M2.3 — Ollama adapters (`ollama_chat.py`, `ollama_embeddings.py`)
| # | Severity | Finding |
|---|---|---|
| O1 | Medium | No retry policy for transient errors (connect resets, 5xx); requirement demands bounded retry. |
| O2 | Low | Module-level `httpx.get/post` — no client reuse/lifecycle (new TCP connection per call, no keep-alive). |
| O3 | Low | No structured logging of generation metadata (model, tokens, latency) — observability requirement. Prompt *content* must never be logged (current behavior correct; keep). |

### M2.4 — Vector store (`db2_vector.py`)
| # | Severity | Finding |
|---|---|---|
| V1 | High | Entire DB2VS wiring is a stub (by design in M1). M2 must implement it against the verified contract: constructor with shared `ibm_db_dbi` connection, `add_texts`, `similarity_search_with_score`, `delete`, `get_pks`, filter-format conversion (dict → `{key: [values]}`), lazy imports, actionable availability probes. |
| V2 | Medium | No LangChain `Embeddings` bridge exists between our `EmbeddingModelAdapter` and DB2VS's expected `Embeddings` object. Needs a duck-typed wrapper built without importing langchain at module import time (offline safety). |

### M2.5 — Audit persistence (`db2_audit.py`)
| # | Severity | Finding |
|---|---|---|
| A1 | Medium | INSERT/SELECT column lists don't cover the extended M2 `APP_AUDIT` schema (actor, operation, metadata). |
| A2 | Medium | No metadata sanitization step (requirement: never store passwords/tokens/full DSNs; truncate + strip before insert). |

### M2.6 — SQL execution & security
| # | Severity | Finding |
|---|---|---|
| S1 | High | No query **execution service** exists: validation is complete, but the validated-statement → row-capped → timed-out → audited execution path (with `QUERY_EXECUTIONS` recording and rejected-query audit) is missing. |
| S2 | Medium | Row cap currently only applied via `fetchmany`; if a validated query contains `FETCH FIRST 1000 ROWS ONLY` it is accepted as-is up to the Python cap — execution service must apply the hard cap deterministically (wrap subselect when `enforce_row_limit`). |
| S3 | Low | EXPLAIN dry-run (planned since M1) not implemented; must be best-effort (read-only accounts may lack EXPLAIN privileges / plan tables). |

### M2.7 — Integration tests
| # | Severity | Finding |
|---|---|---|
| T1 | High | `backend/tests/integration/` does not exist. No pytest `integration` marker registered in `pyproject.toml`. |
| T2 | Medium | No fake-driver / mocked-HTTP offline unit coverage for the real adapters (currently the real adapters are only exercised indirectly). |

### M2.8 — API integration
| # | Severity | Finding |
|---|---|---|
| P1 | Medium | No `/api/v1/sql/execute` route (execution service from S1 not exposed). |
| P2 | Low | No readiness endpoint with fail-fast semantics for orchestrators (`/health` always 200 by design; a 503-capable `/ready` complements it without breaking the degraded-health contract). |

### Dependencies / config
| # | Severity | Finding |
|---|---|---|
| C1 | Low | `requirements-integration.txt` lacks explicit `numpy` (langchain-db2 imports it directly). Add pinned-compatible constraint. |
| C2 | Low | `.env.example` lacks the new M2 variables (app schema, vector table/strategy, Ollama retries, EXPLAIN flag). |

## 3. Explicit non-findings (checked, clean)

- No credentials anywhere; `SecretStr` + DSN sanitizer intact; `.env.example` placeholders only.
- Mock adapters remain separate classes; registry guarantees `real` mode never instantiates mocks (test-enforced, will be preserved).
- M1 offline suite (100 tests) and frontend build pass at baseline.
- Error envelope, request-id propagation, CORS allow-list, strict schemas all intact.
- `requirements-integration.txt` correctly pinned and **not installed** (verified: no ibm_db/langchain in venv).

## 4. Plan summary (what M2 will change)

1. New settings: `DB2_APP_SCHEMA`, `VECTOR_TABLE_NAME`, `VECTOR_DISTANCE_STRATEGY`, `OLLAMA_MAX_RETRIES`, `OLLAMA_RETRY_BACKOFF_MS`, `SQL_EXPLAIN_DRY_RUN`.
2. Db2 adapter: schema fix (D1), SQLSTATE error mapping (D2), timeout warnings (D3), transaction helpers (D4), gate-layering contract (D5).
3. Migrations rewritten idempotently: extended `APP_AUDIT`, new `DOCUMENT_METADATA`, `QUERY_EXECUTIONS`, DB2VS-shaped vector table (`COPILOT_KB`), grants, rollback guidance.
4. Ollama adapters: shared `httpx.Client` lifecycle, bounded retry with backoff, structured metadata logging.
5. `Db2VectorStoreAdapter`: genuine DB2VS implementation per verified contract + LangChain embeddings bridge.
6. `Db2AuditAdapter`: extended columns + sanitization.
7. New `SqlExecutionService` (validate → cap → EXPLAIN best-effort → execute → audit + QUERY_EXECUTIONS) + `/api/v1/sql/execute` + `/api/v1/ready`.
8. `backend/tests/integration/` framework (categories A–D, markers, skip rules) + offline fake-driver/mocked-HTTP unit tests.
9. Docs: 5 new integration docs + updated contract/testing/deployment docs + HANDOFF M3 plan.
