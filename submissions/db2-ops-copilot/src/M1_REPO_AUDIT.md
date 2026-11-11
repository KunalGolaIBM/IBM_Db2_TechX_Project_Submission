# M1 Repository Audit — baseline `5ff5f6a`

**Auditor:** M1 engineering pass (read-only inspection of the M0 baseline before any implementation)
**Date:** 31 October 2026
**Baseline commit:** `5ff5f6a75af48390eeb9aebf9611f657f7ef45d4` (branch `main`)

This document records what existed at the M1 baseline, what was missing or
defective, and what was deliberately preserved. All findings below were fixed
on `feature/m1-portable-foundation` without rewriting the preserved work.

## 1. What existed and was preserved

| Area | State at baseline |
|---|---|
| App entry point | Complete: `create_app()` factory, lifespan (logging → registry → shutdown), request-id ASGI middleware, CORS allow-list (no wildcard), global exception handlers, static frontend mount hook, JSON 404 for unknown `/api/*` |
| API v1 surface | Complete: `/health`, `/status`, `/config`, `/chat`, `/sql/validate`, `/audit` + aggregated router |
| Configuration | Pydantic-settings with `SecretStr` passwords, env aliases matching `.env.example`, validators for CSV fields and log level |
| Adapter contracts | Complete Protocols in `adapters/base.py`: database, vector store, chat model, embeddings, orchestrator, SQL validator, audit |
| Mock adapters | All 6 present, deterministic, offline (canned demo data, hash-based embeddings, keyword-overlap retrieval, in-memory audit) |
| Real adapters | Genuinely implemented (not mocks in disguise): `ibm_db`/`ibm_db_dbi` Db2 adapter, Ollama REST (`/api/chat`, `/api/embed`, `/api/tags`) via httpx, LangChain orchestrator composing real leaf adapters; DB2VS wiring honestly deferred with actionable errors |
| Registry/DI | Mock-vs-real selection from settings; parallel crash-safe probes; graceful `close_all()` |
| SQL security | Fail-closed sqlglot validator (8 layers: hygiene → parse → single-statement → SELECT-only → forbidden nodes → catalog deny-list → denied functions → complexity limits), official `db2-sqlglot-dialect` plugin, row-limit advisory; prompt-injection rules with block/flag/off modes |
| Error handling | Unified JSON envelope `{"error": {code, message, request_id, detail}}` for AppError / validation / HTTP / unhandled |
| Requirements | Split runtime / dev / integration files; integration deps pinned from M0 PyPI verification |
| `.env.example` | Present with placeholders only |

## 2. Findings (defects and gaps)

| # | Severity | Finding | Resolution in M1 |
|---|---|---|---|
| 1 | High | **No tests existed** — `pyproject.toml` referenced `backend/tests` and `tests`, neither present | Created `backend/tests/` (100 offline tests, see TESTING.md) |
| 2 | Medium | **`httpx` dependency gap** — imported at module level by the real Ollama adapters, which the registry imports unconditionally (even in mock mode); `httpx` was only in `requirements-dev.txt` | Moved to `requirements.txt` as a runtime dependency |
| 3 | Medium | **No frontend** — `main.py` served `frontend/dist` when present, but no `frontend/` existed | Built React 19 + TypeScript + Vite SPA (dashboard, chat workspace, configuration) |
| 4 | Medium | **No database scripts** — `db2_audit.py` referenced `database/migrations/003_readonly_user.sql`, which did not exist | Authored `database/migrations/001–003` + `database/README.md` (never executed — M2) |
| 5 | Medium | **No documentation** — `README.md`, `docs/ARCHITECTURE.md`, `DEPLOYMENT.md` referenced in code comments but absent | Created README + `docs/` (architecture, API contract, development, testing, deployment) |
| 6 | Low | **Latent bug** — `mock_db.py` used `Sequence` in a signature without importing it (masked by postponed annotation evaluation; would `NameError` under runtime type evaluation) | Fixed import |
| 7 | Low | **`.env.example` incomplete** — omitted `ADAPTER_MODE`, `ENVIRONMENT`, `CORS_ORIGINS`, `INJECTION_MODE`, SQL limits, timeouts | Rewrote with every variable documented |
| 8 | Low | **`screen_message(mode="off")` still flagged** — implementation contradicted its documented contract ("detection disabled") | Fixed: `off` now returns a clean verdict; contract test added |
| 9 | Low | **`db2_port` unvalidated** — accepted out-of-range values | Added `ge=1, le=65535` |
| 10 | Info | **`HANDOFF.md` stale** — described "no application code, no remote configured" | Rewritten at M1 completion |

## 3. Explicit non-findings (checked, clean)

- **No credentials** anywhere: no hardcoded passwords/tokens in source, no `.env` committed, `.env.example` placeholders only; `SecretStr` used for passwords; DSN builder keeps credentials out of DSN strings; error sanitizer strips password values.
- **No fake production paths**: mock adapters are distinct classes; `ADAPTER_MODE=real` never falls back to mocks; real adapters fail with actionable errors rather than canned success.
- **No swallowed exceptions** beyond documented best-effort boundaries (health probes, audit writes, `close_all`) — each logs with `exc_info`.
- Git history preserved; baseline commits untouched.

## 4. Preserved verbatim

All M0 research, architecture decisions and handoff documents; every existing
backend module (defect fixes above are minimal, targeted edits); the pinned
integration dependency versions; the MIT LICENSE from the remote.
