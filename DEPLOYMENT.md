# BLACKSTART AI — Render Deployment Guide

Step-by-step instructions to deploy **BLACKSTART AI** (FastAPI + IBM Db2 + LangGraph agents + React dashboard) on [Render](https://render.com).

> **Nothing has been deployed yet.** This repository only contains deployment *configuration*. Deploy only after you have reviewed `render.yaml` and set the required secrets.

---

## 1. Architecture on Render

| Component | Render service type | Name (blueprint) | Public URL (default) |
|---|---|---|---|
| FastAPI + LangGraph + ibm_db | Web Service (`runtime: python`) | `blackstart-ai-api` | `https://blackstart-ai-api.onrender.com` |
| React + TypeScript + Vite | Static Site (`runtime: static`) | `blackstart-ai-web` | `https://blackstart-ai-web.onrender.com` |

```
Browser ──► Render Static Site (CDN, SPA rewrite → index.html)
                │  VITE_API_BASE_URL (baked at build time)
                ▼
         Render Web Service (uvicorn 0.0.0.0:$PORT)
                │  /api/v1/*
                ├── LangGraph: VOLT → PULSE → CASCADE → GUARDIAN → BLACKSTART
                └── ibm_db ──► IBM Db2 (must be externally reachable)
```

Blueprint file: [`render.yaml`](render.yaml) at the repository root.

---

## 2. Prerequisites

- GitHub repository (this repo is connected to Render via Git)
- Render account (free tier works for a first bring-up; see §7 for limits)
- An **externally reachable IBM Db2** instance (see §6) — Render cannot use your laptop’s `127.0.0.1:50000`
- `git` access to push the branch that contains `render.yaml`

---

## 3. Environment variables (complete list)

### Backend — `blackstart-ai-api`

| Key | Required | Secret? | Source | Purpose |
|---|---|---|---|---|
| `PYTHON_VERSION` | No (set in blueprint) | No | blueprint `3.12.10` | Pins Python to the verified version |
| `ENVIRONMENT` | No | No | blueprint `production` | Marks the runtime environment |
| `CORS_ORIGINS` | **Yes** | No | blueprint (update if you rename services) | Comma-separated allowed browser origins. Must equal the frontend origin, e.g. `https://blackstart-ai-web.onrender.com` |
| `DB2_DSN` | **Yes** (for live grid data) | **Yes — Dashboard only** | Render Dashboard (`sync: false`) | Full ibm_db DSN: `DATABASE=...;HOSTNAME=...;PORT=50000;PROTOCOL=TCPIP;UID=...;PWD=...;` |
| `PORT` | Automatic | — | Render | Injected by Render; the start command binds `0.0.0.0:$PORT` |

`DB2_DSN` is intentionally **not** committed. Set it in **Render Dashboard → blackstart-ai-api → Environment**. If it is missing, the API still boots; `/api/v1/health` stays green and `/api/v1/db2/status` honestly reports `connected: false` with the driver message.

### Frontend — `blackstart-ai-web`

| Key | Required | Secret? | Source | Purpose |
|---|---|---|---|---|
| `NODE_VERSION` | No | No | blueprint `20` | Node version for the build |
| `VITE_API_BASE_URL` | **Yes** | No | blueprint | Backend base URL **including** `/api/v1`, e.g. `https://blackstart-ai-api.onrender.com/api/v1`. Vite inlines this into the JS bundle **at build time** |

No database credentials or LLM API keys are ever placed in the frontend.

---

## 4. Step-by-step deployment

### Step 1 — Commit configuration (when you are ready)

Files that must be in Git (already prepared):

- `render.yaml` (repo root)
- `DEPLOYMENT.md` (this file)
- `submissions/blackstart-ai/src/backend/.python-version`
- `submissions/blackstart-ai/src/backend/pytest.ini`
- `submissions/blackstart-ai/src/backend/tests/test_smoke.py`
- Backend CORS support (`app/core/config.py`, `app/main.py`)

Do **not** commit `.env`, `.env.*` (except `*.env.example`), or any real `DB2_DSN`.

```powershell
# From the repository root
git status
git add render.yaml DEPLOYMENT.md "submissions/blackstart-ai"
git commit -m "chore: add Render blueprint and deployment guide"
git push origin submission/blackstart-ai
```

> Use your actual branch name if different (`git branch --show-current`).

### Step 2 — Create the Blueprint on Render

1. Open [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect the GitHub repository (`khanadil84/Blackstart-AI`) and branch that contains `render.yaml`.
3. Render parses the blueprint and previews two services: `blackstart-ai-api` (web) and `blackstart-ai-web` (static).
4. Confirm/create. Render starts the first backend deploy.

**Manual alternative (no Blueprint):** create the two services by hand using the settings in §5, then add the SPA rewrite in the static site’s **Redirects/Rewrites** tab.

### Step 3 — Set the backend secret

1. Open **blackstart-ai-api** → **Environment**.
2. Add `DB2_DSN` (mark as secret) with your Db2 connection string from §6.
3. Confirm `CORS_ORIGINS` matches the frontend URL (blueprint default: `https://blackstart-ai-web.onrender.com`).
4. Save; Render redeploys.

### Step 4 — Wait for backend health

- Render pings `GET /api/v1/health` (must return HTTP 200).
- Verify manually:

```powershell
curl.exe https://blackstart-ai-api.onrender.com/api/v1/health
curl.exe https://blackstart-ai-api.onrender.com/api/v1/db2/status
```

Expected when Db2 is configured and reachable:

```json
{"status":"healthy","application":"BLACKSTART AI","version":"1.0.0"}
{"connected":true,"message":"IBM Db2 connection successful."}
```

If `DB2_DSN` is missing or the host is unreachable, `/api/v1/db2/status` returns `{"connected":false,"message":"..."}` — this is intentional, not a fake success.

### Step 5 — Deploy / verify the frontend

The blueprint sets `VITE_API_BASE_URL` at build time. After the static site deploy:

1. Open `https://blackstart-ai-web.onrender.com`.
2. Sidebar should show **FastAPI online** and **IBM Db2 · Connected** (once `DB2_DSN` is set).
3. Deep-link check: `https://blackstart-ai-web.onrender.com/agents` must render (SPA rewrite), not 404.
4. Click **Run Intelligence Analysis** — five agents run server-side; dashboard shows findings.

If the frontend shows “Backend unreachable”, the baked `VITE_API_BASE_URL` is wrong or `CORS_ORIGINS` does not include the frontend origin — fix and **rebuild** the static site (env vars are build-time).

### Step 6 — Smoke-test the API

```powershell
curl.exe https://blackstart-ai-api.onrender.com/
curl.exe https://blackstart-ai-api.onrender.com/api/v1/health
curl.exe https://blackstart-ai-api.onrender.com/api/v1/db2/status
curl.exe https://blackstart-ai-api.onrender.com/api/v1/overview
curl.exe -X POST https://blackstart-ai-api.onrender.com/api/v1/analyze
```

`/overview` and `/analyze` need a reachable Db2; each may take ~10s (fresh connection per table). `POST /analyze` returns `execution_mode: "ADVISORY_ONLY"` with all five agents.

---

## 5. Service settings reference (manual setup)

### Backend — Web Service

| Setting | Value |
|---|---|
| Name | `blackstart-ai-api` |
| Runtime | Python |
| Root directory | `submissions/blackstart-ai/src/backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/v1/health` |
| Python version | `3.12.10` (via `.python-version` or `PYTHON_VERSION`) |

### Frontend — Static Site

| Setting | Value |
|---|---|
| Name | `blackstart-ai-web` |
| Root directory | `submissions/blackstart-ai/src/frontend` |
| Build command | `npm ci && npm run build` |
| Publish directory | `dist` |
| SPA rewrite | Source `/*` → Destination `/index.html` → **Rewrite** |
| Node version | `20` (`NODE_VERSION`) |
| Build env | `VITE_API_BASE_URL=https://blackstart-ai-api.onrender.com/api/v1` |

---

## 6. IBM Db2 hosting requirements (Phase 4)

### What this app expects

- One IBM Db2 database reachable over **TCPIP** from Render’s runtime (public internet or a private link Render can use).
- Tables already used by the code (do not replace Db2 with SQLite/mock data):
  - `POWER_PLANT`, `SUBSTATION`, `TRANSMISSION_LINE`, `GRID_INCIDENT`, `AGENT_EVENT`
- A single env var consumed by the backend: **`DB2_DSN`** (ibm_db DSN format).

### What will NOT work from Render

| Source | Reachable from Render? |
|---|---|
| Db2 on `127.0.0.1:50000` on your laptop | **No** |
| Db2 in local Docker/WSL published only on localhost | **No** |
| Db2 on a LAN IP without public exposure | **No** |
| IBM Cloud Db2 (public endpoint + credentials) | **Yes**, if firewall/IP rules allow Render |
| Any VM/container with a public hostname + open port 50000 (or your port) + TLS/SSL policy as required | **Yes**, if network path is open |

Do **not** assume a local Docker Db2 container is accessible from Render.

### Recommended options

1. **IBM Cloud Db2 (Lite/Standard)**  
   - Create a Db2 service instance, get hostname/port/credentials/DB name.  
   - Build:  
     `DB2_DSN=DATABASE=<db>;HOSTNAME=<public-host>;PORT=<port>;PROTOCOL=TCPIP;UID=<user>;PWD=<password>;`  
   - Store only in Render’s secret env (Dashboard → Environment → *mark as secret*).  
   - Restrict network access per IBM Cloud guidance; rotate credentials if exposed.

2. **Db2 on a publicly reachable server**  
   - Db2 server configured for TCPIP, listening on a public interface (or via a controlled proxy/tunnel you operate).  
   - Security: strong password, TLS where supported, IP allow-listing, no credentials in Git or client bundles.

3. **Private connectivity** (advanced)  
   - Only if your Render plan/network setup supports it; not required for this submission.

### Security rules (mandatory)

- Never commit `DB2_DSN`, passwords, or `PWD=` fragments to Git (root `.gitignore` already ignores `.env`).
- Never expose `DB2_DSN` in the frontend (`VITE_*` vars are public).
- Treat Render env values as production secrets; rotate on any suspected leak.
- Failure modes stay honest:
  - Missing DSN → `Db2 DSN is not configured.` on status/detail paths
  - Unreachable host → driver error string in `/api/v1/db2/status`
  - `/overview` → HTTP 503 with the error detail when queries fail
  - Health endpoint does **not** fake a DB connection

---

## 7. Plans, limits, and operational notes

- **Free web services sleep** after inactivity → first request may be slow (cold start). Static site stays on CDN.
- **Memory:** LangGraph + LangChain imports can be heavy for the free tier. If the backend is killed with OOM during start, upgrade the service plan (e.g. Starter) or trim unused optional dependencies — do not remove the five agents.
- **Latency:** `/overview` and `/analyze` open a fresh Db2 connection per table (~4 connections) and block the event loop; expect multi-second responses. Frontend timeout is 30s (60s for analyze).
- **CORS:** must list the exact frontend origin(s). Wildcard `*` is for local dev only; production blueprint uses the concrete `https://blackstart-ai-web.onrender.com`.
- **Service renames:** if you rename either Render service, update **both** `CORS_ORIGINS` (backend) and `VITE_API_BASE_URL` (frontend, then **redeploy** the static site).

---

## 8. Pre-deploy verification (run locally)

```powershell
# Backend unit/smoke tests (from src/backend, using the venv)
cd "submissions\blackstart-ai\src\backend"
.\.venv\Scripts\python.exe -m pytest

# Frontend typecheck + production build
cd "..\frontend"
npm run typecheck
npm run build
```

Expected: pytest all green (health, CORS, API prefix, five agents offline); `npm run build` exits 0 (`tsc --noEmit && vite build`).

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend deploy fails on health check | Wrong start command / not binding `0.0.0.0:$PORT` | Use blueprint start command exactly |
| `pip install` fails on `ibm_db` | Wheel/platform issue on Render image | Check build logs; ensure Python `3.12.10`; ibm_db manylinux wheels normally install cleanly |
| Frontend loads but “Backend unreachable” | Wrong/missing `VITE_API_BASE_URL` at build time | Fix env var → **Manual redeploy** (rebuild) |
| CORS error in browser | `CORS_ORIGINS` missing frontend origin | Set exact origin → redeploy backend |
| Refresh on `/agents` → 404 | Missing SPA rewrite | Ensure blueprint `routes` rewrite `/*` → `/index.html` |
| `/db2/status` → `connected: false` | Missing `DB2_DSN` or Db2 not publicly reachable | Set secret; verify host/port/credentials from an external network |
| `/overview` → 503 | Db2 query failure | Read `detail` in response; fix DSN/network |
| Backend OOM on free tier | Memory limit | Upgrade plan; avoid adding heavy unused packages |

---

## 10. What was intentionally not changed

- Dashboard UI/UX, branding, and all seven pages
- The five agents and LangGraph workflow (`app/orchestration/graph.py`)
- API routes and `/api/v1` prefixes
- IBM Db2 as the system of record (no SQLite/mock substitution)
- Advisory-only / demonstration-only safety labels

---

## 11. File manifest (deployment-related)

| Path | Action |
|---|---|
| `render.yaml` | **Created** — Blueprint (backend web service + frontend static site) |
| `DEPLOYMENT.md` | **Created** — this guide |
| `src/backend/app/core/config.py` | **Modified** — `cors_origins` + `parse_cors_origins` |
| `src/backend/app/main.py` | **Modified** — CORS from `CORS_ORIGINS` (default `*` for local) |
| `src/backend/.python-version` | **Created** — `3.12.10` for Render |
| `src/backend/pytest.ini` | **Created** — pythonpath/testpaths for smoke tests |
| `src/backend/tests/test_smoke.py` | **Created** — health, CORS, API prefix, five-agent offline test |
| `src/backend/requirements.txt` | Existing — pinned runtime deps (includes pytest/httpx for tests) |
| `.env.example` | **Modified** — documents `CORS_ORIGINS` |
| `src/frontend/.env.example` | **Modified** — documents Render `VITE_API_BASE_URL` |
