# Testing

**Rule: every test in this suite runs offline.** No Docker, no Db2, no
Ollama, no model downloads, no network beyond loopback (`127.0.0.1`).

## Commands

```powershell
# Backend — full offline suite
.venv\Scripts\python -m pytest -q

# Frontend — strict type-check + production build
cd frontend; npm run build
```

## Test taxonomy — read this before trusting a green run

| # | Category | Status | What it proves |
|---|---|---|---|
| 1 | **Offline unit tests** | ✅ passing | Validation gate, injection rules, config validation (incl. approval/agent bounds), mock adapter behavior, error envelope, approval state machine, admin credential guards |
| 2 | **Mock integration tests** | ✅ passing | Full HTTP request → service → mock adapter flows via FastAPI `TestClient` (no real services), incl. SQL execute/explain/DBA APIs and the approval & admin-credential safety contracts |
| 3 | Real Db2 integration tests | ⚠️ **unverified** | Connection, readonly execution, SYSCAT introspection, `APP_AUDIT` writes against a live Db2 CE instance. One opt-in test exists (`test_db2_dialect_integration.py`) but **fails when enabled on this machine** (Application Control blocks the `ibm_db` DLL) — it has never passed here |
| 4 | Real Ollama inference tests | ⏳ **not written** | `granite4.2:3b` generation + `nomic-embed-text` embeddings against a live Ollama server |
| 5 | Real Db2 vector retrieval tests | ⏳ **not written** | `DB2VS` round trip: upsert → `similarity_search_with_score` → metadata filters → persistence after reconnect |

**A passing suite in categories 1–2 says NOTHING about real-service
behavior.** Never report mock tests as real integration tests. Category 3 is
opt-in (`@pytest.mark.integration`, gated in `conftest.py` on
`ADAPTER_MODE=real` + `RUN_REAL_INTEGRATION=1`); categories 4–5 are written
once infrastructure exists.

## Backend coverage map (`backend/tests/` — 18 files)

| File | Requirement §9 coverage |
|---|---|
| `test_app.py` | Application startup, root, request-id middleware, 404/422 envelopes, OpenAPI surface |
| `test_health_status.py` | Health endpoint, degraded-not-down probe behavior, status endpoint, no secret leakage |
| `test_config.py` | Config loading, env overrides, missing env vars → safe defaults, invalid config rejected (`environment`, `adapter_mode`, `injection_mode`, `log_level`, port range), `SecretStr` never serialized, `agent_max_tool_calls`/`approval_ttl_seconds` bounds, `agent_actions_enabled` default false, admin credentials absent from serialization |
| `test_sql_security.py` | Valid SELECT · INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT/MERGE rejection · `SELECT INTO` · multi-statement · malformed fail-closed · empty/NUL/control chars · over-length · catalog deny-list · denied functions · join/IN-list/subquery limits · row-limit advisory · policy echo |
| `test_injection.py` | Attack detection, benign pass-through, block raises, flag verdicts, `off` mode, **layering check**: SQL-payload phrasing belongs to the SQL gate |
| `test_adapters.py` | Mock DB (SELECT, `FETCH FIRST`, non-SELECT refusal, schema), mock vector (scoring, filters, upsert), mock LLM/embeddings determinism, mock audit, orchestrator intents + gate-passing SQL, **registry DI: mock mode vs real mode — real never instantiates mocks**, probes never raise, idempotent shutdown |
| `test_chat_api.py` | Chat docs/data flows, mode override, injection → 400, audit append (incl. `BLOCKED`), SQL validate outcomes, limits validation, no secret leakage |
| `test_db2_unit.py` | Fake-driver adapter unit tests: DSN built without credentials, read-only connect args, row cap + `SET CURRENT QUERY TIMEOUT`, audit column binding, sanitized errors (password never leaks) |
| `test_db2_dba_explain.py` | Real-mode-but-offline adapter suite (fake `ibm_db_dbi`, never native): EXPLAIN plan capture/cleanup, DBA tool binding + caps, SQLSTATE→HTTP mapping, SQLAlchemy URL password masking, HTTP contract tests |
| `test_dba_specs.py` | DBA templates are single parameterized SELECTs; clamped/validated limits; injection-shaped identifiers and system schemas refused |
| `test_dba_api.py` | DBA HTTP endpoints: every tool runs in mock mode, limit truncation flags, unknown tool → 404, monitoring statement text redacted, audit |
| `test_explain.py` | ExplainService: labelled mock plans, unsafe SQL rejected **before** the database, audited, graceful `UNAVAILABLE`/`FAILED` (never raises) |
| `test_sql_execute_api.py` | `/sql/execute` HTTP: hard row-cap wrapper, existing small `FETCH FIRST` preserved, EXPLAIN status reported |
| `test_sql_execution_service.py` | Execution pipeline: timeout recorded as timeout, timeout from policy, truncation warning + flag, `_json_safe` driver-type normalization |
| `test_approvals.py` | **M3 approval workflow safety contract**: PENDING/never-executed-on-propose, 409 invalid transitions, 410 expiry, statement/param tamper detection, action allow-list + forbidden verbs + reserved schemas, parameter validation, normalized statement rendering, every transition audited, audit failure never masks outcome, actor sanitization, password-free failure detail, `ACTIONS_DISABLED`/`ADMIN_NOT_CONFIGURED` → recorded-not-executed, execution only after approval, exact `"approve"`/`"reject"` decision validation (invalid values raise 422 before any state change) |
| `test_approval_api.py` | HTTP proposal/list/detail/decision workflow, prevalidation without partial approvals, tool-call bounds, invalid/missing IDs, expiry and terminal decisions, sanitized actors, simulated execution, and audit preservation |
| `test_knowledge_api.py` | Mock-mode ingestion, retrieval of an ingested document, and batch-size validation |
| `test_admin_credentials.py` | **Privileged admin path**: `connect_args` vs `admin_connect_args` separation, read-only path never receives admin credentials, `sanitize()` strips both passwords, guard order (disabled / unconfigured / multi-statement refuse **before** connecting), privileged connect + commit only after all safeguards, rollback + close on failure, mock adapter is simulation-only, `SecretStr` never serialized, `GET /api/v1/config` leaks no secrets |
| `test_repo_hygiene.py` | No credential-like literals in source, `.env.example` placeholders only, `.env` never git-tracked, `.gitignore` coverage |
| `test_db2_dialect_integration.py` | **Opt-in only** (`integration` marker): native-driver dialect load — **unverified on this machine** (Application Control blocks `ibm_db`) |

Current run: **389 passed, 1 skipped** (offline). The 1 skip is the opt-in
integration test above — a skipped integration test is *not* a verified
integration.

## Frontend checks

- `npm run build` = `tsc -b` (strict) **and** production bundle — a type-level
  contract check against `src/api/types.ts`, which mirrors the backend models.
- Behavior verified by the M1 smoke procedure below (manual, offline).

## Smoke test (end-to-end, offline)

1. `cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --port 8000`
2. `cd frontend; npm run build` (backend then serves the SPA at `/`)
3. `GET /api/v1/health` → `status: ok`, `mode: mock`, 6 checks
4. `GET /api/v1/status` → database/vector/llm/embeddings populated
5. `POST /api/v1/chat {"message":"What is DB2VS?"}` → `intent: docs`, citations, `mock: true`
6. `POST /api/v1/chat {"message":"List servers by uptime"}` → `sql` present; re-submit that SQL to `/api/v1/sql/validate` → `valid: true`
7. `POST /api/v1/chat` with an instruction-override message → 400 `PROMPT_INJECTION_BLOCKED`
8. UI at `/` renders Dashboard, sends a chat message, shows config — all without Docker/Db2/Ollama

## Notes

- Tests construct fresh apps and clear the settings cache per fixture, so env
  pollution between tests is impossible.
- `TestClient` is used with `raise_server_exceptions=False` so the global
  500-envelope handler itself is exercised where relevant.
