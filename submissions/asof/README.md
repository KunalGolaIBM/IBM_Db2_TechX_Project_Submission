# AsOf

> **What did the policy say on that date, and what did your AI tell the customer?**
> AsOf checks each policy claim in an AI assistant's answer against the policy version in force on the customer's date, stops answers that contradict it, and keeps a tamper-evident Db2 record of what was said and why.

[![CI](https://github.com/JustJay7/asof/actions/workflows/ci.yml/badge.svg)](https://github.com/JustJay7/asof/actions/workflows/ci.yml)

**Try it:** [Live demo](https://136-108-251-170.sslip.io) | [Demo video (2:58)](https://www.youtube.com/watch?v=mntehVWQn8E) | `./quickstart.sh` (one command, no API key)

**Built on IBM Db2 12.1 for Db2Hack 2026.** Source: [github.com/JustJay7/asof](https://github.com/JustJay7/asof) (standalone mirror of `submissions/asof`). Bitemporal tables, native `VECTOR` search, SQL/JSON, in-database SHA-256, triggers, SQL PL and least-privilege users, with LangGraph, LangChain and the official `langchain-db2` connector.

![The same draft checked for two customer dates: for 10 March 2026 the retroactive bereavement claim is contradicted by BRV-002 v1 and the answer is corrected; for 2 June 2026 it is supported by BRV-002 v2 and released as written](docs/screenshots/00-same-draft-two-dates.png)

*The same draft, two customer dates: contradicted by the March policy and corrected in 5 of 5 live runs, supported by the June policy and released in 4 of 5 (one was held for a person) ([the runs](docs/live-runs/same-draft-two-dates.json)).*

**At a glance** (latest runs, 7 and 8 Nov 2026):

| | |
|---|---|
| **The date decides** | Checked against today's policy instead of the customer's date, the same check released 6 of 16 date-sensitive wrong drafts; with the customer's date, none ([measured](docs/evaluation.md#why-the-date-matters-measured)). |
| **Safety** | Latest run: 0 of 121 wrong drafts released across nine frozen splits, 1 of 70 correct drafts stopped (rewritten from the clause instead of released as written). On the five splits that never motivated a fix, 0 of 65 (95% upper bound about 4.6%) ([results](#testing--verification)). |
| **Db2 does the work** | `FOR BUSINESS_TIME AS OF` with `VECTOR_DISTANCE` in one statement, a hash-chained ledger in SQL PL, `JSON_TABLE`, column masks, in-database embeddings, partitions and MQTs measured at 1,000,000 decisions; `python -m asof.db2check` runs 34 feature checks. |
| **Tamper evidence** | Triggers stop even the owner; `VERIFY_CHAIN` finds an edited row; receipts and anchors kept outside Db2 catch a rebuilt ledger. |
| **People where the check stops** | Held answers go to a specialist inbox, and Db2 records a reply only if it passes the same check; customers told a rule that later changed get a checked correction notice a specialist approves. |
| **Engineering** | A LangGraph check with fixed edges that fails closed, five least-privilege Db2 users, 1231 tests (80% line coverage), mypy, and three CI jobs including IBM's stock Db2 image. |

> **Fictional data.** "Aurelia Air", "Fernhollow Bank" and every policy, fee schedule, FAQ and help-centre answer in this repository are invented for the demo. The airline is modelled on the kind of policy at issue in *Moffatt v. Air Canada*; neither describes a real company.

**The reviewer's quick path** (from this folder; Python 3.12 and Docker; no API key needed). About 90 seconds when Db2 is already running and the packages are cached; a first Db2 start adds 2 to 25 minutes, and the first install downloads PyTorch:

```bash
./quickstart.sh --no-serve          # Db2, schema, five least-privilege users, seed data; no key: replay mode
source .venv/bin/activate
python src/main.py &                # the UI and API on http://127.0.0.1:8000
python scripts/smoke_check.py       # a real check through the API: the Moffatt question, recorded in the Db2 ledger
python -m asof.db2check             # 34 checks of the Db2 features AsOf relies on
pytest -q                           # unit tests plus Db2 integration tests in throwaway schemas
```

Then open http://127.0.0.1:8000 (console) and http://127.0.0.1:8000/chat (customer side). Without a key, the built-in scenarios replay recorded model outputs while everything else runs live in Db2 ([replay mode](#replay-mode-no-model-at-all)).

**For judges: where each criterion is evidenced.**

| Criterion | Start here |
|---|---|
| IBM Db2 integration & depth | [IBM Db2 Integration](#ibm-db2-integration), [the full Db2 page](docs/db2.md), the SQL in [src/asof/sql/](src/asof/sql/), `python -m asof.db2check`, [the DDL as Db2 holds it](docs/ddl/asof_schema_db2look.sql) |
| Innovation & real-world impact | [Problem Statement](#problem-statement), [why the date matters, measured](docs/evaluation.md#why-the-date-matters-measured), [how AsOf compares](docs/overview.md#how-asof-compares), [the specialist inbox and correction notices](docs/db2.md#the-specialist-inbox-and-correction-notices) |
| Technical architecture & AI | [architecture.md](architecture.md) (diagrams, design decisions, threat model summary; in full: [design decisions](docs/design-decisions.md), [threat model](docs/threat-model.md), [schema](docs/schema.md)), [AI / LLM Architecture](#ai--llm-architecture-if-applicable), [routing, measured](docs/routing_eval.md) |
| Security | [architecture.md: Security & Secrets Management](architecture.md#security--secrets-management), each rubric point mapped to code and tests |
| Reproducibility & code quality | the quick path above, [Setup & Installation](#setup--installation), [Testing & Verification](#testing--verification), [the frozen evaluation](docs/evaluation.md), CI badge |
| Documentation & presentation | [Screenshots & Demo](#screenshots--demo), [every screen](docs/screenshots.md), [slides](docs/slides/AsOf_slides.pdf) |

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture (if applicable)](#ai--llm-architecture-if-applicable)
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

In *Moffatt v. Air Canada*, 2024 BCCRT 149, Air Canada's website chatbot told a grieving customer he could apply for a bereavement fare after travelling. The airline's own policy page said the opposite. The tribunal held the airline liable for negligent misrepresentation: the company owns what its chatbot says, and correct information on another page is no defence.

Every company running a customer-facing assistant has the same exposure, and it grows: policies get new versions with new effective dates, so the right answer depends on the customer's date, and when a complaint arrives months later the company usually cannot show which version an answer relied on or what its systems held at the time.

**Who it is for:** CX platform, compliance and legal-operations teams at airlines, banks, insurers and telcos, the organisations that already run Db2 as their system of record.

---

## Solution Overview

Given an AI-generated answer and the date that matters (booking or travel date, supplied by the calling system, never guessed by the model), AsOf finds the applicable policy version, flags claims that contradict it, stops unsupported answers from going out, and keeps the evidence needed to review that decision later.

1. **As-of lookup:** one Db2 query returns the clauses in force on the date, ranked by meaning.
2. **Claim check:** a model extracts and judges each policy claim with a verbatim quote; deterministic rules on each clause's JSON parameters overrule it.
3. **Decision:** PASS with citations, CORRECTED (rewritten from the clause and checked again) or ESCALATED to a person; any error fails closed.
4. **Audit ledger:** append-only, hash-chained Db2 rows, replayable with `FOR SYSTEM_TIME AS OF`.
5. **Change impact:** after a policy change, Db2 finds the answers it made wrong for their date, and an agent drafts checked corrections for a person to approve.
6. **People:** held answers go to a specialist inbox, whose replies are checked and recorded the same way.
7. **Routing and intake:** Db2 routes a draft to its policy document; a policy PDF becomes clause versions that code checks and an editor approves.
8. **Anywhere:** the API, a LangChain runnable, a chat page, an MCP tool and a Langflow component, on OpenRouter, Ollama or IBM watsonx.ai.

**Two domains, one check:** Aurelia Air's customer service plan (34 clauses, 38 versions) and Fernhollow Bank's fee schedule (18 clauses, 26 versions) share the schema, the query, the rule checker, the ledger and the agents.

**How AsOf compares.** Amazon Bedrock Automated Reasoning checks, NVIDIA NeMo Guardrails and IBM watsonx.governance already check or score answers against policies or retrieved text; AsOf did not invent that. It adds time, inside the customer's system of record: effective-dated policy versions, bitemporal replay of what the database held at a moment, and change impact on past answers ([the comparison and the build status](docs/overview.md)).

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 12.1.5.0 Community Edition in Docker: the VS Code extension's instance, IBM's stock image or AsOf's Compose service ([setup paths](#setup--installation)); database `testdb`, schema `ASOF`. The public demo runs the Compose path on a Google Cloud VM.
- **Connector / Driver Used:** `ibm_db` / `ibm_db_dbi` with parameter markers only; SQLAlchemy with `ibm_db_sa` (Ask the ledger); LangChain's official `langchain-db2` (`DB2VS`); IBM's `db2-sqlglot-dialect`, `ibm-dbt-db2` adapter, the Airflow IBM Db2 provider and the `lfx-ibm` Langflow bundle.
- **Database Schema / Data Models:** a bitemporal `POLICY_CLAUSE` (business and system time, history table, `VECTOR(384, FLOAT32)` embeddings, `RULE_JSON` checked as JSON), an append-only hash-chained `ANSWER_LEDGER` with `CLAIM_CITATION` rows, and the help-centre, review, notice and intake tables ([schema](docs/schema.md)).
- **Key Queries & Operations:** the as-of plus vector query below; replay with `FOR SYSTEM_TIME AS OF`; policy changes through `UPDATE ... FOR PORTION OF BUSINESS_TIME` in SQL PL; every decision appended and hash-chained by `APPEND_LEDGER` and verified by `VERIFY_CHAIN`; `CHANGE_IMPACT` for stale answers; analytics over views and MQTs ([db2.md](docs/db2.md)).

Db2 12.1.5 does the work, not just the storage ([everything, with the SQL and the measurements](docs/db2.md)):

- **Bitemporal policy versions.** `POLICY_CLAUSE` has a business-time period (when a version applies) and a system-time period (when Db2 recorded it), with a history table. Policy changes run `UPDATE ... FOR PORTION OF BUSINESS_TIME` inside the SQL PL procedure `APPLY_POLICY_CHANGE`, so Db2 splits the version itself.
- **Time and meaning in one statement.** The check's retrieval, the clauses in force on the customer's date ranked by `VECTOR_DISTANCE` over a native `VECTOR(384, FLOAT32)` column with a vector index:

  ```sql
  SELECT c.CLAUSE_ID, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON,
         VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
  FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c
  WHERE c.DOC_ID = ? ORDER BY DIST FETCH EXACT FIRST ? ROWS ONLY
  ```

  `FETCH EXACT` keeps the search exact although a vector index exists; replay puts `FOR SYSTEM_TIME AS OF ?` in front: the same question, answered from what the database held when the assistant answered.
- **A ledger Db2 guards.** Every decision is a row whose SHA-256 is computed in SQL PL (`APPEND_LEDGER`) and chained to the previous one under a lock; triggers stop `UPDATE` and `DELETE` even for the owner; `VERIFY_CHAIN` recomputes the chain; receipts and anchors kept outside Db2 catch a rebuilt ledger.
- **Rules in JSON, checked in SQL too.** Each version's rule parameters are `RULE_JSON` (a `JSON_EXISTS` check constraint), read with `JSON_VALUE` and `JSON_TABLE` in the views and procedures; `CHANGE_IMPACT`, `RESOLVE_ESCALATION`, `ADD_NOTICE` and `DECIDE_NOTICE` enforce in SQL PL what the application may not decide alone.
- **More of Db2:** column masks, in-database embeddings (`CREATE EXTERNAL MODEL`, `TO_EMBEDDING`), monthly partitions and `REFRESH IMMEDIATE` MQTs [measured at 1,000,000 decisions](docs/db2.md#monthly-partitions-and-materialized-query-tables-measured-at-1000000-decisions), an [online backup restored into a new database](docs/db2.md#backup-and-restore-proven-on-a-database-that-did-not-exist), TLS, dbt (`ibm-dbt-db2`) and Airflow (IBM Db2 provider).
- **Five least-privilege users:** runtime `asofapp` (reads and eleven procedures, no writes or DDL), reviewer `asofrev` (two procedures, no table), editor `asofedit`, analyst `asofread` (audit views, text masked) and dbt's `asofmart`.
- **Drivers:** `ibm_db` with bound parameters only, `ibm_db_sa`, `langchain-db2`'s `DB2VS`, and SQLGlot's Db2 dialect gating the one model-written query ([Ask the ledger](docs/db2.md#ask-the-ledger-questions-for-auditors-as-a-read-only-db2-user)).

### What building AsOf taught us about Db2

Each finding was checked on Db2 12.1.5.0 Community Edition in IBM's stock image and links to its evidence ([measurements in full](docs/db2.md#storage-the-vector-index-and-access-plans)).

- **A Db2 defect: a forced vector-index scan under a date predicate fails with SQL0901N.** With an optimizer guideline forcing the vector index under `FOR BUSINESS_TIME AS OF` (or plain `BUS_START <= ? AND BUS_END > ?`), a search list of 200 returns rows and 210 or more fails with SQL0901N, "Fetched nodes unexpectedly unsorted.", from 1,500 rows up; without the date predicate a search list of 1,000 runs. [One-command repro](docs/explain/sql0901n_repro.py) (needs only `ibm_db`, cleans up after itself), [test](tests/test_db2_vectorbench.py).
- **The optimizer leaves the vector index out under `FOR BUSINESS_TIME AS OF`.** At 100,000 clause versions, `FETCH APPROX` under the period is planned as the same B-tree range scan as the exact query, while without the period it reads the vector index ([with the period](docs/explain/as_of_retrieval_approx_100k.txt), [without](docs/explain/nearest_any_date_approx_100k.txt)). An optimizer guideline can force it (above), at 4.6 ms with recall@10 of 1.00 on average ([benchmark](docs/vector_benchmark.md)).
- **With a vector index present, `FETCH FIRST` means approximate.** A plain `FETCH FIRST 10 ROWS ONLY` reads the index ([plan](docs/explain/nearest_any_date_default_100k.txt)), so the check says `FETCH EXACT`; and `FETCH APPROX FIRST ? ROWS` never uses the index, only a constant k does ([benchmark](docs/vector_benchmark.md#a-generic-table)). Exact search under the period took 84 ms at 100,000 versions, so AsOf keeps it ([decision](docs/design-decisions.md#db2-storage-queries-and-schema)).
- **Three of the six distance metrics can be indexed.** `VECTOR_DISTANCE` takes COSINE, EUCLIDEAN, EUCLIDEAN_SQUARED, DOT, HAMMING and MANHATTAN; `CREATE VECTOR INDEX` takes only the first three for `FLOAT32` (SQL0104N for the rest) and only the Euclidean pair for `INT8` (SQL0628N for COSINE), and a 384-dimension `FLOAT32` index does not fit a 4K page (SQL0614N) ([metrics test](tests/test_db2_vector_metrics.py), [page test](tests/test_db2_findings.py)).
- **`FOR PORTION OF BUSINESS_TIME` does the versioning.** One `UPDATE ... FOR PORTION OF BUSINESS_TIME` in `APPLY_POLICY_CHANGE` splits the version in force at the change date, and system versioning moves the replaced row to the history table, where replay still finds it ([test](tests/test_db2_policy_change.py)).
- **`JSON_TABLE` takes only `'strict $'` as its row path.** `'lax $.claims[*]'` fails with SQL0104N ("Expected tokens may include: "strict $"") and the `ON ERROR` clause is mandatory, so `CLAIMS_FROM_JSON` reads each array position with a literal index ([test](tests/test_db2_findings.py)).
- **`ibm_db` cannot return a NULL integer OUT parameter.** `callproc` fails with CLI0110E (SQLSTATE 22002), while a NULL `VARCHAR` comes back as `None`, so `VERIFY_CHAIN` reports 0 for "no bad row" and `ledger.verify_chain` maps 0 back to `None` ([test](tests/test_db2_findings.py), [procedure](src/asof/sql/03_procedures.sql)).
- **Db2 can call the embedding model itself.** With `CREATE EXTERNAL MODEL` and `TO_EMBEDDING`, the engine sends the HTTP request, one per row of an `UPDATE`, and setup uses it only when Db2's vector matches the app's local one ([indb.py](src/asof/indb.py), [details](docs/db2.md#in-database-embeddings-db2-1215)).
- **The VS Code extension's Create Db2 instance flow switches the global Docker context** to Docker Desktop's on macOS with Colima, and then waits for an app that is not there; reported with repro steps as [IBM/db2developerextension-about#25](https://github.com/IBM/db2developerextension-about/issues/25).

---

## AI / LLM Architecture (if applicable)

- **Framework:** LangGraph for the check, the change-impact agent and the router (graphs with fixed edges); LangChain for structured outputs, the Db2 retriever, `langchain-db2`'s `DB2VS` and the Ask the ledger SQL chain; plus a Langflow component and an MCP server.
- **Model Provider & Model:** OpenRouter with `google/gemini-3.1-flash-lite` by default; local Ollama `qwen2.5:7b-instruct` with no key, also the fallback when a hosted call fails; IBM watsonx.ai or any OpenAI-compatible endpoint; replay mode with no model. Embeddings: `all-MiniLM-L6-v2` (384 dimensions) on CPU, or in Db2 with `TO_EMBEDDING`.
- **RAG / Tool Calling Workflow:** each claim retrieves the clauses in force on the customer's date from Db2; the judge must quote them verbatim from escaped data blocks and the rule check on `RULE_JSON` can overrule it; an uncovered claim goes to an agent with Db2 tools (at most 3 calls); the decision and its citations go to the ledger (steps below, [in depth](docs/ai.md)).

A LangGraph graph with fixed edges ([checkgraph.py](src/asof/checkgraph.py)); no model decides whether a check, the re-check or the ledger write happens ([in depth](docs/ai.md)):

1. **Redact** names, emails, phone and card numbers before anything reaches the model or the ledger.
2. **Extract** atomic policy claims (strict schema, at most 8); a premise about the customer the extractor drops, or a policy sentence when it finds no claim at all, is judged as written.
3. **Retrieve** the clauses in force on the date for each claim (the Db2 query above).
4. **Judge** every claim in one call, with a verbatim quote from a retrieved clause; a quote that is not in the clause downgrades the verdict.
5. **Rule check** the claim's numbers, deadlines, permissions and family lists against `RULE_JSON`; a mismatch overrules the judge.
6. **Investigate** an uncovered claim with an agent whose tools query Db2 (at most 3 calls), then **decide**: a contradiction is rewritten from the clause text and must pass a full re-check; anything uncovered goes to a person.
7. **Record** the decision and every citation through `APPEND_LEDGER`; if that fails, nothing is released.

User and clause text stay in escaped data blocks, outputs pass strict Pydantic schemas, and every call has a deadline; a failed hosted call falls back to local Ollama, recorded in the ledger. The change-impact and routing agents are LangGraph graphs too; Ask the ledger is a LangChain SQL chain.

### Replay mode: no model at all

With `LLM_PROVIDER=replay` (what `./quickstart.sh` sets when there is no key), every model call is answered from [recorded outputs](src/asof/data/replay.json) of the hosted model, keyed by a SHA-256 of the input; Db2 runs live. An unrecorded input fails closed, and the ledger labels replayed decisions `replay:` ([details](docs/ai.md#replay-mode-no-model-at-all)).

---

## Tech Stack

- **Backend / Core:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings
- **Database:** IBM Db2 12.1.5.0 Community Edition (Docker); `ibm_db` / `ibm_db_dbi`; SQLAlchemy with IBM's `ibm_db_sa`
- **AI:** LangGraph, LangChain, `langchain-db2`, `langchain-openai`, `langchain-ollama`, `langchain-ibm` (optional), `all-MiniLM-L6-v2` embeddings (local, CPU), Db2's `TO_EMBEDDING`
- **Other:** pypdf (policy intake), the MCP SDK, SQLGlot with IBM's `db2-sqlglot-dialect`
- **Frontend / UI:** plain HTML, CSS and JavaScript served by FastAPI (no framework, no build step), under a strict Content Security Policy
- **Data and orchestration (each in its own environment):** dbt with `ibm-dbt-db2`, Apache Airflow with the IBM Db2 provider, Langflow's `lfx` with `lfx-ibm`
- **Libraries & Tools:** Docker Compose, pytest, ruff, mypy, pip-audit, GitHub Actions

---

## Prerequisites

- **Python 3.12** (the lock file supports only 3.12) on macOS 14+ with Apple Silicon or x86-64 Linux; on Windows, WSL 2 with Ubuntu. Intel Macs cannot install the Python side (no PyTorch 2.15 wheel).
- **Docker** (Docker Desktop, Docker Engine, or Colima on macOS) and about 10 GB of free disk.
- **IBM Db2 12.1.2 or later** (12.1.5 tested), from any of the three paths below.
- **An LLM, optional:** an [OpenRouter](https://openrouter.ai/keys) key, or [Ollama](https://ollama.com) with `ollama pull qwen2.5:7b-instruct`. With neither, replay mode runs the built-in scenarios.
- **Apple Silicon:** IBM's Db2 image is Intel-only; with Colima, `colima start --cpu 4 --memory 6 --vz-rosetta`, then path C.

Install commands per platform: [docs/setup.md](docs/setup.md#prerequisites).

---

## Setup & Installation

**Get the code:** `git clone https://github.com/JustJay7/asof.git && cd asof` (the standalone repo), or `cd submissions/asof` in a clone of the IBM submission repo.

**One command:** `./quickstart.sh`. It creates `.venv` and `.env`, uses the Db2 on `localhost:50000` (paths A and B) or starts AsOf's Compose service (path C), runs setup and serves the app; CI runs it on a bare runner on every push. The steps it automates:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
# Linux only, first: pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -c requirements.lock && pip install -e . --no-deps
cp .env.example .env     # set DB2_PASSWORD, and OPENROUTER_API_KEY (or LLM_PROVIDER=ollama)
```

**A Db2 database** (one database, `testdb` at `localhost:50000` by default, and its owner account):

- **A. IBM Db2 Developer Extension for VS Code** (the organizers' path): **Create Db2 instance** with port `50000`, user `db2inst1`, database `testdb`; put the password in `.env` as `DB2_PASSWORD`, and set `DB2_PORT` if the instance shows another port.
- **B. IBM's image with Docker** (Intel or Linux; tested in CI on every push):

  ```bash
  docker run -itd --name db2server --privileged=true -p 127.0.0.1:50000:50000 \
    -e LICENSE=accept -e DBNAME=testdb \
    -e DB2INST1_PASSWORD="$(sed -n 's/^DB2_PASSWORD=//p' .env)" \
    -v db2data:/database icr.io/db2_community/db2:12.1.5.0
  docker logs -f db2server     # wait for "Setup has completed", then Ctrl+C
  ```

- **C. AsOf's Compose file** (Apple Silicon, or anywhere): `docker compose up -d --wait db2`. It adds a thin fix to IBM's image, whose first-run setup [silently fails under Rosetta](docs/setup.md#why-asof-builds-its-own-db2-image).

**Then:** `python -m asof.setup`. It is safe to re-run: it generates the five users' passwords into `.env` (never printed), creates them as OS users in the Db2 container, installs the schema, seeds the fictional data, applies the grants, and proves as the runtime user that the as-of query works and writes are refused.

> **Use a database AsOf can own.** Setup revokes `CONNECT`, `CREATETAB`, `BINDADD` and `IMPLICIT_SCHEMA` from `PUBLIC` on the whole database, so on a database other applications share it would lock them out. Point `DB2_DATABASE` at a dedicated one.

Every detail, including remote Db2 and the Rosetta fix: [docs/setup.md](docs/setup.md).

---

## Configuration

> **Security warning:** `.env` holds real passwords and keys. It is gitignored: never commit it, and never put a real value in `.env.example`.

All settings come from `.env` ([.env.example](.env.example) lists every one, with no secret values). The ones that matter first:

| Setting | Meaning |
|---|---|
| `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USER`, `DB2_PASSWORD` | The Db2 database and its owner, used by setup only (the organizers' names) |
| `LLM_PROVIDER` | `openrouter` (default), `ollama`, `openai_compatible`, `watsonx`, or `replay` |
| `OPENROUTER_API_KEY` | The hosted model's key; the default model is `google/gemini-3.1-flash-lite` |
| `ASOF_AUTH` | `local` (default: localhost only, and the server refuses to listen beyond it) or `users` (a personal token with a role for every `/api/` call) |
| `ASOF_ROUTER_AGENT` | `auto` (default: the routing agent runs only with a model measured on the pinned routing split), `on` or `off` |

The other settings, IBM watsonx.ai, per-user API access and TLS: [docs/setup.md](docs/setup.md#configuration).

---

## Running the Project

```bash
python -m asof.db2check      # verify the Db2 features AsOf needs (owner account)
python -m asof.setup         # schema, users, seed data, grants, self-check
python src/main.py           # web UI at http://127.0.0.1:8000, API docs at /docs
python -m asof.demo          # optional: thirteen sample decisions, three of them drafts written to be held for the inbox (a live answer can be held too), then the backtest sample, so every screen has history
```

- **The console** (http://127.0.0.1:8000) and **the customer chat** (http://127.0.0.1:8000/chat), whose every reply AsOf checks ([every screen](docs/screenshots.md)).
- **The API:** JSON over HTTP; every route and a `curl` walkthrough of the Moffatt scenario are in [docs/api.md](docs/api.md). Integrations call `POST /api/gate` with their own draft and show the customer only `final_answer` (when `released` is false, that is just the holding reply), while `POST /api/assistant/ask` is the demo console's endpoint and deliberately returns the demo assistant's raw draft so the Playground and the chat's Behind-the-scenes view can show it struck through. In a LangChain app:

  ```python
  chain = RunnablePassthrough.assign(draft=assistant_prompt | llm | StrOutputParser()) | as_runnable()
  answer = chain.invoke({"question": "Can I get a bereavement fare after I travel?", "as_of": booking_date})
  ```

- **Agents:** [mcp_server/](mcp_server/) runs AsOf as an MCP tool for any agent.
- **Backtest:** upload a CSV of past conversations (or run the 20-row fictional sample) on the Backtest page or with `python -m asof.backtest`. Every row is checked for its customer's date and recorded on ledger channel `backtest`, and Db2 reports how many answers were wrong, by clause version, and the dollar gap where the data has one ([docs/backtest.md](docs/backtest.md)).

---

## Testing & Verification

```bash
pytest -q                                 # 1231 tests; 9 need an opt-in flag, 3 need TLS on and 1 the watsonx.ai extra (CI provides both)
pytest -q -m "not db2"                    # unit tests only, no database needed
python scripts/audit_deps.py && mypy      # dependency audit, type check
python -m asof.eval --split test          # the frozen airline split (needs a model)
```

Db2 tests run in throwaway schemas as the real least-privilege users ([what they cover, types and coverage](docs/testing.md)).

**The frozen evaluation.** Every test split was written and committed before its first run, and a test pins its SHA-256. Latest run on the hosted model (`google/gemini-3.1-flash-lite`, Sun 8 Nov):

| Frozen split | Cases | False allow | False block | Safe | Ideal | Citation | p50 |
|---|---|---|---|---|---|---|---|
| Airline `test` | 40 | **0 of 26** | 0 of 14 | 100% | 100% | 100% | 5.8 s |
| `escalation-test` (needless holds, blind) | 33 | **0 of 22** | 0 of 11 | 100% | 97.0% | 100% | 6.1 s |
| `situation-test3` (premises, blind) | 20 | **0 of 12** | 0 of 8 | 100% | 95.0% | 95.0% | 5.7 s |
| `list-test` (family and document lists, blind) | 16 | **0 of 9** | 1 of 7 | 93.8% | 87.5% | 100% | 5.2 s |
| `situation-test2` (premises) | 12 | **0 of 7** | 0 of 5 | 100% | 83.3% | 91.7% | 6.1 s |
| `situation-test` (premises) | 12 | **0 of 7** | 0 of 5 | 100% | 83.3% | 75.0% | 6.0 s |
| Bank `bank-test2` (blind) | 22 | **0 of 14** | 0 of 8 | 100% | 100% | 100% | 5.9 s |
| Bank `bank-test` | 26 | **0 of 16** | 0 of 10 | 100% | 96.2% | 100% | 5.5 s |
| `extractor-test` (attacks on the extractor, blind) | 10 | **0 of 8** | 0 of 2 | 100% | 100% | 100% | 6.0 s |

0 of 121 wrong drafts released, 1 of 70 correct drafts stopped (latest run, at `1df152e`, after the Db2 release rules). Four splits motivated a fix at some point and are not blind; the five that never did released **0 of 65** (95% upper bound about 4.6%). One earlier run released a draft; that gap is closed. Every run and miss: [docs/evaluation.md](docs/evaluation.md); routing: [docs/routing_eval.md](docs/routing_eval.md); intake: [docs/intake_eval.md](docs/intake_eval.md).

**Unseen domain.** Another AI (GPT) wrote a fictional railway's three-version refund policy and 40 cases meant to make AsOf fail; the policy went in through Policy intake, and the runner and metrics were committed before any case was read. First run: AsOf released **2 of 25** wrong drafts and held 2 of 15 correct ones, with 30 of 40 ideal outcomes; a plain LLM judge given only the latest version, on the same model, also released 2 of 25 but held 9 of 15 correct drafts and reached 6 of 40. AsOf's two releases were both at a fare-table band boundary. [docs/eval/unseen-results.md](docs/eval/unseen-results.md), intake: [docs/eval/unseen-intake.md](docs/eval/unseen-intake.md).

---

## Screenshots & Demo

| | |
|---|---|
| ![The playground: the Moffatt draft for a March booking contradicted by BRV-002 v1 and corrected from the clause](docs/screenshots/01-playground-moffatt-march.png) | ![Ledger replay: the row the decision used, what Db2 held at that moment, and what applies today](docs/screenshots/05-replay-after-change.png) |
| ![The specialist inbox: a held decision, its claims and the policy in force, and a reply that contradicts BRV-002 v1 refused](docs/screenshots/20-specialist-inbox.png) | ![The customer chat: a reply corrected before sending, with its source clause version](docs/screenshots/18-customer-chat-corrected.png) |

- **Live Demo Link:** https://136-108-251-170.sslip.io, a public demo for judging on one Google Cloud VM with Db2 12.1.5 Community Edition. The built-in scenarios replay recorded model outputs, with Db2 live; with live checks on (`ASOF_DEMO_LIVE`, [how](docs/public-demo.md)), a new question or draft is checked by OpenRouter within a daily cap Db2 holds and per-visitor limits, and refused with the reason when a live check cannot start. Every page, checks, previews and Ask the ledger work. Anything that would change policy or send something (applying a change, approving a draft, sending a reply or a notice) is refused with a "disabled in the public demo" message, and requests are rate-limited per address (`ASOF_PUBLIC_DEMO`, [api.py](src/asof/api.py)). To try those too, run `./quickstart.sh`.
- **Demo Video Link:** https://www.youtube.com/watch?v=mntehVWQn8E (2:58, with captions)

**Demo walkthrough:** the chat corrects the March bereavement answer from `BRV-002` v1; a policy PDF becomes checked versions; the pet-fee change finds the customer told the old fee and drafts a notice; the inbox answers a held decision; the ledger replays a decision. Every screen: [docs/screenshots.md](docs/screenshots.md).

---

## Known Limitations & Future Roadmap

- **Added on 10 Nov 2026** (each behind tests, CI on IBM's stock Db2 image): live checks on the [public demo](docs/public-demo.md) for new input, inside a daily cap Db2 holds (`DEMO_SPEND`, SQLSTATE 75097) and per-visitor limits, while the built-in scenarios replay; Db2 itself refuses to record a release unless every released claim cites a clause version in force on the date and quotes it ([release rules](docs/release-rules.md)); policy-change previews run in Db2 and roll back to a savepoint (`PREVIEW_POLICY_CHANGE`); row permissions per policy domain with a domain analyst and specialist each ([row permissions](docs/row-permissions.md)); a Db2 workload with thresholds that stops runaway AI-generated SQL ([WLM](docs/wlm.md)); backtest mode, which checks a CSV of past answers and reports what was wrong for its date ([backtest](docs/backtest.md)); attack chips on Ask the ledger that name the layer that stops each one; and an unseen domain written by another AI: on its railway refund policy AsOf made the right call on 30 of 40 drafts, a plain LLM judge on 6 of 40 (both let 2 of 25 wrong drafts through) ([results](docs/eval/unseen-results.md)).
- **Current Limitations:** a probabilistic judge, bounded by rule checks and verbatim quotes; the author's own evaluation on a fictional corpus; a single-node demo; about 6 s per check; a full-scan chain verification; one date per check and PDFs with a text layer only; and a read-mostly public demo. Each is below.
- **Next Steps:** incremental chain verification from a checkpoint, a larger routing split and a third document, the remaining frozen splits on watsonx.ai, and `db2audit` on the policy history ([full roadmap](docs/limitations.md)).

In detail:

- **The judge is probabilistic.** Rule checks and the verbatim-quote rule bound its mistakes; they do not remove them.
- **The evaluation is the author's,** on a fictional corpus: four of the nine frozen splits motivated a fix and are no longer blind.
- **Synthetic, single-node demo;** Db2 runs under emulation on Apple Silicon.
- **About 6 s per check** on the hosted model: fine before a reply is sent, not for token streaming.
- **`VERIFY_CHAIN` reads the whole chain:** [46 minutes at 1,000,000 decisions](docs/db2.md#verify_chain-at-1000000-decisions); receipt checks and evidence packs call it, so a large ledger needs checkpointed verification.
- **One date per check,** and policy intake reads PDFs with a text layer only (no OCR).
- **The public demo is read-mostly:** with `ASOF_PUBLIC_DEMO=true` it replays the built-in scenarios, checks new input live only within a daily cap Db2 holds and per-visitor limits (`ASOF_DEMO_LIVE`), and refuses policy changes and sends; everything else works, with Db2 live.

Every limit, what was done since the Round 1 proposal, and the full roadmap: [docs/limitations.md](docs/limitations.md). The temporal search pattern is also packaged as a module for IBM's db2-ai-cookbook ([cookbook/](cookbook/)).

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Jay Malhotra | [@JustJay7](https://github.com/JustJay7) | Everything: design, Db2, AI pipeline, UI |

- Case reference: *Moffatt v. Air Canada*, 2024 BCCRT 149 (BC Civil Resolution Tribunal, 14 February 2024).
- Licence: Apache 2.0 ([LICENSE](LICENSE)). Third-party software and its licences: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). IBM Db2 Community Edition is used under IBM's Community Edition licence.
