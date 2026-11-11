# HANDOFF — Db2Hack Project (M3 in progress — real integration still unverified)

**Current milestone:** **M3 — approval workflow & agent groundwork (in progress)** on branch `feature/m2-core-integrations`.

**Current verified status (read this first):**

- **Offline test suite: 389 passed, 1 skipped.** The skip is the single opt-in integration test (`test_db2_dialect_integration.py`) — it is *not* a passing integration; on this machine it fails when enabled (Application Control blocks the `ibm_db` DLL).
- **Implemented and offline-tested:** mock-mode app end to end (chat, `sql/validate|execute|explain`, DBA tools, health/status/config/audit), the SQL safety gate, SQL execution service (row cap → EXPLAIN dry-run → read-only execution → audit), the M3 approval workflow (`app/agent/*`, `approval_service.py`) with dedicated safety tests (P0.1/P0.2) and fail-closed decision validation (P0.3), and read-only vs admin credential separation (P0.2 tests).
- **Implemented but UNVERIFIED (no live service ever available on this machine):** genuine Db2 / Ollama / `DB2VS` adapters, LangChain orchestration (partial — retrieval legs only; the orchestrator does not execute SQL), and all `database/migrations/` scripts (**authored, never executed**).
- **Implemented since the initial M3 handoff:** approval HTTP API, bounded
  deterministic action-proposal workflow, Approvals UI, and mock-only knowledge
  ingestion. These additions are offline-tested; see the API contract.
- **Still not built:** autonomous LangChain/LangGraph agent execution. Proposal
  creation accepts explicit allow-listed actions rather than deriving them
  from an LLM or diagnostic run.
- **No infrastructure installed** (Docker/Ollama/Db2 untouched — constraint honored). **Nothing submitted yet.**

---

**M1 record (historical):** completed 31 October 2026 IST; branch `m1-portable-foundation` merged to `main`. Backend + frontend run fully offline; production frontend build passes; the M1 suite was 100 offline tests.
**M1 implementation:** ✅ FastAPI backend, adapter layer (mock + genuine real implementations), SQL security gate, React/TS frontend, Db2 SQL migrations (authored, not executed), full documentation set.

---

## Completed research tasks (M0) — preserved

1. ✅ Inspected all mandatory official sources in full:
   - Summit website `https://ibmdb2techxsummit.glbajajgroup.ac.in/` (+ `/resources`, `/submit`) — a React SPA; content extracted from its production JS bundle (`/assets/index-D1oV8j9W.js`).
   - Official submission repo `https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission` — README, CONTRIBUTING, PR template, `docs/submission-guide.md`, `docs/judging-criteria.md`, `docs/db2-setup-guide.md`, `docs/faq.md`, `submissions/README.md`, `submissions/_template/submission.json`, `scripts/validate_submission.py`, CI workflow.
   - IBM Db2 AI Cookbook `https://github.com/IBM/db2-ai-cookbook` — archived 3 Oct 2026, read-only, fully readable (8 modules).
2. ✅ Extracted and verified the **nine official Db2 toolkit packages** — see `REQUIREMENTS_MATRIX.md` §3.
3. ✅ Verified all mandated AI frameworks and their local Python compatibility on PyPI (LangChain/Haystack/Langflow OK on 3.14; CrewAI/LlamaIndex/dbt blocked by version caps).
4. ✅ Audited the local Windows environment (`ENVIRONMENT_AUDIT.md`) — nothing modified.
5. ✅ Verified both Ollama model identifiers (`granite4.2:3b`, `nomic-embed-text:v1.5`) against ollama.com.
6. ✅ Confirmed `ibm_db 3.3.0` ships a cp314 Windows wheel → Python 3.14.2 is viable.
7. ✅ Developed and rubric-ranked **six** project concepts; recommended one (`PROJECT_CONCEPTS.md`).
8. ✅ Produced full architecture proposal (`PROPOSED_ARCHITECTURE.md`).
9. ✅ Documented the GitHub submission workflow (`SUBMISSION_GUIDE.md`).

## Completed foundation tasks (M1) — this milestone

- 📄 **`M1_REPO_AUDIT.md`** — baseline audit of `5ff5f6a` (10 findings, all resolved; preserved work listed).
- 🔧 **Backend** — app factory, lifespan, request-id middleware, CORS, unified error envelope, DI, 6 endpoints (`health`, `status`, `config`, `chat`, `sql/validate`, `audit`), structured logging. Starts with **zero services**.
- 🔌 **Adapters** — Protocol contracts (`adapters/base.py`); 6 mock adapters (offline, deterministic) + 6 genuine real adapters (`ibm_db`, Ollama REST, LangChain composition, DB2VS stub with actionable M2 errors). Mock/real selected by `ADAPTER_MODE`; real mode never instantiates mocks (test-enforced).
- 🛡 **SQL security** — fail-closed sqlglot gate on the official `db2` dialect: SELECT-only, single statement, forbidden nodes, catalog deny-list, complexity caps, row-limit advisory + independent enforcement documented (read-only grants, timeout, parameterized app queries). Prompt-injection screening (`block` default) with contract-fixed `off`/`flag` modes.
- 🗄 **Database scripts** — `database/migrations/001_app_schema.sql` (APP schema, demo tables, `APP_AUDIT`, `KB_CHUNKS VECTOR(768)`), `002_indexes.sql`, `003_readonly_user.sql` (least-privilege grants) + `database/README.md`. **Authored only — never executed.**
- 🖥 **Frontend** — React 19 + TS (strict) + Vite SPA: sidebar shell, Dashboard (health probes + service cards), Chat workspace (mode routing, citations, SQL block, blocked-message states, loading/error/empty), Configuration (effective config + audit table). `npm run build` passes (tsc strict + bundle, 87 KB gzip). Served by FastAPI from `dist/`.
- ✅ **Tests** — 100 offline tests in `backend/tests/` across 8 modules (app startup, health/status, config validation, SQL security matrix, injection, adapters/DI, chat API flows, repo hygiene). Taxonomy in `docs/TESTING.md` separates offline/mock (passing) from real-service tests (**pending M2**). *(The suite has since grown to **389 passed, 1 skipped** — see current status above.)*
- 📖 **Docs** — `README.md`, `docs/ARCHITECTURE.md` (incl. security defaults), `docs/API_CONTRACT.md`, `docs/DEVELOPMENT.md`, `docs/TESTING.md`, `docs/DEPLOYMENT.md`; `.env.example` documents every variable.
- ⚙️ **Dependencies** — `httpx` promoted to runtime requirements (real Ollama adapters import it unconditionally); integration deps remain pinned and uninstalled.

## Completed since M1 (M2/M3 code — all offline-verified only)

> Everything below is proven **offline** (mock adapters / fake `ibm_db_dbi`). None of it has run against a live Db2, Ollama or DB2VS instance.

- **SQL execution service** — validate → hard row cap → best-effort EXPLAIN dry-run → read-only execution → history + audit (`POST /api/v1/sql/execute`), plus `POST /api/v1/sql/explain` with graceful `UNAVAILABLE`/`FAILED` fallback.
- **DBA tools** — fixed catalog/monitoring templates exposed at `GET/POST /api/v1/dba/tools*` (`docs/DBA_TOOLS.md`), bound parameters + clamped row limits.
- **Adapters deepened** — Db2 schema introspection, session timeout, SQLSTATE→HTTP error mapping, `DB2VS` contract implemented in `db2_vector.py` (**never executed against live Db2**), `004`/`005` migrations authored.
- **M3 approval workflow** — `app/agent/` (state machine, intent/analysis modules, closed action allow-list) + `app/services/approval_service.py`, with **offline safety tests** covering tamper/expiry/audit/guard behavior and read-only vs admin credential separation. HTTP list/detail/decision routes and a deterministic bounded proposal API now use this service. The UI previews statements and refreshes after a decision.
- **Approval decision validation (P0.3 fix)** — `decide()` accepts only the exact strings `"approve"`/`"reject"`; anything else raises `ApprovalDecisionError` (422) before any state change, regression-tested.
- **Mock KB ingestion** — `POST /api/v1/knowledge/documents` uses the existing vector adapter in mock mode; real-mode ingestion is explicitly blocked until Db2/Ollama/DB2VS is verified.
- **Demonstration limitation:** approvals are in-memory and not durable across process restarts. Mock approval execution only records a simulation; it never runs SQL against a database. In real mode, actions stay disabled unless separately enabled and admin credentials are configured; live execution remains unverified.

## Verified technical decisions (unchanged from M0)

- **Project:** "Db2 Ops Copilot" — hybrid **RAG + guardrailed text-to-SQL** where Db2 is both the vector store (`DB2VS`) and the live query target.
- **Framework:** LangChain (mandatory-listed). Haystack = fallback. **Driver:** `ibm_db` + `db2-sqlglot-dialect`.
- **Models (local Ollama):** `granite4.2:3b` + `nomic-embed-text:v1.5` (768-dim).
- **Database:** IBM Db2 Community Edition via Docker (`icr.io/db2_community/db2`), ≥ 12.1.2 for VECTOR.
- **App:** Python + FastAPI + React/TS SPA; zero API keys needed for demo.

## Unresolved questions (carry into M1-era research → M2/submission)

1. ❓ **Rubric conflict:** website = 6 criteria vs repo = 5 criteria. Design to the union; confirm with organisers.
2. ❓ Deadline/closing time — confirm in the WhatsApp community.
3. ❓ Google Form link — obtain from organisers.
4. ❓ Db2 CE image version vs `VECTOR` support — verify `db2level` after provisioning.
5. ❓ Measured inference latency of granite4.2:3b + nomic-embed-text on target CPU — unmeasured.
6. ❓ Whether DB2VS creates/uses vector indexes on CE — verify in M2 PoC.

## Local environment status (summary — details in `ENVIRONMENT_AUDIT.md` / `M1_ENVIRONMENT_REPORT.md`)

- ✅ Working: Git, Python 3.14.2 (`.venv` with fastapi/pydantic/sqlglot/db2-dialect/pytest/httpx), Node 24 + npm 11, VS Code. Frontend deps installed (`frontend/node_modules`).
- ❌ Intentionally absent (M2): Docker running, Ollama, Db2 instance, integration Python packages.
- ⚠️ No `.env` file needed yet (mock mode uses defaults).

## Important official URLs

- Summit site: https://ibmdb2techxsummit.glbajajgroup.ac.in/ · /resources · /submit
- Submission repo: https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission
- Db2 AI Cookbook: https://github.com/IBM/db2-ai-cookbook (archived, readable)
- langchain-db2: https://pypi.org/project/langchain-db2/ · docs: https://docs.langchain.com/oss/python/integrations/vectorstores/db2
- ibm_db: https://pypi.org/project/ibm_db/ · SQLGlot plugin: https://github.com/IBM/db2-sqlglot-plugin
- VS Code Db2 extension docs: https://ibm.github.io/db2developerextension-about/
- Db2 CE: https://www.ibm.com/db2/get-started · Docker image `icr.io/db2_community/db2`
- Ollama models: https://ollama.com/library/granite4.2 · https://ollama.com/library/nomic-embed-text
- Organizers: Dhruv Chaturvedi (SPOC, IBM), Kunal Gola (repo maintainer, IBM)

---

## EXACT M2 TASKS (start only on explicit operator approval)

**M2 = Real integration validation. Requires infrastructure bring-up — the M1 machine constraint (no Docker/Ollama/Db2 installs) must be lifted by the operator first.**

1. **Environment & approval**
   1. Operator approves infrastructure installation and specifies where (C: space check first — see `ENVIRONMENT_AUDIT.md` §4; Docker data ideally on E:).
   2. Install/enable Docker → pull `icr.io/db2_community/db2` (verify tag ≥ 12.1.2, record `db2level` in a report). Port `127.0.0.1:50000` only.
   3. Install Ollama → pull exactly `granite4.2:3b` + `nomic-embed-text:v1.5`; model storage on a big drive; verify `ollama list`, one chat completion, one embedding.
   4. `.venv\Scripts\pip install -r requirements-integration.txt` (pinned: `ibm_db==3.3.0`, `langchain==1.3.14`, `langchain-community==0.4.2`, `langchain-ollama==1.1.0`, `langchain-db2==1.0.0`).
   5. Create `.env` from `.env.example`; generate `DB2_INSTANCE_PASSWORD` / `DB2_RO_PASSWORD` programmatically (never echoed/committed).
2. **Database bring-up** — apply `database/migrations/001 → 002 → 003` (see `database/README.md`); verify: SELECT allowed for `db2ro`, INSERT/UPDATE/DELETE denied, `VECTOR` type exists, audit INSERT+SELECT works.
3. **Validate the real vector store** — `DB2VS` is already constructed inside `app/adapters/vector/db2_vector.py` (contract implemented from package source, but **never executed against a live Db2**); verify table layout vs `KB_CHUNKS` design; confirm metadata filters.
4. **Real adapter validation** — run with `ADAPTER_MODE=real`:
   - `GET /api/v1/health` → truthful probes (all `ok` with services up; `unavailable` when one is stopped — app must still start).
   - Schema introspection via `fetch_schema()` (SYSCAT) and readonly `execute_readonly()` with row cap + timeout.
   - Ollama generation + embeddings through the real adapters (latency + token counts recorded).
   - `langchain_orchestrator`: RAG path with real `DB2VS` retrieval + citations; text-to-SQL path with **EXPLAIN dry-run**, row-limit wrapping, execution under `db2ro`, single bounded self-repair retry. *(Reality check: today the orchestrator only returns a proposal marked "not executed yet" — statement execution lives in `POST /api/v1/sql/execute`, not in the orchestrator — and real-mode chat fails closed with 503 until the integration packages are installed. Validate/decide the intended split during this task.)*
   - `db2_audit`: real `APP_AUDIT` writes/reads; verify `GET /api/v1/audit` against the table.
5. **Real integration tests (new — must be separated)**
   - One opt-in test already exists at `backend/tests/test_db2_dialect_integration.py` (native-driver dialect load; currently **failing** on this machine — Application Control blocks the `ibm_db` DLL). Add the remaining coverage marked `@pytest.mark.integration`, skipped unless `ADAPTER_MODE=real` and `RUN_REAL_INTEGRATION=1` (categories 3–5 in `docs/TESTING.md`): Db2 connectivity/permissions, Ollama inference, DB2VS round trip (≥3 docs, `similarity_search_with_score`, metadata, reconnect persistence — **no FAISS/Chroma/in-memory substitutes**).
   - Confirm offline suites still pass with services absent.
6. **Security validation against the live system** — verify grants actually block DML/DDL for `db2ro`; verify prompt-injection block on live chat; confirm zero secrets in `git ls-files`; record results in `M2_*_REPORT.md`.
7. **Deployment & submission prep** — Docker compose / containerization (optional per time), `scripts/validate_submission.py` from the official repo, submission PR branch `submission/db2-ops-copilot`, Form link, demo video.

**Resume protocol:** read `M1_COMPLETION_REPORT.md` + this file, confirm operator approval for installs, then execute M2 tasks in order with reports per step.

**⚠️ Do not auto-start M2. Do not install infrastructure without explicit operator approval. Do not download AI models on this machine until approved.**
