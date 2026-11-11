# Deployment

> **Status: runbook only — never executed.** As of M3 no infrastructure
> exists on the development machine (no Db2, no Ollama, migrations never
> run), so every step below is an *unverified* procedure to be performed on
> an operator-approved machine.

## 1. Prerequisites (user-facing list)

| Requirement | Version / notes |
|---|---|
| Linux or Windows host | ≥ 16 GB RAM free recommended (Db2 CE is licensed ≤ 16 GB / 4 cores) |
| Docker Engine / Docker Desktop | Any recent (24+) — required **only** for Db2 |
| IBM Db2 Community Edition image | `icr.io/db2_community/db2`, tag **≥ 12.1.2** (VECTOR support; confirm via `db2level`) |
| Ollama | For local inference; models: `granite4.2:3b` (~2.2 GB), `nomic-embed-text:v1.5` (~274 MB) |
| Python | 3.10+ (pinned & verified on 3.14.2) |
| Node.js | 20+ (build verified on 24.14) — build-time only |
| Ports | `8000` (API, localhost), `50000` (Db2, **bound to 127.0.0.1 only**), `11434` (Ollama, localhost) |

Never publish the Db2 or Ollama ports to a public interface.

## 2. Full bring-up order (M2)

```powershell
# 1. Python deps (integration set is pinned in requirements-integration.txt)
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements-integration.txt   # ibm_db, langchain stack

# 2. Db2 Community Edition (see database/README.md for details)
docker run -d --name db2server --restart unless-stopped \
  -e DB2_INSTANCE_PASSWORD=$env:DB2_INSTANCE_PASSWORD \
  -p 127.0.0.1:50000:50000 \
  -v db2_data:/database \
  icr.io/db2_community/db2:12.1.2
# wait for healthy, then apply migrations in order:
db2 -tvf database/migrations/001_app_schema.sql
db2 -tvf database/migrations/002_indexes.sql
db2 -tvf database/migrations/003_readonly_user.sql   # after substituting placeholders

# 3. Ollama
ollama pull granite4.2:3b
ollama pull nomic-embed-text:v1.5

# 4. Configure
Copy-Item .env.example .env    # then fill DB2_RO_PASSWORD etc. (local secrets only)

# 5. Run with REAL adapters
$env:ADAPTER_MODE = "real"
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check first: `GET /api/v1/health` must show `mode: real` with truthful
per-probe status. If a service is down, the app **still starts** and reports
that service `unavailable`.

## 3. Frontend build

```powershell
cd frontend; npm install; npm run build   # emits frontend/dist
```
FastAPI serves `dist/` at `/` automatically (`SERVE_FRONTEND=true`). Behind a
reverse proxy/CDN, set `SERVE_FRONTEND=false` and serve `dist/` there instead.

## 4. Production settings checklist

| Variable | Production value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `ADAPTER_MODE` | `real` |
| `CORS_ORIGINS` | exact origin list — never `*` |
| `INJECTION_MODE` | `block` (default) |
| `SERVE_FRONTEND` | `false` behind a proxy, else `true` |
| `DB2_*` / `OLLAMA_*` | loopback addresses; passwords via env/secret store, never files in the repo |

## 5. Security notes for operators

- The app connects as **db2ro** (SELECT-only + audit INSERT). If the SQL gate
  were ever bypassed, the grants still prevent modification — do not broaden them.
- Passwords: generate locally (`secrets.token_urlsafe(24)`), store in `.env`
  or a secret manager. Never in code, scripts, images, or logs.
- Keep TLS at the reverse proxy; the API itself binds localhost.
- Rotate `DB2_RO_PASSWORD` via Db2 `CHANGE PASSWORD` and update the env.

## 6. Future hardening (post-M2 backlog)

- Containerize backend+frontend (multi-stage image, non-root user), compose
  file with pinned Db2/Ollama services.
- Readiness endpoint gating on `ADAPTER_MODE=real` for orchestrators.
- Rate limiting, structured JSON log shipping, metrics.
