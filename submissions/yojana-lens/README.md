# YojanaLens

> **One-line pitch:** An eligibility agent for Indian welfare schemes where IBM Db2 decides, the LLM only explains, and every verdict is replayable from a stored audit trail.

[![tests](https://img.shields.io/badge/tests-54%20passing-2ecc9a)](#testing--verification)
[![db2](https://img.shields.io/badge/IBM%20Db2-12.1.5-0f62fe)](#ibm-db2-integration)
[![langgraph](https://img.shields.io/badge/orchestration-LangGraph-6d8cff)](#aillm-architecture)

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#aillm-architecture)
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

India runs **thousands of welfare schemes** administered by different ministries and states. Eligibility is written as prose inside PDFs, circulars and amendment notices. Three groups lose because of this:

1. **Citizens** do not know which schemes they qualify for. A widow in Uttar Pradesh may be eligible for a pension, a food entitlement, a housing grant and a girl-child scheme at the same time, and will typically learn about one of them.
2. **Frontline workers** (CSC operators, panchayat staff, NGO caseworkers) make eligibility calls from memory and cannot show *why* they said yes or no.
3. **Auditors** cannot reconstruct a decision made six months ago, because the reasoning lived in a conversation, not in a record.

Generic LLM chatbots make this worse: they *invent* eligibility verdicts, cite clauses that do not exist, and leave no trace. In welfare, an unauditable "you qualify" is a liability, not a feature.

**Users:** citizens checking themselves, and caseworkers checking on their behalf.

---

## Solution Overview

YojanaLens turns each scheme into **two linked representations stored in the same database**:

| Representation | Stored in | Used for |
| --- | --- | --- |
| Source clauses + 384-dim embeddings | `scheme_chunks` (`VECTOR(384, FLOAT32)`) | finding and quoting the paragraph that justifies a rule |
| Machine-checkable criteria | `scheme_rules` (`eq`, `in`, `lte`, `gte`) | deciding eligibility deterministically |

A run is a LangGraph agent:

```
user text → normalize → persist facts → vector retrieval → rule matrix → explain → persist audit
```

The important inversion: **the LLM never decides anything.** Db2 compares the applicant's normalised facts against every active scheme's rules inside a stored procedure. The model receives the finished verdicts as read-only input and writes a short explanation, with citations that are validated against the retrieved set.

### What the user gets

- A ranked list of schemes grouped as **Eligible / Near miss / Needs info / Not eligible**
- For every scheme, the exact criteria that passed or failed, the observed value, the requirement, and the **clause reference** that grounds it
- A follow-up question instead of a guess when a mandatory fact is missing
- An **audit record** for the run: rule rows, model, prompt version, timings, event log

### What makes a "near miss" useful

A verdict is not one bit. `NEAR_MISS` means **exactly one mandatory failure, and it is a numeric threshold** the person can plausibly move towards:

- "Income is 1.8 lakh; the priority ration card requires at most 1.5 lakh." → actionable
- "Your daughter is 17; Sukanya Samriddhi closes at 10." → explains a closed door instead of silently omitting the scheme
- "Widow pension starts at 40; you are 34." → shows a future entitlement

A categorical mismatch (SC/ST scholarship for an OBC household) is **not** a near miss, and is labelled `NOT_ELIGIBLE`. That policy lives in one small, unit-tested function (`src/rules.py`).

### Demo outcome (pinned by `tests/test_corpus.py`)

One household — 34-year-old widow, OBC, rural Uttar Pradesh, two acres, kutcha house, Rs 1.8 lakh, daughter in class 12:

| Eligible (6) | Near miss (3) | Needs info (1) | Not eligible (4) |
| --- | --- | --- | --- |
| PM-KISAN | Sukanya Samriddhi | Ujjwala 2.0 | Post-matric SC/ST |
| PM-JAY | Widow pension | | PM SVANidhi |
| PMAY-Gramin | NFSA priority ration | | PMKVY 4.0 |
| Kanya Sumangala | | | PM Vishwakarma |
| Atal Pension Yojana | | | |
| PM Fasal Bima | | | |

Plus one Madhya Pradesh scheme excluded by the residency pre-filter in SQL.

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 Community Edition **12.1.5.0**, Linux/amd64, running in Docker (`icr.io/db2_community/db2:12.1.5.0`). The version is pinned because native `VECTOR` support requires 12.1.2+, and the version used here is 12.1.5.
- **Connector / Driver Used:** `ibm_db` 3.2.3 (Python, DB2 CLI driver shipped inside the wheel). Every statement is executed with parameter markers; no SQL is assembled by string concatenation at runtime.
- **Framework:** LangGraph 0.2 (`StateGraph`), with FastAPI serving the API and the UI.

### Schema / Data Models

| Table | Purpose |
| --- | --- |
| `schemes` | dimension: 15 active schemes, level, state, category, source URL |
| `scheme_rules` | 44 machine-checkable criteria (`rule_op` ∈ `eq, in, lte, gte`), each with `clause_ref` and a `chunk_id` grounding it |
| `scheme_chunks` | 39 source clauses + **native `VECTOR(384, FLOAT32)`** embeddings |
| `profiles` | the raw text the person actually wrote + normalised JSON |
| `profile_facts` | EAV facts (`fact_num`, `fact_text`) that rules can join against |
| `agent_runs` | one row per run: model, prompt version, latency, status, summary |
| `decision_trace` | one row per **criterion evaluated**, with observed value, verdict, clause and narrative |
| `audit_log` | append-only event log, with a SHA-256 prefix of the SQL that ran |
| `schema_meta` | declares which Db2 capabilities the schema relies on |

Indexes: `schemes(state_code, status, category)`, `scheme_rules(scheme_id)`, `scheme_rules(criterion_code)`, `scheme_chunks(scheme_id)`, `profile_facts(profile_id)`, `decision_trace(run_id)`, `decision_trace(run_id, scheme_id)`, `audit_log(run_id)`.

### Key Operations

**1. Retrieval — residency filter and vector ranking in one statement.**

```sql
WITH candidate AS (
    SELECT s.scheme_id
    FROM schemes s
    WHERE s.status = 'ACTIVE'
      AND (CAST(:state AS VARCHAR(8)) IS NULL OR s.state_code IN ('ALL', :state))
      AND (CAST(:category AS VARCHAR(32)) IS NULL OR s.category = :category)
)
SELECT c.chunk_id, c.scheme_id, c.clause_ref,
       VECTOR_DISTANCE(c.embedding,
                       VECTOR(CAST(:query_vec AS VARCHAR(32672)), 384, FLOAT32),
                       COSINE) AS distance
FROM scheme_chunks c
JOIN candidate s ON s.scheme_id = c.scheme_id
ORDER BY distance ASC
FETCH FIRST 12 ROWS ONLY;
```

**2. Decision — the whole eligibility matrix moves into Db2.**

`CALL SP_RECORD_TRACE(run_id, profile_id)` joins every active scheme's rules against the applicant's facts and persists one row per criterion, with the verdict computed by SQL:

```sql
CASE
  WHEN f.fact_key IS NULL THEN 'UNKNOWN'
  WHEN r.rule_op = 'eq'  THEN CASE WHEN LOWER(f.fact_text) = LOWER(r.value_text) THEN 'PASS' ELSE 'FAIL' END
  WHEN r.rule_op = 'in'  THEN CASE WHEN LOCATE(','||LOWER(f.fact_text)||',',
                                             ','||LOWER(r.value_text)||',') > 0
                                   THEN 'PASS' ELSE 'FAIL' END
  WHEN r.rule_op = 'lte' THEN CASE WHEN f.fact_num IS NULL THEN 'UNKNOWN'
                                   WHEN f.fact_num <= r.value_num THEN 'PASS' ELSE 'FAIL' END
  WHEN r.rule_op = 'gte' THEN CASE WHEN f.fact_num IS NULL THEN 'UNKNOWN'
                                   WHEN f.fact_num >= r.value_num THEN 'PASS' ELSE 'FAIL' END
  ELSE 'UNKNOWN'
END
```

**3. Audit — reconstruct any decision.** `sql/03_queries.sql` contains the exact queries used by `GET /api/runs/{id}`: run metadata, every rule row, and the event log.

### Why this is a Db2 argument, not a checkbox

- The clause vector and the rule that clause justifies are **the same database, same transaction, same join**. There is no Pinecone-plus-Postgres sync problem, and no window where the retrieved clause and the evaluated rule disagree.
- The comparison of *every criterion of every active scheme* against the applicant's facts is one `INSERT … SELECT` inside `SP_RECORD_TRACE`. Python passes two strings.
- The audit trail is relational: `decision_trace` joins back to `scheme_rules` and `scheme_chunks`, so a reviewer can reconstruct why each verdict happened without replaying an LLM.
- `VECTOR_DISTANCE(..., COSINE)` is computed by Db2's engine on a native `VECTOR` column — not by Python after fetching every row.

---

## AI / LLM Architecture

**Framework:** LangGraph (`StateGraph`), with LangChain-compatible chat models called over the OpenAI-compatible protocol.

```
begin ──► normalize ──► persist_facts ──► retrieve ──► record_trace ──► explain ──► finalize
              │
              └──► clarify  (when no fact could be extracted)
```

| Node | What it does | LLM? |
| --- | --- | --- |
| `begin` | creates the profile and run rows, logs `request.received` | no |
| `normalize` | prose → typed facts; drops unknown keys; keeps evidence | yes, with a deterministic fallback |
| `persist_facts` | writes `profile_facts` (EAV) | no |
| `retrieve` | embeds the query locally, runs the Db2 vector query | no |
| `record_trace` | calls `SP_RECORD_TRACE` | no |
| `explain` | narrates verdicts, validates citations | yes |
| `finalize` | writes counts, latency, status, `run.completed` | no |

### Guardrails that are structural, not prompt suggestions

1. **The model cannot change a verdict.** It receives labels it did not produce; the labels are already persisted in `decision_trace`.
2. **Citations are validated.** The model returns `cited_chunk_ids`; anything not in the retrieved set for that scheme is dropped, and if nothing valid remains the clause attached to the rule is used instead.
3. **Unknowns stay unknown.** If a mandatory fact is missing, the verdict is `CLARIFY` — the UI shows a question, not an assumption. Ration-card ownership does not imply BPL status.
4. **Graceful degradation.** No API key → templated narration from the rule trace (`LLM_PROVIDER=mock`). A failing live call falls back to the same path. A demo cannot hard-crash on a free-tier quota.
5. **Closed vocabulary.** Facts are coerced against an allow-list (`src/models.py`); an LLM cannot invent `crypto_holdings` and have it reach SQL.

### Embeddings

`sentence-transformers/all-MiniLM-L6-v2` (384-dim) via `fastembed` (ONNX, CPU). It runs offline and is **baked into the Docker image at build time**, so no API key and no network are needed at inference time. The dimension is asserted against the `VECTOR(384, FLOAT32)` column at write time, so a model swap fails loudly instead of silently truncating.

---

## Tech Stack

| Layer | Choice |
| --- | --- |
| Database | IBM Db2 12.1.5 (Community Edition, Docker), native `VECTOR` + `VECTOR_DISTANCE` |
| Driver | `ibm_db` 3.2.3 |
| Orchestration | LangGraph 0.2 (`StateGraph`, conditional edge, typed state) |
| LLM | any OpenAI-compatible endpoint (Groq / OpenRouter / OpenAI / Ollama / watsonx gateway) |
| Embeddings | `fastembed` + `all-MiniLM-L6-v2` (ONNX, 384-dim, offline) |
| API | FastAPI + Uvicorn |
| UI | server-served HTML/CSS/vanilla JS (no build step, works offline) |
| Tests | pytest (54 tests, no database required) |

---

## Prerequisites

- Docker Desktop 4.x with **8 GB RAM** allocated (Db2 will not start reliably with less)
- ~10 GB free disk (Db2 image plus the model cache)
- No Python installation required for the Docker path
- Optional, for running the app outside Docker: Python 3.11 (not 3.14 — `ibm_db` has no 3.14 wheels)

---

## Setup & Installation

```bash
git clone https://github.com/<your-handle>/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission/submissions/yojana-lens

cp .env.example .env        # optional: add an LLM key, otherwise mock mode is used

docker compose up --build
```

First boot takes **5–10 minutes**: the Db2 container creates the instance and the `YOJANADB` database, then the app waits for it, creates the schema, installs `SP_RECORD_TRACE`, embeds 39 clauses and seeds the corpus.

Open **http://localhost:8000**. The header shows live corpus counters read from Db2 — if those numbers appear, the whole path is working.

To confirm Db2 directly:

```bash
docker compose exec db2 su - db2inst1 -c "db2 connect to YOJANADB && db2 'select count(*) from schemes'"
```

---

## Configuration

All settings are environment variables (see `.env.example`). Nothing secret is committed.

| Variable | Default | Notes |
| --- | --- | --- |
| `DB_HOST` / `DB_PORT` | `db2` / `50000` | `localhost` when running outside compose |
| `DB_NAME` | `YOJANADB` | created by the Db2 container |
| `DB_USER` / `DB_PASSWORD` | `db2inst1` / `change-me-locally` | change the password locally |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | must stay at 384 dims |
| `EMBEDDING_DIM` | `384` | must match the `VECTOR(384, …)` column |
| `LLM_PROVIDER` | `openai_compatible` | narration provider; an empty key still selects mock mode |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | any OpenAI-compatible base URL |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | e.g. `ibm/granite-3-8b-instruct` |
| `LLM_API_KEY` | *(empty)* | empty ⇒ mock narration, everything still works |
| `RETRIEVER_TOP_K` | `8` | clauses kept for explanation |

> **Secrets:** `.env` is git-ignored, `.env.example` contains dummy values only, and the submission validator's forbidden-file check passes.

---

## Running the Project

| Command | What it does |
| --- | --- |
| `docker compose up --build` | full stack |
| `docker compose logs -f app` | watch schema creation, seeding, requests |
| `docker compose exec app python -m src.cli stats` | corpus counters from Db2 |
| `docker compose exec app python -m src.cli ask "..."` | run one decision from the CLI |
| `docker compose exec app python -m src.cli seed` | re-ingest the corpus (idempotent) |
| `docker compose exec app python -m src.cli reset` | drop and rebuild (development only) |

API: `POST /api/ask`, `GET /api/runs/{id}`, `GET /api/schemes`, `GET /api/stats`, `GET /api/health`, and interactive docs at `/docs`.

```bash
curl -s localhost:8000/api/ask -H 'Content-Type: application/json' \
  -d '{"text":"I am a 34-year-old widow in a village in Uttar Pradesh, OBC, I farm two acres, kutcha house, income 1.8 lakh, daughter in class 12, bank account."}'
```

---

## Testing & Verification

```bash
# inside the container
docker compose exec app python -m pytest tests -q

# or on a host with Python 3.11
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
.venv/bin/pip install -r requirements.txt          # macOS / Linux
.venv/Scripts/python -m pytest tests -q
```

**54 tests, no database required.** They cover:

- `test_corpus.py` — every scheme has rules, every rule uses the canonical vocabulary and resolves to a clause on the same page, and the exact demo verdicts are pinned (6 / 3 / 1 / 4, one filtered)
- `test_agent_flow.py` — runs the **real LangGraph** end to end against a stubbed Db2 layer: node order, conditional edge, result ordering, narration, citations, audit events
- `test_rules.py` — the four-verdict policy, including near-miss vs categorical rejection
- `test_extract.py` — fact extraction, including the trap where "my daughter is in class 12" must not become the applicant's education
- `test_llm_guardrails.py` — invented citations are dropped; transport failures degrade to templated narration
- `test_models.py` — unknown keys and unparsable values never reach SQL
- `test_sql_assets.py` — parameter markers and the SQL files can never drift apart
- `test_graph_wiring.py` — the graph compiles, every node exists, and a missing driver produces an actionable error

Offline, the suite runs in under a second.

---

## Screenshots & Demo

- `docs/demo-script.md` — a three-minute walkthrough with timings and the exact narration
- `docs/screenshots/` — place the submission screenshots here (`01-results.png`, `02-rule-trace.png`, `03-audit-record.png`)

Suggested captures:

1. Results view with the four verdict groups and the live corpus counters in the header
2. An expanded rule trace showing observed value, requirement, verdict and clause
3. The audit drawer with the stored `decision_trace` and the event log

---

## Known Limitations & Future Roadmap

Honest limitations:

- **Brute-force vector search.** 39 clauses are scanned per query. That is the right trade-off at this scale and is documented rather than hidden. A Db2 vector index becomes worthwhile past a few thousand chunks; the query shape does not change.
- **Curated corpus.** Rules were extracted by hand from public scheme guidelines for demonstration. They are not a live feed, and the UI links to the official source for each scheme. Real deployment needs a review workflow per amendment.
- **English embeddings.** Queries are normalised to English keywords before embedding. A multilingual embedder is a drop-in change (`EMBEDDING_MODEL` + column dimension).
- **Closed rule vocabulary.** 15 criteria cover the seeded schemes. A new criterion requires a vocabulary entry and a rule row — deliberately, so nothing reaches SQL unchecked.
- **Single-node, trusted-network deployment.** No authentication or multi-tenancy; profiles are personal data and would need encryption, retention limits and consent capture in production.

Roadmap: vector index + larger corpus, state-specific rule packs, document OCR intake (ration card, land record), a caseworker review queue, Hindi UI, and an IBM watsonx Granite narrator via the same OpenAI-compatible client.

---

## Team Members & Credits

**Solo submission** — built for IBM Db2 TechX Hackathon 2026.

- **Author:** Aditya Lobhe ([@Aditya02-cpu](https://github.com/Aditya02-cpu))
- **Role:** everything — data curation, schema, agent, API, UI, tests, docs
- **AI/LLM framework requirement:** LangGraph (used as the actual execution engine, not a wrapper around a single prompt)
- **Db2 features used:** relational tables, indexes, `VECTOR` column, `VECTOR_DISTANCE(…, COSINE)`, SQL PL stored procedure, transactional writes, `SYSCAT` introspection, `CURRENT TIMESTAMP`, identity columns, foreign keys with cascading deletes

Scheme rules were curated from publicly available guidelines on the official portals linked in `data/schemes.json`. This project is a technical demonstration and not affiliated with any government body.
