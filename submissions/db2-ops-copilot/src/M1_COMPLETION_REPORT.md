# M1 Completion Report — Portable Project Foundation

**Milestone:** M1 — Portable Project Foundation
**Date:** 31 October 2026 (IST)
**Branch:** `feature/m1-portable-foundation` (from baseline `5ff5f6a75af48390eeb9aebf9611f657f7ef45d4`)
**Commit:** `feat(m1): complete portable project foundation`
**Constraint honored:** ✅ No Docker/Db2/Ollama installed, no models downloaded, no containers touched, no WSL/system changes, no significant C: usage (npm packages only, on E:).

---

## 1. Existing code audit (summary — full detail in `M1_REPO_AUDIT.md`)

Baseline `5ff5f6a` was substantially complete and was **extended, not replaced**:
app factory/lifespan, 6 API endpoints, DI, error envelope, adapter Protocols,
6 mock + 6 real adapters, fail-closed sqlglot gate, injection screening,
`SecretStr` config — all preserved.

**10 findings, all resolved:**

| # | Finding | Severity |
|---|---|---|
| 1 | No tests existed (pyproject referenced nonexistent dirs) | High |
| 2 | `httpx` missing from runtime requirements (module-level import in real Ollama adapters, loaded even in mock mode) | Medium |
| 3 | No frontend (despite `main.py` serving `frontend/dist`) | Medium |
| 4 | No `database/` scripts (referenced by code) | Medium |
| 5 | No README / docs (referenced by code comments) | Medium |
| 6 | `mock_db.py` missing `Sequence` import (latent NameError) | Low |
| 7 | `.env.example` missing 12 variables | Low |
| 8 | `screen_message(mode="off")` still flagged (contract violation) | Low |
| 9 | `db2_port` accepted out-of-range values | Low |
| 10 | `HANDOFF.md` stale | Info |

**Clean checks:** no credentials anywhere; no fake-production mock paths; no swallowed exceptions outside documented best-effort boundaries; git history preserved.

## 2. Files created

| Path | Purpose |
|---|---|
| `backend/tests/` (9 files) | 100-test offline suite: `conftest.py`, `test_app.py`, `test_health_status.py`, `test_config.py`, `test_sql_security.py`, `test_injection.py`, `test_adapters.py`, `test_chat_api.py`, `test_repo_hygiene.py` |
| `frontend/` (17 files) | React 19 + TS + Vite SPA: shell/sidebar, Dashboard, Chat workspace, Configuration pages, typed API client, hooks, UI states, styles, config files |
| `database/migrations/001_app_schema.sql` | APP schema, demo tables, `APP_AUDIT`, `KB_CHUNKS VECTOR(768, FLOAT32)` |
| `database/migrations/002_indexes.sql` | Audit/introspection indexes |
| `database/migrations/003_readonly_user.sql` | Least-privilege GRANTs for `db2ro` |
| `database/README.md` | Setup instructions (M2), schema overview, security notes |
| `docs/ARCHITECTURE.md` | Layered architecture, 8 ADRs, chat lifecycle, **security defaults**, data model |
| `docs/API_CONTRACT.md` | Every endpoint's request/response shape + error codes |
| `docs/DEVELOPMENT.md` | Offline setup, run commands, mock/real matrix, standards |
| `docs/TESTING.md` | **5-category test taxonomy**, coverage map, smoke procedure |
| `docs/DEPLOYMENT.md` | Prerequisites list, M2 bring-up runbook, production settings |
| `README.md` | Purpose, quick start, API table, repo layout |
| `M1_REPO_AUDIT.md` | Documented baseline audit (acceptance item 1) |
| `M1_COMPLETION_REPORT.md` | This document |

## 3. Files modified

| Path | Change |
|---|---|
| `backend/app/adapters/db/mock_db.py` | +`Sequence` import (bug fix) |
| `backend/app/core/config.py` | `db2_port` range validation (`ge=1, le=65535`) |
| `backend/app/security/injection.py` | `mode="off"` now honors its documented "detection disabled" contract |
| `.env.example` | Fully documented: 28 lines → complete variable reference (all settings grouped: app, adapters, Db2, Ollama, SQL policy, security) |
| `requirements.txt` | +`httpx>=0.27,<1.0` as runtime dependency (with rationale comment) |
| `requirements-dev.txt` | −`httpx` (promoted to runtime) |
| `HANDOFF.md` | Rewritten: M1 complete, M0 preserved, **exact M2 task list** |
| `frontend/.gitignore` | node_modules, dist, tsbuildinfo |

## 4. Backend functionality completed

- **Entry point:** factory + lifespan (logging → adapter registry → shutdown), request-id ASGI middleware (echoed + logged), CORS allow-list (no wildcard), unified JSON error envelope for 4 handler classes, static SPA mount with API-priority routing.
- **Endpoints:** `GET /api/v1/health` (200 + `degraded` when services down — never a startup failure), `GET /api/v1/status` (db/vector/llm/embeddings; **zero secrets**), `GET /api/v1/config` (non-secret effective config), `POST /api/v1/chat`, `POST /api/v1/sql/validate`, `GET /api/v1/audit`.
- **Adapter contracts:** complete Protocol surface — DB (ping, readonly execute, schema introspection, timeout; connection-per-call; parameterized app queries), vector store (search, filters, upsert, count), AI (chat generate, embed, model availability), orchestration, audit.
- **DI:** registry built once at startup from settings; services per-request; tests swap cleanly.
- **Database scripts:** audit schema, document metadata (`KB_CHUNKS`), query metadata (demo + audit), grants — authored, documented, **not executed**.

## 5. Frontend functionality completed

Sidebar shell + 3 routed pages, all wired to the live API (Vite proxy; served statically in prod):
- **Dashboard:** health header (status/mode/version/uptime), per-probe rows, DB/vector/LLM/embeddings cards, Refresh.
- **Chat workspace:** mode selector (auto/rag/sql), user/assistant messages, intent + **mock badges**, citations, SQL block, blocked-injection error state, pending spinner, empty state.
- **Configuration:** effective config sections (app/db/models/SQL policy/security) + recent audit table with status badges.
- Cross-cutting: typed API client normalizing failures into `ApiClientError`; loading/error/empty states everywhere; responsive layout; strict TS build.

## 6. Architecture decisions

1. **Extended, not duplicated** — existing modules were audited and patched with minimal targeted edits (see §3); no parallel structures created.
2. **Adapters promoted to runtime deps** — `httpx` moved to `requirements.txt` rather than making imports lazy, keeping module structure simple and import-time failures honest.
3. **Mock/real honesty** — test-enforced: `ADAPTER_MODE=real` never instantiates a mock; real adapters fail with actionable `unavailable` detail (DB2VS stub documents its exact M2 wiring steps).
4. **Validation ≠ boundary** — documented in ARCHITECTURE + `003_readonly_user.sql`: grants, row caps, timeouts, parameterization and audit are the independent layers.
5. **Frontend contract = backend contract** — `src/api/types.ts` mirrors strict Pydantic models; drift fails `tsc`.
6. **Single-origin prod** — FastAPI serves `dist/`; Vite proxy in dev (one CORS story).

## 7. Dependencies added

- Runtime: **`httpx>=0.27,<1.0`** (already installed; used by real Ollama adapters).
- Dev: none new beyond existing `pytest` (`httpx` promoted out).
- Frontend (`package.json`, lockfile committed): `react`, `react-dom`, `react-router-dom`; dev: `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react(-dom)`.
- Integration set unchanged and **not installed** (pinned from M0 PyPI verification).

## 8. Offline test results

| Suite | Result |
|---|---|
| Backend (`pytest backend/tests`) | ✅ **100 passed in ~1.0 s** — zero failures, offline |
| Frontend (`npm run build`) | ✅ `tsc -b` strict + Vite bundle — `dist/` 275 kB JS (87 kB gzip), 7 kB CSS |
| End-to-end smoke (uvicorn + built SPA) | ✅ health `ok`/6 checks · status db+llm+5 docs · config · chat `docs` intent +2 citations · `/` serves SPA |

Coverage by requirement §9: startup ✅ · health ✅ · status ✅ · config
loading ✅ · missing env vars ✅ · invalid config ✅ · exception handling ✅ ·
mock adapters ✅ · DI ✅ · SQL matrix (SELECT/INSERT/UPDATE/DELETE/DROP/
multi/malformed/catalog/limits) ✅ · injection ✅ · repo hygiene ✅ ·
frontend build ✅ · API contract (types + strict models) ✅.

## 9. Security checks

- ✅ No credentials in source, tests, fixtures, or `.env.example` (regex-enforced test).
- ✅ `.env` never git-tracked (test); `.gitignore` covers `.env*`, `.venv`, caches, `*.pem/*.key`, `node_modules`, build outputs, `*.tar.gz` (test-verified).
- ✅ Status/config/chat/audit responses contain no password/secret/token material (tests).
- ✅ `SecretStr` serialization blocked; DSN excludes credentials; error sanitizer strips password values.
- ✅ Prompt-injection default `block` (400 + rule IDs); SQL gate fail-closed; row cap + timeout policy echoed to clients.
- ✅ Static validation explicitly **not** claimed as complete production security (documented).

## 10. Mocked functionality (honest list)

Mock mode (default) provides: demo DB with canned fleet/incident data;
keyword-overlap retrieval over 5 seeded docs; canned replies marked **"MOCK
MODE"**; deterministic hash embeddings; in-memory audit (3 seed entries). All
mock responses surface `mock: true` / `mode: mock` badges in API and UI.
**Never used in real mode** — enforced by `test_registry_real_mode_never_uses_mock_adapters`.

## 11. Pending real-service tests (M2)

1. **Real Db2:** connectivity, `db2ro` permission matrix, SYSCAT introspection, readonly execution with row cap/timeout, `APP_AUDIT` writes/reads, VECTOR type verification — *blocked on infrastructure approval*.
2. **Real Ollama:** `granite4.2:3b` generation, `nomic-embed-text` embeddings, latency/token counts — *blocked*.
3. **Real Db2 vector retrieval:** `DB2VS` upsert → `similarity_search_with_score` → metadata → reconnect persistence (no in-memory substitutes) — *blocked*.
4. E2E with live services: RAG citations from real retrieval, text-to-SQL EXPLAIN dry-run + execution under `db2ro`.

These will live in `backend/tests/integration/` marked `@pytest.mark.integration`, skipped unless `ADAPTER_MODE=real` with reachable services (see `docs/TESTING.md`).

## 12. Acceptance criteria

- [x] Existing repository audit documented (`M1_REPO_AUDIT.md`)
- [x] Backend starts offline (uvicorn smoke + lifespan tests)
- [x] Frontend starts offline (`npm run dev` proxy; build served at `/`)
- [x] Health and status APIs work
- [x] Configuration is environment-driven (pydantic-settings + full `.env.example`)
- [x] Db2 adapter contracts complete
- [x] Ollama adapter contracts complete
- [x] Mock adapters work (dedicated tests)
- [x] Database initialization scripts exist (`database/migrations/001–003`)
- [x] SQL validation tests pass (100-test suite)
- [x] Security defaults documented (`docs/ARCHITECTURE.md`, `.env.example`)
- [x] Frontend communicates with the backend (typed client + smoke)
- [x] Automated offline tests pass (100/100)
- [x] Frontend production build passes
- [x] Documentation updated (README + 5 docs + HANDOFF)
- [x] `HANDOFF.md` describes exact M2 tasks
- [x] No Docker/Ollama/Db2 installations occurred
- [x] No AI models were downloaded

## 13. Git & verification

- Baseline recorded: `5ff5f6a75af48390eeb9aebf9611f657f7ef45d4` on `main`.
- Work done entirely on `feature/m1-portable-foundation`; integrated via **merge (no force-push)**; remote history untouched.
- Diff inspected; secrets/generated files checked (`node_modules/`, `dist/`, `*.tsbuildinfo`, `__pycache__` all ignored; `package-lock.json` intentionally tracked).
- Push + merge verification: see final report in the M1 handoff message / `git log origin/main`.
