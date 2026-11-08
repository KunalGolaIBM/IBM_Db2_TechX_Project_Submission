# Db2 Cortex

> **One-Line Pitch:** A governed, self-auditing multi-agent analytics copilot where IBM Db2 is the agents' brain, memory and black box: ask business questions in English and get SQL answers that are validated, cached, PII-safe and provably audited.

Built for **IBM Db2Hack 2026** (AI Engineering track), solo submission.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement
- Business users wait on SQL experts for every new question, and plain LLM text-to-SQL is unsafe: it can hallucinate tables, run destructive statements, leak personal data and leave no proof of what happened.
- **Target users:** analysts, risk and compliance teams, and Db2 shops (banking, insurance, healthcare) that want AI on their data without moving it out of the database.
- Existing tooling gives answers without governance or evidence; agent state, vectors and logs usually live in separate systems.

## Solution Overview
Ask a question in plain English. Eight LangGraph agents (Memory, Retriever, Cache, SQL Writer, Guardrail, Executor, Analyst, Auditor) answer it inside Db2's guard rails and show their work in a light-theme web UI: live agent trace, generated SQL, chart, insight and an audit trail.

Key features:
- **Self-repair loop:** Db2 errors are fed back to the SQL Writer (max 3 attempts).
- **Guardrail agent:** SELECT-only, table allow-list, no comments or system objects, role-based PII policy, 200-row cap, then Db2 `PREPARE`.
- **Semantic query cache** stored as Db2 vectors (a hit skips the LLM).
- **Tamper-evident audit:** SHA-256 hash chain in Db2, verifiable in one click.

## IBM Db2 Integration
- **Db2 Edition & Environment:** Db2 Community Edition 12.1.x on Docker (`icr.io/db2_community/db2`); the VECTOR type needs 12.1.2 or later.
- **Connector / Driver Used:** `ibm_db` / `ibm_db_dbi` for SQL and `PREPARE`; `langchain-db2` (`DB2VS`) for the governance glossary vector store.
- **Database Schema / Data Models:**

| Object | Purpose | Db2 capability |
|---|---|---|
| `BANKING.CUSTOMERS/ACCOUNTS/TRANSACTIONS/LOANS/BRANCHES` | demo business data (15,000 transactions) | relational SQL, joins, aggregates |
| `CORTEX.SEMANTIC_LAYER` | schema and metric descriptions | `VECTOR(384, FLOAT32)`, `VECTOR_DISTANCE(..., COSINE)` |
| `CORTEX_GLOSSARY` | governance rules | langchain-db2 `DB2VS` |
| `CORTEX.QUERY_CACHE` | question to SQL cache | vector similarity lookup, hit counter |
| `CORTEX.SESSION_MEMORY` | follow-up context | identity column, per-session history |
| `CORTEX.AUDIT_LOG` | audit black box | hash chain (`PREV_HASH` to `HASH`) |

- **Key Queries & Operations:** top-k vector retrieval with `ORDER BY VECTOR_DISTANCE(...) FETCH FIRST n ROWS ONLY`; cache lookup with the same function; `PREPARE` for validation; transactional audit appends serialised to keep the chain linear.

## AI / LLM Architecture
- **Framework:** LangGraph state graph (conditional edges for cache hit, self-repair and policy stop) with LangChain components.
- **Model Provider & Model:** `LLM_PROVIDER=ollama|watsonx|openai|gemini`, or the default `demo` (offline planner, no key; answers 6 built-in topics). Embeddings: MiniLM-L6-v2 (384-d) via fastembed, with an automatic hashing fallback.
- **RAG / Tool Calling Workflow:** the Retriever pulls the top-6 schema/metric rows and glossary rules from Db2; they are injected into the SQL Writer prompt together with the last three turns; every draft passes the Guardrail before it can touch data.

## Tech Stack
- **Backend / Core:** Python 3.10-3.12, FastAPI, LangGraph, sqlglot
- **Database:** IBM Db2 (Community Edition 12.1.x)
- **Frontend / UI:** single-page light-theme UI (HTML/JS, Chart.js)
- **Libraries & Tools:** Docker, ibm_db, langchain-db2, fastembed, pytest

## Prerequisites
- Docker (for the local Db2 container)
- Python >= 3.10 and `pip`
- About 4 GB RAM free for Db2; first container boot takes several minutes

## Setup & Installation
Create the virtual environment **outside** the repository (the organisers' validator scans every file in the folder).

```bash
cd submissions/db2-cortex
python -m venv ~/venvs/db2-cortex
source ~/venvs/db2-cortex/bin/activate        # Windows: %USERPROFILE%\venvs\db2-cortex\Scripts\activate
pip install -r src/requirements.txt pytest
```

## Configuration
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
Set `DB2_PASSWORD` in `.env`; `docker-compose.yml` reads the same value, so there is one source of truth. Never commit `.env`.

## Running the Project
```bash
docker compose up -d
cd src
python wait_db.py           # waits until Db2 is ready
python seed.py              # BANKING data + VECTOR semantic layer + glossary
python verify.py            # 20+ end-to-end checks against your Db2
uvicorn app:app --port 8000 # open http://localhost:8000
```
If you change `EMBEDDINGS` after seeding, run `python seed.py` again.

**2-minute tour**
1. Click "Which branches have the highest loan default rate?" and watch the 8-step trace, SQL, chart and insight.
2. Ask the same question again: **semantic cache hit**, no LLM call.
3. Ask "Delete all customers": the Guardrail blocks it and the data stays intact (demo mode deliberately emits the unsafe SQL to show the guard).
4. Ask "Top 10 customers by balance" as Analyst, then Admin: personal data is denied to analysts.
5. Open the Audit trail tab and press **Verify chain**.

## Testing & Verification
```bash
pytest ../tests             # no database needed (guardrail, planner, routing, hash chain)
python verify.py            # needs a running, seeded Db2: vector search, cache, guard, PII, audit tamper test
```
`verify.py` also tampers with an audit row inside a transaction and confirms the chain breaks, then rolls back.

## Screenshots & Demo
- **Live Demo Link:** not hosted; runs locally from the steps above.
- **Demo Video Link:** PASTE_VIDEO_LINK
- ![Ask](docs/screenshots/01-ask.png)
- ![Cache hit](docs/screenshots/02-cache-hit.png)
- ![Blocked](docs/screenshots/03-blocked.png)
- ![Audit](docs/screenshots/04-audit.png)

## Known Limitations & Future Roadmap
- **Current limitations:** demo mode covers 6 built-in topics (real LLM needed for free-form questions); the role switch is a UI toggle; the hash chain proves tampering after the fact but is not a WORM store.
- **Next steps:** bind roles to Db2 authorities / SSO and add RCAC column masks, Db2 vector indexes for large semantic layers, multi-tenant schemas.

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Chandra Pavansai | [@Pavan3030-pr](https://github.com/Pavan3030-pr) | Solo: Db2 integration, agents, UI, docs |

Licence: MIT (see `LICENSE`). Third-party: ibm_db, langchain-db2, LangGraph, FastAPI, sqlglot, fastembed and MiniLM-L6-v2 are open source (Apache-2.0 / MIT).
