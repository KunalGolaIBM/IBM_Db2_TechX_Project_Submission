# Development guide

## Prerequisites (development machine — nothing else)

- **Python 3.14** (3.10+ should work; CI-verified on 3.14.2)
- **Node.js 20+ / npm** (built on 24.14)
- Git

**Not required for development:** Docker, Db2, Ollama, AI models — mock mode
needs none of them and downloads none of them. This is a hard project
constraint, not a suggestion.

## Setup

```powershell
# Backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt

# Frontend
cd frontend
npm install
```

## Running

```powershell
# Terminal 1 — API (mock adapters; starts with zero services)
cd backend
..\..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — UI dev server (proxies /api → 127.0.0.1:8000)
cd frontend
npm run dev          # http://127.0.0.1:5173
```

Alternative — single origin: `cd frontend && npm run build`, then run uvicorn;
the API serves `frontend/dist` at `http://127.0.0.1:8000`.

## Configuration

All behavior is environment-driven (`app/core/config.py`, pydantic-settings).
Copy `.env.example` → `.env` for local overrides. Rules:

- `.env` is gitignored and must never be tracked (verified by a test).
- Passwords are `SecretStr` — they never appear in logs, API responses, or dumps.
- Defaults are offline-safe: **missing variables never break startup.**

### Mock vs real

| | `ADAPTER_MODE=mock` (default) | `ADAPTER_MODE=real` |
|---|---|---|
| Database | Canned demo tables, SELECT-only | `ibm_db` → Db2 (needs `requirements-integration.txt` + running instance) |
| Vector store | In-memory keyword-overlap retrieval | `DB2VS` via langchain-db2 (contract implemented — **unverified**, never run against live Db2) |
| Chat/embeddings | Deterministic canned text / hash vectors | Ollama `/api/chat`, `/api/embed` (chat also needs the LangChain stack from `requirements-integration.txt`; without it real-mode chat fails closed with 503 — never mock data) |
| Audit | In-memory bounded trail | Db2 `APP_AUDIT` |
| Probes | Always `ok` | Report **true** availability (`unavailable` if a service is down) |

Real adapters are genuine implementations — they do not contain mock
fallbacks. If a service is missing you get an actionable `unavailable` probe,
never fabricated data.

## Code standards in force

- Type hints everywhere; strict `pydantic` models with `extra=forbid`.
- One module per responsibility; no giant files (largest ≈ 270 lines).
- No hardcoded credentials (enforced by `test_repo_hygiene.py`).
- No swallowed exceptions outside documented best-effort boundaries
  (health probes, audit writes, shutdown) — those log with `exc_info`.
- Errors surface through `app/core/errors.py` only.

## Useful commands

```powershell
.venv\Scripts\python -m pytest backend/tests -q      # full offline suite
cd frontend; npm run build                            # type-check + bundle
cd frontend; npx tsc -b --noEmit ...                  # (build does this)
```

## Project layout

See README → *Repository layout*, and `docs/ARCHITECTURE.md` §7 for the
module map.
