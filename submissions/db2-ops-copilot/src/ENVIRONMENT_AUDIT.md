# ENVIRONMENT AUDIT — Local Windows Development Environment

**Audit date:** 30 October 2026 (IST)
**Machine:** Windows 11 (win32) — local username redacted
**Auditor:** M0 Research phase (read-only inspection — no software installed, no config changed)

Verification legend used across all M0 documents:
- ✅ **Verified** — measured/inspected directly on this machine or read from an official source on 2026-10-30.
- ⚠️ **Technical finding** — verified fact plus derived engineering judgement.
- ❓ **Unresolved** — could not be verified; needs action or organizer confirmation.

---

## 1. Core Toolchain

| Tool | Status | Version | Evidence |
|---|---|---|---|
| Git | ✅ Installed & working | 2.52.0.windows.1 | `git --version` |
| Python | ✅ Installed & working | 3.14.2 (`C:\Program Files\Python314\python.exe`) | `python --version` |
| Node.js | ✅ Installed & working | v24.14.0 | `node --version` |
| npm | ✅ Installed & working | 11.9.0 | `npm --version` |
| VS Code | ✅ Installed & working | 1.143.1 | `code --version` |
| Java | ✅ Installed & working | 25.0.1 LTS (Java HotSpot 64-bit) | `java -version` |
| Docker CLI | ✅ Installed | 29.8.1 (build 4a63305) | `docker --version` |
| Docker Desktop | ⚠️ Installed, **daemon NOT running** | 4.93.0, `%LOCALAPPDATA%\Programs\DockerDesktop` (user path redacted) | Registry uninstall key + `docker ps` failed: "pipe/dockerDesktopLinuxEngine … The system cannot find the file specified" |
| WSL | ✅ Installed | Ubuntu (WSL2; WSL1 not supported on this hardware) | `wsl --status` |
| OpenCode | ✅ Installed & working | 1.143.1 (x64, commit e6468682…) | `code --version` / harness environment |
| Ollama | ❌ **Missing** | — | Not on PATH (`where.exe ollama` → not found), not in `%LOCALAPPDATA%\Programs\Ollama`, not in `%ProgramFiles%\Ollama`, not in WSL. A leftover `%USERPROFILE%\.ollama` directory exists containing only an empty `cache` folder — no `models/manifests`, no server binary. |

⚠️ **Docker must be started** (launch Docker Desktop) before any Db2 container or the VS Code "Create Db2 instance" flow can work. This is a prerequisite action for M1, not a missing install.

## 2. IBM Db2–Related Tooling

| Item | Status | Detail |
|---|---|---|
| IBM Db2 Developer Extension (VS Code) | ✅ Installed | `ibm.db2-for-luw-1.2.1` (also `ibm.db2forzosdeveloperextension-2.2.7`, `ibm.ims-explorer-for-vscode-1.2.1`, z/OS middleware pack — Z stuff is irrelevant here) |
| Db2 database server / instance | ❌ **Not present** | No Db2 instance exists. Per organizer guidance the VS Code extension can *create* a Db2 Community Edition instance (requires Docker — see above). We must not assume a server is available. |
| Python `ibm_db` driver | ❌ Not installed | `pip show ibm_db` → not found |
| Python `ibm_db_sa` / `ibm_db_dbi` | ❌ Not installed | Not in `pip list` |
| Node `ibm_db` driver | ❌ Not installed | Not verified in any global npm list (would be installed per-project) |

## 3. Python Ecosystem (global `pip list`, relevant subset)

✅ Installed: `langchain 1.3.14`, `langchain-classic 1.0.8`, `langchain-community 0.4.2`, `langchain-core 1.5.3`, `langchain-ollama 1.1.0`, `langchain-openai 1.4.1`, `langchain-text-splitters 1.1.2`, `ollama 0.6.2` (client lib only — no server), `SQLAlchemy 2.0.51`.

❌ Not installed: `ibm_db`, `langchain-db2`, `llama-index-*`, `haystack`, `crewai`, `langflow`, `sentence-transformers`.

⚠️ **Critical version constraint — Python 3.14.2 is very new.** Verified against PyPI metadata on 2026-10-30:

| Package (latest) | `requires_python` | Works on local 3.14? |
|---|---|---|
| `ibm_db 3.3.0` | (sdist metadata empty, but) ships **cp314 win_amd64 wheel** (uploaded 2026-08-11) | ✅ Yes |
| `langchain-db2 1.0.0` | `>=3.10,<4.0` | ✅ Yes |
| `ibm-db-haystack 1.0.0` | `>=3.11` (no cap) | ✅ Yes |
| `lfx-ibm 0.3.1` (Langflow IBM bundle) | `>=3.10,<3.16` | ✅ Yes |
| `db2-sqlglot-dialect 1.1.0` | `>=3.10` | ✅ Yes |
| `crewai-tools 1.15.33` | `>=3.10,<3.14` | ❌ **No — capped below 3.14** |
| `llama-index-vector-stores-db2 0.1.0` | `>=3.9,<3.13` | ❌ **No — capped below 3.13** |
| `ibm-dbt-db2 1.0.0` | `>=3.10,<3.13` | ❌ **No — capped below 3.13** |

⚠️ CrewAI and LlamaIndex Db2 connectors would require a separate Python 3.12 (or 3.11) virtual environment (e.g., via `uv python install 3.12`). LangChain and Haystack need no interpreter change. See `TECH_STACK_DECISION.md`.

## 4. Hardware & Storage Constraints

| Resource | Value | Assessment |
|---|---|---|
| CPU | AMD Ryzen 7 7445HS, 6 cores / 12 threads | ✅ More than adequate |
| RAM | 16 GB total (15,973,788 KB); **~4.5 GB free at audit time** | ⚠️ Tight. Db2 Community Edition is licensed up to 16 GB RAM / 4 cores; organizers state ≥4 GB free RAM needed for the VS Code instance flow. Running Db2 container + Ollama (granite4.2:3b ≈ 2.2 GB weights + KV cache) + app + browser simultaneously on ~4.5 GB free is a **real risk**. Mitigation: stop background apps; configure Db2 container memory modestly; consider embedding via HuggingFace/sentence-transformers instead of a second Ollama model; test and document memory behaviour in M1. |
| C: drive free | **3.4 GB** (172.5 GB used) | 🔴 **Critical constraint.** The `icr.io/db2_community/db2` image plus its data volume needs many GB; Docker Desktop's data root lives on C: by default. Also Ollama models and pip/HuggingFace caches default to C:. **Must relocate Docker data root and/or OLLAMA_MODELS to E:** (or free up C: space) before M1 provisioning. |
| E: drive free | 123.7 GB | ✅ Plenty — use this for Docker images/volumes, Ollama models, HuggingFace cache, project files. |

## 5. Ollama Model Check (requested models)

Neither requested model is installed (Ollama itself is not installed):

| Model | Local status | Official identity (verified 2026-10-30) |
|---|---|---|
| `granite4.2:3b` | ❌ Not installed | ✅ Valid tag on https://ollama.com/library/granite4.2 — 2.2 GB, 128K context, text-only, Apache-2.0, IBM Granite, supports RAG/tool-use/JSON/thinking mode |
| `nomic-embed-text:v1.5` | ❌ Not installed | ✅ Valid tag on https://ollama.com/library/nomic-embed-text — 274 MB, **2K context window**, embedding-only model |

⚠️ `nomic-embed-text:v1.5` is currently `latest`. Downloading both ≈ 2.5 GB — feasible on E: but not on the remaining 3.4 GB of C:.

## 6. Status Summary

- **Installed and working:** Git, Python 3.14.2, Node 24, npm 11, VS Code (+ IBM Db2 extension 1.2.1), Java 25, Docker CLI, WSL2 Ubuntu, OpenCode.
- **Installed but not configured/running:** Docker Desktop 4.93.0 (daemon off), WSL Ubuntu (no Ollama inside).
- **Missing:** Ollama server, both Ollama models, `ibm_db` (and all Db2 Python drivers), any Db2 server/instance, `langchain-db2`.
- **Not verified (deferred to M1 with real server):** Actual Db2 connectivity, DB2VS vector operations, VECTOR column support of the provisioned image version, end-to-end Ollama inference speed on this CPU.
- **Nothing was installed or modified during this audit.**

**Top-3 environment risks for M1:** (1) C: drive nearly full — relocate Docker/Ollama/HF storage to E: first; (2) Docker daemon not running; (3) ~4.5 GB free RAM when stacking Db2 + Ollama + app.
