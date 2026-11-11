# M1 ENVIRONMENT REPORT — Infrastructure & Environment Setup (PARTIAL — PAUSED)

**Milestone:** M1 — Infrastructure & Environment Setup
**Status:** ⏸️ **PAUSED by operator decision** after M1.2 (Docker migration cancelled). M1.3 (Ollama), M1.4 (Db2 CE), M1.5 (Python venv), M1.6 (vector PoC) are **NOT started**.
**Date:** 30 October 2026 (IST)
**Workspace:** `E:\future\Db2Hack`

Verification legend: ✅ verified by execution · ⚠️ technical finding/deviation · ❌ not done / failed · ❓ unresolved.

---

## 1. M1.1 — Environment inspection (✅ complete)

Inspected 30 October 2026 ~14:45 IST. Nothing was deleted, overwritten or migrated during inspection.

### 1.1 Drives

| Drive | Used | Free | Role (per brief) |
|---|---|---|---|
| C: | 165 GB | **10.9 GB** → 11.4 GB after Docker start | System only |
| D: | 8.8 GB | 141.2 GB | Applications/software |
| E: | 26.3 GB | 123.6 GB | Data/workloads (project, Docker, models, venv) |

Note: M0 audit recorded only 3.4 GB free on C:; Windows temp data has since been reclaimed — **11.4 GB free now**, but still tight for a ~2–4 GB Db2 image + growth.

### 1.2 Toolchain (unchanged from M0 `ENVIRONMENT_AUDIT.md`)

| Tool | Version | Evidence |
|---|---|---|
| Docker CLI | 29.8.1 (build 4a63305) | `docker --version` |
| Docker Desktop | 4.93.0 at `%LOCALAPPDATA%\Programs\DockerDesktop` (user path redacted) | directory listing |
| Docker engine (server) | 29.8.1, os=linux | `docker version --format 'server={{.Server.Version}}'` after daemon start |
| WSL2 distros | `Ubuntu` (v2, stopped), `docker-desktop` (v2) | `wsl --list --verbose` |
| Python | 3.14.2 (`C:\Program Files\Python314\python.exe`), pip 26.2.1 | `python --version` |
| Git | 2.52.0.windows.1 | `git --version` |
| Ollama | **not installed** | `Get-Command ollama` → missing |

### 1.3 Docker state at inspection

- Daemon initially **off** (`npipe` connect error) — started manually; server up in ~11–21 s on later restarts.
- Data disk: `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx` ≈ **3.07 GB** (on C:; local user path redacted).
- Docker settings file: `%APPDATA%\Docker\settings-store.json` (SettingsVersion 46).

### 1.4 Pre-existing Docker data (other projects — preserved)

| Type | Items |
|---|---|
| Images (5) | Two app images from another local project (74 MB + 200 MB), `postgres:17-alpine` (424 MB), `postgres:16-alpine` (420 MB), `nginx:1.27-alpine` (74 MB) |
| Containers (6) | 4 from another local project's stack + 2 stopped Postgres containers (names redacted — unrelated projects) |
| Volumes (3) | 2 anonymous volume IDs + 1 named Postgres data volume (~187 MB total Postgres data; IDs/names redacted) |
| Build cache | 45 entries, 345 MB (123.8 MB reclaimable) |

### 1.5 Git state

- Branch `main`, **zero commits, no remote configured** — 8 M0 markdown files untracked.
- ⚠️ Consequence: the brief's final "push to the existing GitHub repository" step **cannot be executed** until the operator supplies the existing repository URL (creating a new repo is forbidden by the brief).

### 1.6 RAM

- Host: ~5.5 GB free at inspection time (16 GB total).
- Docker VM: MemTotal ≈ 7.9 GB.
- ⚠️ Db2 CE needs ≥4 GB free RAM during setup — co-residency with Ollama must be sequenced, not parallel.

---

## 2. M1.2 — Docker configuration (⚠️ attempted, migration CANCELLED — deviation)

### 2.1 Approvals obtained (operator, 30 Oct 2026)

1. ✅ "Approve backup + migrate" — back up 3 volumes to E:, then relocate Docker data disk to E:.
2. ✅ "Stop them during M1" — stop other projects' containers during M1; nothing removed.
3. ⏸️ After several failed migration attempts, operator chose **"cancel all docker activities as now and close the docker"** and later **"Pause M1 entirely"**.

### 2.2 Work completed

1. ✅ All 6 existing containers stopped (`docker stop` on each — other projects' container names redacted). Left installed and restartable; **nothing removed**.
2. ✅ **Volume backups created** (safety net, tar.gz via `postgres:17-alpine`):
   - `E:\DockerBackups\` — 3 archives (filenames derive from volume IDs; redacted), 7.0 MB + 10.34 MB + 6.45 MB
3. ❌ **Data-disk relocation to E: did not complete.** Three approaches tried; all failed to trigger the move (data verified intact after every attempt):

| # | Approach | Result |
|---|---|---|
| 1 | Legacy `DataFolder: "E:\Docker"` in `settings-store.json`, cold start | Key ignored by Docker Desktop 4.93; vhdx stayed on C: |
| 2 | Correct key `vm.resources.wslDataFolder: "E:\Docker"` (disverified by extracting Docker Desktop's own UI schema from `app.asar` — the "Disk image location" directorypicker uses exactly this key), cold start | Backend only performs the move through its own settings-apply pipeline; cold-start config edits are ignored. vhdx stayed on C: |
| 3 | Operator clicked "Apply & restart" in Settings → Resources while the value was pre-set in the file | UI saw no delta through its own picker → no move executed |

4. ✅ **Docker fully closed per operator request** (30 Oct ~15:40 IST): all Docker processes stopped, `wsl --shutdown` executed, both WSL distros Stopped, settings-store.json reverted to defaults (no leftover custom keys).

### 2.3 Final state at pause (verified)

- `docker_data.vhdx` (3.07 GB) remains at `%LOCALAPPDATA%\Docker\wsl\disk\` (user path redacted) — **all 5 images, 3 volumes, 6 containers intact**.
- Volume backups intact on `E:\DockerBackups\` (3 files, 23.8 MB).
- C: free: 11.4 GB · E: free: 123.6 GB.
- Docker daemon: stopped. No Docker processes running.

### 2.4 ⚠️ Documented deviation from M1 requirements

- **M1 requirement:** "Verify Docker workload storage is stored on E:" — **NOT met.** Docker workload data remains on C:.
- **Reason:** Docker Desktop 4.93's migration executes only via its UI picker pipeline; the config-file route is ignored by design, and the operator chose to pause rather than continue clicking through the UI flow (a fully manual `vhdx` move via `wsl --shutdown` + file relocation was offered but not taken).
- **Risk:** C: has 11.4 GB free. Pulling `icr.io/db2_community/db2` (~2–4 GB) plus Db2 data growth will consume a large share of it. Must be re-checked before M1.4.
- **Recovery path (for next session, requires operator approval):** start Docker Desktop → Settings → Resources → pick `E:\Docker` in the "Disk image location" picker → Apply & restart → confirm move dialog. Backups already exist; nothing else needed.

---

## 3. M1.3 — Ollama installation (❌ NOT started)

Not executed — M1 paused after M1.2. Planned (unchanged from brief):
- Official `OllamaSetup.exe`, install to D: (`/VERYSILENT /DIR="D:\Ollama"`), document unavoidable C: usage.
- `OLLAMA_MODELS=E:\future\ollama-models` (user env var) — verify model dir on E: **before** any download.
- Pull exactly `granite4.2:3b` and `nomic-embed-text:v1.5`; verify via `ollama list`, a chat completion, and an embedding test. No substitutions.

## 4. M1.4 — IBM Db2 Community Edition (❌ NOT started)

Blocked on Docker being restarted (operator approval required first). Planned (unchanged):
- Official image `icr.io/db2_community/db2`, verify tag ≥ 12.1.2 (VECTOR requirement) and record `db2level`.
- Port bound to 127.0.0.1 only; passwords generated programmatically into gitignored env files (never echoed, never in source/logs/reports/commits); persistent `/database` volume; healthcheck + `--restart unless-stopped`.
- Dev database + separate read-only account; verify SELECT works / INSERT denied / VECTOR type available.
- **Re-check C: free space before pulling** (see §2.4) or complete the E: migration first.

## 5. M1.5 — Python environment (❌ NOT started)

Not executed — M1 paused. Planned (unchanged):
- `python -m venv E:\future\Db2Hack\.venv`
- Pinned: `ibm_db==3.3.0`, `langchain==1.3.14`, `langchain-community==0.4.2`, `langchain-ollama==1.1.0`, `langchain-db2==1.0.0`, `sqlglot`, `db2-sqlglot-dialect==1.1.0` (nine-package allowance from `REQUIREMENTS_MATRIX.md`; exact pins to be confirmed against PyPI at install time).
- `PIP_CACHE_DIR=E:\future\pip-cache`; verify imports + Db2 connectivity.

## 6. M1.6 — Db2 vector-store PoC (❌ NOT started)

Blocked on M1.4 (Db2) + M1.3 (Ollama embeddings) + M1.5 (venv). Planned directory: `E:\future\Db2Hack\m1-poc\`. Requirements unchanged: real DB2VS round trip — ≥3 docs, `similarity_search_with_score`, metadata verification, persistence after reconnect. No FAISS/Chroma/in-memory substitutes.

---

## 7. M1 completion checklist (at pause)

- [x] D:/E: storage allocation documented (§1.1, §2)
- [ ] Docker daemon running (closed at pause per operator request)
- [ ] **Docker workload storage verified on E:** (❌ deviation — see §2.4)
- [ ] Ollama installed, model storage on E: (not started)
- [ ] Both models downloaded and tested (not started)
- [ ] Db2 CE running with persistent E: storage (not started)
- [ ] Database connectivity verified (not started)
- [ ] Read-only permissions verified (not started)
- [ ] Python venv + dependencies work (not started)
- [ ] LangChain Db2 vector-store round trip succeeds (not started)
- [x] No credentials committed (no credentials created yet; `.env.example` placeholders added, `.env` not created)
- [x] Documentation updated (`M1_ENVIRONMENT_REPORT.md`, `HANDOFF.md`)

## 8. Security notes (M1 pause)

- No passwords, keys or credentials were created, printed, logged or committed during M1.1/M1.2.
- No files were deleted. Docker/WSL data directories were never manually deleted (per brief); only a routine `wsl --shutdown` was performed at operator request.
- Other projects' containers/images/volumes were preserved (stopped only) plus tar-gzipped to `E:\DockerBackups\`.
- Git: nothing committed yet (zero-commit repo, no remote) — see §1.5.

## 9. Exact next steps when M1 resumes (operator approval required)

1. Decide the Docker storage question first: retry the UI picker migration (Settings → Resources → pick `E:\Docker` → Apply & restart — 2 clicks), or accept C: and re-check space before the Db2 pull.
2. M1.3: Ollama to D:, models to `E:\future\ollama-models`, pull + test both models.
3. M1.4: Db2 CE ≥12.1.2, local-only port, env-file credentials, read-only account, VECTOR verification.
4. M1.5: `.venv` on E:, pinned deps, import + connectivity checks.
5. M1.6: `m1-poc/` DB2VS round trip with real output captured.
6. Wrap-up: `.gitignore`, `.env.example` final review, HANDOFF update, **operator supplies existing GitHub repo URL** (required — none configured), commit + push.
