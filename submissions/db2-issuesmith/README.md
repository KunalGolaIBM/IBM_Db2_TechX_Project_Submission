# IssueSmith – Agentic Db2 Issue Assistant

> **One-line pitch:** IssueSmith turns a messy IBM Db2 Developer Extension log into a maintainer-ready, evidence-based GitHub issue in seconds, using a team of LangGraph agents that keep their memory, knowledge base, vector search and audit trail inside IBM Db2.

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
- Developers who hit setup, runtime, connection or restart problems in the **IBM Db2 Developer Extension** usually file vague issues ("Db2 not working") or paste raw logs that contain **passwords, connection strings and hostnames**.
- Maintainers then spend time asking for versions, steps and logs, and many reports guess a root cause the logs do not support.
- The community *Db2 Developer Extension – How to raise a good GitHub issue* guide describes the right format (environment, numbered steps, actual vs expected behaviour, sanitised logs, and an **evidence boundary**), but following it by hand is slow and error-prone.
- **Target users:** students and developers using the Db2 Developer Extension, and the maintainers who triage their issues.

---

## Solution Overview
IssueSmith is a multi-agent pipeline with a Streamlit UI and a CLI:

1. **Sanitizer agent** – deterministic regex redaction of passwords, tokens, user IDs, private hostnames/IPs, emails and user paths *before* anything is stored or sent to a model. Public endpoints such as `download.docker.com` are kept because they are evidence.
2. **Triage agent** – extracts evidence lines, environment (extension, OS/WSL, distro, runtime, image, Db2 version), classifies the failure, builds an error fingerprint and stores its embedding in a Db2 `VECTOR` column.
3. **Retriever agent** – semantic search over a troubleshooting knowledge base stored in Db2 with **LangChain `DB2VS`**, plus a search of existing GitHub issues ("search before you submit").
4. **Deduplicator agent** – calls the Db2 stored procedure `FIND_SIMILAR_INCIDENTS`, which ranks earlier incidents with `VECTOR_DISTANCE(..., COSINE)` and flags duplicates.
5. **Writer agent** – an LLM (IBM Granite via Ollama or watsonx.ai, or any OpenAI-compatible model) writes only the narrative. Facts such as the environment table and log excerpts are rendered deterministically from evidence, so they are always real. If no LLM is configured, a rule-based writer is used and the app still works end to end.
6. **Critic agent** – checks every draft against the guide: required sections, title format, **no secrets**, **no certainty language outside "Hypotheses"**, **every quote exists in the log**, verbatim excerpts, environment completeness and numbered steps. Failed drafts go back to the Writer with feedback.
7. **Publisher agent** – finalises the draft for **human review**. Posting to GitHub happens only after the user ticks "I reviewed this draft".

There are also two analytics features:
- **Insights** – Db2 views show incidents by category, the most frequent error signatures, agent latency, environment breakdown (`JSON_VALUE`) and draft quality.
- **Ask the data** – a guarded text-to-SQL analyst agent. It only allows read-only `SELECT` statements on the IssueSmith schema, enforces a row limit and rolls the transaction back.

See [`docs/sample_output/`](docs/sample_output/) for issues generated from the three sample logs.

---

## IBM Db2 Integration
- **Db2 edition & environment:** Db2 Community Edition 12.1.x in Docker/Podman (`icr.io/db2_community/db2`). Version 12.1.2 or later is required for the `VECTOR` type.
- **Connectors used:** `ibm_db` / `ibm_db_dbi` (parameterised SQL everywhere) and **`langchain-db2` (`DB2VS`)** for the knowledge-base vector store.
- **Schema (`src/issuesmith/schema.sql`):**

| Object | Purpose |
|---|---|
| `INCIDENTS` | One row per analysed log: category, confidence, `ENV_JSON` (CLOB JSON), sanitised log (CLOB), redaction count, **`EMBEDDING VECTOR(384, FLOAT32)`**, status (CHECK constraint), duplicate link |
| `EVIDENCE` | Extracted log lines with kind (ERROR / WARNING / OBSERVATION), label and normalised signature. FK with `ON DELETE CASCADE` |
| `ISSUE_DRAFTS` | Every draft round with critic score and notes (JSON). The final draft is flagged and the GitHub URL is stored after posting |
| `AGENT_RUNS` | Audit trail: one row per agent step with status, detail and latency |
| `KB_DOCS` | Created by LangChain `DB2VS`: text CLOB, BSON metadata, VECTOR embedding |
| 5 indexes | Category/time, evidence by incident and signature, drafts, agent runs |
| `V_CATEGORY_STATS`, `V_TOP_SIGNATURES`, `V_AGENT_PERFORMANCE`, `V_DRAFT_QUALITY`, `V_INCIDENT_ENV` | Analytics views. `V_INCIDENT_ENV` uses `JSON_VALUE` over `ENV_JSON` |
| `FIND_SIMILAR_INCIDENTS` (SQL PL procedure) | Vector similarity search inside Db2 returning a result set |

- **Key operations:**
  - `SELECT ... FROM FINAL TABLE (INSERT ...)` returns generated IDs in one round trip.
  - `UPDATE ... SET EMBEDDING = VECTOR(?, 384, FLOAT32)` stores embeddings.
  - `CALL FIND_SIMILAR_INCIDENTS(?)` runs the duplicate search.
  - `DB2VS.similarity_search_with_score` runs knowledge retrieval using `VECTOR_DISTANCE` with `COSINE`.
  - `executemany` handles bulk evidence inserts.
  - Read-only analyst queries are always rolled back.

---

## AI / LLM Architecture
- **Framework:** LangGraph `StateGraph` with a conditional critic → writer retry loop, plus LangChain core (embeddings interface, `DB2VS`).
- **Model providers:**
  - IBM **Granite** via Ollama (`granite3.3:2b`, local and free).
  - **IBM watsonx.ai** (`ibm/granite-3-3-8b-instruct`).
  - Any OpenAI-compatible endpoint.
  - `none`, which uses the rule-based writer.
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local). It falls back automatically to deterministic hash embeddings if the model is not installed.
- **RAG workflow:**
  1. The error fingerprint is embedded.
  2. The closest knowledge docs are retrieved from Db2 (`DB2VS`).
  3. Similar incidents are found with the Db2 procedure.
  4. Knowledge, evidence lines and environment are injected into the writer prompt, which enforces the evidence-boundary rules.
  5. The critic validates the output. The LLM never invents log excerpts, because those are rendered from stored evidence.

---

## Tech Stack
- **Backend / core:** Python 3.11 / 3.12
- **Database:** IBM Db2 Community Edition 12.1 (Docker / Podman)
- **Frontend / UI:** Streamlit (IBM Plex typography), plus a CLI
- **Libraries & tools:** `ibm_db`, `langchain-db2`, `langchain-core`, `langgraph`, `sentence-transformers`, `pandas`, `requests`, `pytest`

---

## Prerequisites
- Docker Desktop (WSL 2 backend on Windows) or Podman
- Python 3.11 or 3.12 and `pip`
- About 4 GB of free RAM for the Db2 container
- Optional: [Ollama](https://ollama.com) for a free local IBM Granite model, or a watsonx.ai API key

---

## Setup & Installation

```bash
# 1. Start Db2 Community Edition (first start takes 5-15 minutes)
docker run -itd --name db2server --privileged=true -p 50000:50000 \
  -e LICENSE=accept -e DB2INST1_PASSWORD=<choose-a-password> -e DBNAME=testdb \
  -v db2data:/database icr.io/db2_community/db2
docker logs -f db2server          # wait for "Setup has completed", then Ctrl+C

# 2. Install the project
cd submissions/db2-issuesmith
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-semantic.txt   # optional: semantic embeddings

# 3. Configure
cp .env.example .env              # Windows: copy .env.example .env
# edit .env -> DB2_PASSWORD=<the password you chose above>
```

On Windows PowerShell, put the `docker run` command on one line (remove the `\` characters).

---

## Configuration
All settings live in `.env` (see [`.env.example`](.env.example)). Values still set to the `your_...` placeholders are ignored.

| Variable | Meaning |
|---|---|
| `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USER`, `DB2_PASSWORD`, `DB2_SECURITY` | Db2 connection |
| `DB2_SCHEMA` | Schema for all IssueSmith objects (default `ISSUESMITH`) |
| `EMBEDDING_BACKEND` | `sentence-transformers` (default) or `hash` |
| `LLM_PROVIDER` | `none`, `ollama`, `watsonx` or `openai` |
| `OLLAMA_*`, `WATSONX_*`, `OPENAI_*` | Provider settings |
| `GITHUB_SEARCH_REPO` | Repository searched for existing issues (default `IBM/db2developerextension-about`) |
| `GITHUB_TOKEN`, `GITHUB_TARGET_REPO` | Optional: post approved drafts. **Use your own test repository for demos.** |
| `MAX_CRITIC_ROUNDS`, `DUPLICATE_DISTANCE` | Agent behaviour |

To use IBM Granite locally:

```bash
ollama pull granite3.3:2b
```

Then set `LLM_PROVIDER=ollama` in `.env`.

---

## Running the Project

```bash
python src/cli.py check      # Db2 connection, service level, VECTOR support, LLM status
python src/cli.py demo       # create schema + load knowledge base + analyse all sample logs + show duplicate detection
streamlit run src/app.py     # web UI at http://localhost:8501
```

Other commands:

```bash
python src/cli.py init-db [--reset]      # create (or recreate) tables, indexes, views, procedure
python src/cli.py seed-kb                # (re)load data/knowledge_base into Db2 via DB2VS
python src/cli.py analyze data/sample_logs/02_quick_restart_stopped_container.log --steps "Opened WSL\nClicked Restart" --out issue.md
python src/cli.py stats                  # print the analytics views
```

In the UI, the **Set up database** button in the sidebar does the same as `init-db` plus `seed-kb`.

---

## Testing & Verification

```bash
pytest -q                     # 25 unit tests, no Db2 server needed
```

The tests cover:
- Sanitiser redaction and false positives (versions, localhost, public endpoints).
- Evidence extraction and classification on all sample logs.
- Critic rules (secrets, invented quotes, root-cause overclaims).
- The full LangGraph pipeline, including duplicate detection and the critic → writer retry loop with a scripted LLM.
- SQL guardrails and schema parsing.

**Verify the Db2 integration yourself** after `python src/cli.py demo`, using any SQL client or `docker exec -it db2server bash -c "su - db2inst1"` then `db2 connect to testdb`:

```sql
SELECT INCIDENT_ID, CATEGORY, STATUS, DUPLICATE_OF FROM ISSUESMITH.INCIDENTS;
CALL ISSUESMITH.FIND_SIMILAR_INCIDENTS(1001);
SELECT * FROM ISSUESMITH.V_TOP_SIGNATURES;
SELECT AGENT, STATUS, LATENCY_MS, DETAIL FROM ISSUESMITH.AGENT_RUNS ORDER BY RUN_ID;
SELECT COUNT(*) FROM ISSUESMITH.KB_DOCS;
```

---

## Screenshots & Demo
Screenshots are in [`docs/screenshots/`](docs/screenshots/):

| Screen | File |
|---|---|
| Agent trace while analysing a log | `docs/screenshots/01-agent-trace.png` |
| Evidence, critic checks and context | `docs/screenshots/02-evidence-critic.png` |
| Final draft issue | `docs/screenshots/03-draft-issue.png` |
| Insights dashboard from Db2 views | `docs/screenshots/04-insights.png` |
| Ask the data (text-to-SQL) | `docs/screenshots/05-ask-the-data.png` |

Example outputs: [`docs/sample_output/`](docs/sample_output/).

---

## Known Limitations & Future Roadmap
- Evidence rules are tuned for the Db2 Developer Extension's runtime, restart and connection flows. New failure types need new signal patterns (one line each in `log_parser.py`).
- Vector search is exact (brute force). Db2 vector indexes (`CREATE VECTOR INDEX`, in preview) would make it scale to large incident histories.
- Roadmap:
  - A VS Code command that sends the current Output channel straight to IssueSmith.
  - Multi-user deployment on Db2 on Cloud.
  - Automatic linking of new incidents to the GitHub issue that later fixed them.

---

## Team Members & Credits
- **Shiva Gupta** (@shivagupta114) – design, agents, Db2 schema, UI

**Credits:**
- The issue structure follows the community *Db2 Developer Extension – How to raise a good GitHub issue* guide (IBM Db2 TechX Summit).
- Built with `ibm_db`, `langchain-db2`, LangGraph and Streamlit (all open source; see their licenses).
- Knowledge-base notes in `data/knowledge_base/` are original summaries written for this project.

**License:** MIT (see [LICENSE](LICENSE)).
