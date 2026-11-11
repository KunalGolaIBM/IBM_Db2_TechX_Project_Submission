# M0 RESEARCH REPORT — IBM Db2 TechX Summit 2026 (Db2Hack)

**Milestone:** M0 — Research & Feasibility Audit (research/inspect/document only)
**Date:** 30 October 2026 (IST) — summit event day
**Workspace:** `E:\future\Db2Hack`
**Status:** ✅ M0 complete. ❗No application code has been written, no dependencies installed, no database provisioned, nothing submitted.

Verification legend: ✅ officially verified (source read on 2026-10-30) · ⚠️ technical finding · 💡 recommendation · ❓ unresolved.

---

## 1. Executive Summary

We are building — pending M1 approval — **"Db2 Ops Copilot"**: a hybrid RAG + guardrailed text-to-SQL assistant where **IBM Db2 plays two essential roles**: the vector store for documentation RAG (via `langchain-db2`'s `DB2VS`) *and* the live query target for schema-aware, sqlglot-validated, read-only natural-language SQL. The stack is Python 3.14 + LangChain + `ibm_db` + Ollama (`granite4.2:3b` + `nomic-embed-text:v1.5`) + Db2 Community Edition on Docker. This design maximizes the heaviest-weighted judging criterion (genuine Db2 depth), is structurally differentiated from generic chatbots, and is reproducible with zero API keys.

All official sources were successfully inspected: the summit website (a client-side React SPA — content extracted from its production JS bundle), the full submission repository (README, CONTRIBUTING, PR template, judging criteria, submission guide, Db2 setup guide, FAQ, submissions rules, validator script, CI workflow) and the IBM Db2 AI Cookbook (archived 3 Oct 2026 but fully readable). Two material discrepancies were discovered and flagged rather than smoothed over: **(a)** the website publishes a **6-criterion rubric with Security at 15%**, while the repo documents a **5-criterion rubric without Security**; **(b)** the repo states a **29 Oct 7 PM "hard deadline"**, while the live website states "**there is no deadline today**… not strict… closing time will be announced". Local environment is capable but has three concrete risks: nearly-full C: drive (3.4 GB), Docker daemon not running, and ~4.5 GB free RAM.

## 2. Competition Requirements (verified)

Full matrix in `REQUIREMENTS_MATRIX.md`. Key facts:

- **Open to everyone, solo or team** — individual entry explicitly allowed (✅ website FAQ).
- **Mandatory:** meaningful IBM Db2 integration in code; **at least one of LangChain / Haystack / CrewAI / LlamaIndex / Langflow**; four files (`README.md`, `architecture.md`, `submission.json`, `.env.example`); GitHub PR **and** Google Form entry (PR alone insufficient); LinkedIn post; joining the mandatory WhatsApp community (where the Form link and closing-time announcements land).
- **AI/LLM optional but encouraged** — approved providers: watsonx.ai, OpenAI, Gemini, OpenRouter, Ollama. Any language allowed.
- **Submission mechanics:** fork → `submission/<slug>` branch from `upstream/main` → copy `submissions/_template/` → validate with `python scripts/validate_submission.py submissions/<slug>` → Conventional Commit `feat(<slug>): …` → PR titled `[Submission] <slug>: <Title>` → scope isolation enforced by CI (Python 3.11 GitHub Action).
- **Disqualification triggers:** cosmetic Db2 usage, committed secrets, plagiarism, tampering with repo root/CI/others' folders.
- **Dates:** kick-off 28 Oct 19:00 IST; finale 30 Oct with Top-10 pitches 16:00–16:30 IST at GL Bajaj, Mathura. ⚠️ Repo "hard deadline" 29 Oct 19:00 IST is contradicted by the live website ("no deadline today… not strict… closing time to be announced"). ❓ Exact closing time unknown.

## 3. The Nine Official Db2 Packages (verified from the website's Toolkit section)

| # | Package | Install | Capability | Local Python 3.14 |
|---|---|---|---|---|
| 1 | **LangChain** `langchain-db2` | `pip install -U langchain-db2` | Db2 vector store (`DB2VS`) for RAG/retrieval | ✅ (>=3.10,<4.0) |
| 2 | **Langflow** `lfx-ibm` | `pip install lfx-ibm` | No-code IBM bundle w/ Db2 vector store component | ✅ (>=3.10,<3.16) |
| 3 | **Haystack** `ibm-db-haystack` | `pip install ibm-db-haystack` | Db2 document store for pipelines | ✅ (>=3.11) |
| 4 | **CrewAI** `crewai-tools`+`ibm_db` | `pip install crewai-tools ibm_db` | Db2 vector search tool for agents | ❌ `<3.14` cap |
| 5 | **LlamaIndex** `llama-index-vector-stores-db2` | `pip install llama-index-vector-stores-db2` | Db2 vector store | ❌ `<3.13` cap |
| 6 | **dbt** `ibm-dbt-db2` | `pip install ibm-dbt-db2` | Db2 adapter for data transformation | ❌ `<3.13` cap |
| 7 | **SQLGlot** `db2-sqlglot-dialect` | `pip install db2-sqlglot-dialect` | Db2 SQL dialect (IBM plugin) | ✅ (>=3.10) |
| 8 | **Python driver** `ibm_db` | `pip install ibm_db` | Core Python driver | ✅ v3.3.0 cp314 win wheel |
| 9 | **VS Code** IBM Db2 Developer Extension | `code --install-extension IBM.db2-for-luw` | Dev extension; can *provision* a Db2 CE instance via Docker | ✅ installed v1.2.1 (a tool, not a server) |

All nine names/commands/URLs are verbatim from the official site (✅). Compatibility column verified on PyPI (⚠️). We will use packages **1 + 7 + 8** (all Python-3.14-clean).

## 4. Local Environment Audit (details in `ENVIRONMENT_AUDIT.md`)

- ✅ Working: Git 2.52, **Python 3.14.2**, Node 24.14, npm 11.9, VS Code 1.143 (+ IBM Db2 extension 1.2.1), Java 25, Docker CLI 29.8, WSL2 Ubuntu, OpenCode. LangChain 1.3.14 & friends already pip-installed.
- ⚠️ Installed but not running: **Docker Desktop 4.93** (daemon off — must be started in M1).
- ❌ Missing: **Ollama** (no binary; models `granite4.2:3b` and `nomic-embed-text:v1.5` therefore not installed — both tags verified to exist on ollama.com), `ibm_db`, `langchain-db2`, **any Db2 server**.
- 🔴 **C: drive: 3.4 GB free** — Docker images, Ollama models and HF cache must be relocated to **E:** (123.7 GB free). RAM 16 GB total, ~4.5 GB free — Db2 + Ollama + app co-residency must be tested.
- Nothing was installed or modified during the audit.

## 5. Framework Comparison & Decision (details in `TECH_STACK_DECISION.md`)

Decision: **LangChain primary**. Decisive evidence, in order: (1) the organizers' own official worked example on the `/submit` page *is* LangChain + `DB2VS`; (2) it's the only mandated framework fully compatible with the local Python 3.14 *and* whose driver has a cp314 Windows wheel; (3) Ollama glue (`langchain-ollama`) already installed; (4) best documentation density (LangChain docs page + IBM announcement + site example); (5) Haystack kept as zero-friction fallback; CrewAI/LlamaIndex blocked by Python caps (would need a 3.12 venv); Langflow rejected (visual builder is invisible in a code-reviewed submission and heavier to reproduce). Models: `granite4.2:3b` (2.2 GB, 128K ctx, Apache-2.0, IBM — perfect summit optics and the only size that fits RAM) + `nomic-embed-text:v1.5` (274 MB, 2K ctx — mind chunk sizes). ⚠️ Speed unmeasured until M1.

## 6. Five+ Project Concepts & Ranking (details in `PROJECT_CONCEPTS.md`)

| Rank | Concept | Weighted /100 |
|---:|---|---:|
| 1 | **Db2 Ops Copilot — hybrid RAG + guardrailed text-to-SQL over Db2** | **89** |
| 2 | AskMyData — guardrailed text-to-SQL analytics copilot | 76 |
| 3 | Ticket Twin — support-ticket dedup & triage intelligence | 73 |
| 4 | CampusDocs Q&A — RAG over institutional documents | 68 |
| 5 | SkillMatch — course/resource recommender with live filters | 65 |
| 6 | PolicyGuard — agentic compliance checker (rejected: corpus/hallucination risk) | 64 |

## 7. Final Recommendation

**Concept 5 — "Db2 Ops Copilot"** (slug candidate `db2-ops-copilot`). Db2 is essential twice over (vector store + query engine), the demo visibly proves real integration (live SQL, EXPLAIN, SYSCAT, audit table), it uses three of the nine official packages (`langchain-db2`, `db2-sqlglot-dialect`, `ibm_db`), runs 100% local on IBM's own Granite model (strong story on an IBM stage), and has a staged build path where a demoable core exists early.

## 8. Architecture Proposal (full detail + Mermaid in `PROPOSED_ARCHITECTURE.md`)

FastAPI app + minimal web UI; LangChain router classifies intent → **RAG path** (nomic embeddings → `DB2VS.similarity_search` with metadata filters → Granite grounded answer with citations) and **Text-to-SQL path** (SYSCAT introspection → Granite generates Db2-dialect SQL → official `db2-sqlglot-dialect` parse-gate → EXPLAIN dry-run → execute under a least-privilege read-only Db2 user with row caps → Granite summarizes). Every request audited into a Db2 `APP_AUDIT` table. Schema: `KB_CHUNKS` (VECTOR 768), synthetic demo tables, audit table. Security per rubric: zero secrets, parameterized SQL, statement allow-list, prompt-injection defenses, license attribution (cookbook is Apache-2.0).

## 9. Submission Workflow (details in `SUBMISSION_GUIDE.md`)

Fork → branch `submission/<slug>` → copy `_template` → build → `python scripts/validate_submission.py` passes → conventional commit → PR `[Submission] <slug>: <Title>` → **Google Form with PR URL** (link via WhatsApp — repo still shows placeholder) → **LinkedIn post tagging organisers**. CI validates structure/metadata/secrets automatically; scope isolation strictly enforced. Nothing submitted yet.

## 10. Risks & Unresolved Questions

| # | Risk / Question | Impact | Mitigation / Next action |
|---|---|---|---|
| 1 | C: drive 3.4 GB free | Docker pull / model downloads fail | Relocate Docker data root + `OLLAMA_MODELS` + HF cache to E: before provisioning |
| 2 | Docker daemon not running | No Db2 possible | Start Docker Desktop as first M1 action |
| 3 | ~4.5 GB free RAM with Db2+Ollama+app | OOM / thrash | Stop heavy apps; modest Db2 memory config; measure; fallback to sentence-transformers embeddings or watsonx |
| 4 | Db2 CE image version vs `VECTOR` type (needs 12.1.2+) | DB2VS may fail | Verify `db2level` at provisioning; fallback: pin a specific image tag; Haystack fallback unlikely to help (same engine) |
| 5 | Rubric conflict (6-dim website vs 5-dim repo) | Scoring ambiguity | Design to the union; ask organisers (WhatsApp / Submission Help issue) |
| 6 | Deadline conflict + unannounced closing time | Missing the window | Treat website as current; submit as early as sound; watch WhatsApp |
| 7 | Google Form link is a repo placeholder | Can't complete submission without it | Retrieve from mandatory WhatsApp community / email |
| 8 | granite4.2:3b latency on this CPU | Demo sluggishness | Measure in M1; cap k/limit; stream UI; pre-warm model |
| 9 | `nomic-embed-text` 2K context | Truncation | Chunk 300–800 tokens |
| 10 | Solo timeline | Scope creep | Staged build: RAG core first, SQL half second, polish third |

## 11. Exact M1 Plan (await approval — do not auto-start)

1. Start Docker Desktop; relocate Docker data root, `OLLAMA_MODELS`, HF cache to **E:**; free C: if possible.
2. Provision Db2 Community Edition (`icr.io/db2_community/db2` via VS Code extension *or* `docker run` — test both, pick one); record `db2level`, confirm `VECTOR`/`VECTOR_DISTANCE` support; create `testdb` + read-only user.
3. Install Ollama; pull `granite4.2:3b` + `nomic-embed-text:v1.5` (models on E:); smoke-test chat + embeddings; measure latency.
4. `pip install` pinned set: `ibm_db`, `langchain-db2`, `langchain-ollama`, `fastapi`, `uvicorn`, (+ test deps); verify DB2VS `from_documents` + `similarity_search` end-to-end (mirroring the official worked example).
5. Scaffold app skeleton (router, RAG path), seed schema + KB ingest, then text-to-SQL path with sqlglot gate; audit table; tests.
6. Parallel: fork submission repo, create branch, copy template, draft README/architecture/submission.json; join WhatsApp; get Form link; confirm rubric + closing time.
7. Record demo video, screenshots; final validator run; open PR; submit Form; publish LinkedIn post.

**Gate:** explicit human approval required to begin M1.
