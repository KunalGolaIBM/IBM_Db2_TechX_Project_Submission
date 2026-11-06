# AsOf

> **What did the policy say on that date, and what did your AI tell the customer?**
> AsOf checks each policy claim in an AI assistant's answer against the policy version in force on the customer's date, stops answers that contradict it, and keeps a tamper-evident Db2 record of what was said and why.

**Built on IBM Db2 12.1 for Db2Hack 2026.** Bitemporal tables, native `VECTOR` search, SQL/JSON, in-database SHA-256, triggers, SQL PL and least-privilege users, with LangChain and the official `langchain-db2` connector.

> **Fictional data.** "Aurelia Air" and every policy, FAQ and help-centre answer in this repository are invented for the demo. They are modelled on the kind of policy at issue in *Moffatt v. Air Canada* and describe no real airline.

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
- [Evaluation](#evaluation)
- [Testing & Verification](#testing--verification)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement

In *Moffatt v. Air Canada*, 2024 BCCRT 149, Air Canada's website chatbot told a grieving customer he could apply for a bereavement fare after travelling. The airline's own policy page said the opposite. The tribunal held the airline liable for negligent misrepresentation: the company owns what its chatbot says, and correct information on another page is no defence.

Every company running a customer-facing assistant has the same exposure, and it gets worse over time:

- **Policies change.** Refund windows, fees and eligibility rules get new versions with new effective dates. Assistants, cached FAQ answers and help articles drift out of date.
- **The right answer depends on the date.** A customer who booked in March and one who booked in June can be under different rules for the same question.
- **Disputes come later.** When a complaint arrives months on, the company usually cannot show which policy version the answer relied on, or what its systems held at that moment.

**Who it is for:** CX platform, compliance and legal-operations teams at airlines, banks, insurers and telcos, the organisations that already run Db2 as their system of record.

**Why existing tooling falls short:** guardrail products check an answer against retrieved text, but have no notion of which policy version applied on which date, cannot replay what the database knew at the time, and cannot tell you which past answers a policy change has made stale. See [How AsOf compares](#how-asof-compares).

---

## Solution Overview

Given an AI-generated answer and the date that matters (booking or travel date, supplied by the calling system, never guessed by the model), AsOf finds the applicable policy version, flags claims that contradict it, stops unsupported answers from going out, and keeps the evidence needed to review that decision later.

1. **As-of policy lookup.** One Db2 query returns the clauses in force on a date, ranked by meaning: `FOR BUSINESS_TIME AS OF` plus `VECTOR_DISTANCE`.
2. **Claim check.** An LLM extracts atomic policy claims; one batched LLM call judges all of them against the retrieved clauses, quoting the deciding text; deterministic rules then compare numbers, deadlines and eligibility flags with each clause's JSON rule parameters.
3. **Decision.** PASS with citations, CORRECTED (rewritten from clause text and re-checked), or ESCALATED to a person. Any error, timeout or invalid model output fails closed.
4. **Audit ledger.** Append-only, hash-chained Db2 rows, replayable with `FOR SYSTEM_TIME AS OF`.
5. **Change impact.** After a policy change, find past answers and published help-centre answers whose cited version is no longer the one in force for their date.

### Build status

| Capability | Status |
|---|---|
| Db2 schema, least-privilege users, seed data, as-of + vector retrieval, replay query | Done, tested |
| LLM layer: provider switch, strict schemas, batched judge, hard deadlines | Done, tested |
| Claim pipeline, deterministic rule checks, redaction, hash-chained ledger, API, LangChain runnable | Done, tested (incl. live LLM) |
| Change impact, web UI, analytics views, evaluation results | Next |

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 Community Edition 12.1.5.0 in Docker (`icr.io/db2_community/db2:12.1.5.0`), database `TESTDB`. Native `VECTOR` needs 12.1.2 or later.
- **Connector / Driver Used:** `ibm_db` / `ibm_db_dbi` for every query (parameter markers only), and the official LangChain integration `langchain-db2` (`DB2VS`) for the demo assistant's FAQ store.
- **Database Schema / Data Models:** schema `ASOF`, defined in [src/asof/sql/](src/asof/sql/).
  - `POLICY_CLAUSE`: bitemporal. `BUSINESS_TIME` is when a clause version applies to customers, `SYSTEM_TIME` is when the database held it. `PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS)` makes overlapping versions impossible. Each row has a `VECTOR(384, FLOAT32)` embedding and `RULE_JSON` parameters guarded by a `JSON_EXISTS` check constraint. Old rows move to `POLICY_CLAUSE_HIST` automatically.
  - `ANSWER_LEDGER`, `CLAIM_CITATION`, `CHAIN_HEAD`: one row per decision and one per claim per check. Written only by the SQL PL procedure `APPEND_LEDGER`, which locks `CHAIN_HEAD`, assigns the next gapless `LEDGER_ID`, computes the row's SHA-256 in Db2 (`HASH(..., 2)`) over the previous row's hash and every field, and shreds the claim citations out of the hashed verdict JSON with `JSON_TABLE`, all in one atomic call. `BEFORE UPDATE` / `BEFORE DELETE` triggers reject any change with SQLSTATE 75001, even for the owner, and `VERIFY_CHAIN` recomputes the whole chain to catch anyone who drops the triggers first.
  - `PUBLISHED_ANSWER`: help-centre answers pinned to the clause version they were written from.
  - `FAQ_KB`: the naive demo assistant's knowledge base, created and searched by `DB2VS`.
- **Key Queries & Operations:** the core query, from [src/asof/retriever.py](src/asof/retriever.py):

  ```sql
  SELECT c.CLAUSE_ID, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, c.BUS_START, c.BUS_END,
         VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
  FROM ASOF.POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c      -- the customer's date
  WHERE c.DOC_ID = ?
  ORDER BY DIST FETCH FIRST ? ROWS ONLY
  ```

  For replay, `FOR SYSTEM_TIME AS OF ?` goes in front of `FOR BUSINESS_TIME AS OF ?`: the same question, answered from what the database held at an earlier moment. Each citation also records the clause row's `SYS_START`, so replay can show the exact row a decision used, what the database held for that customer date at decision time, and what applies today.
- **Least privilege:** the runtime user `asofapp` holds `SELECT` on the tables it reads and `EXECUTE` on `APPEND_LEDGER` and `VERIFY_CHAIN`, nothing else: no `INSERT`, `UPDATE`, `DELETE` or DDL anywhere. The procedures run with the owner's authority. Setup revokes Db2's default `PUBLIC` database privileges.

### Check that your Db2 supports all of it: one command

[src/asof/db2check.py](src/asof/db2check.py) exercises every Db2 feature AsOf depends on in a throwaway schema, prints PASS or FAIL for each, removes everything it created, and exits non-zero on any failure:

```bash
python -m asof.db2check
```

```
PASS  Db2 version supports VECTOR: DB2/LINUXX8664 12.01.0500
PASS  Bitemporal table with VECTOR column: BUSINESS_TIME + SYSTEM_TIME periods, VECTOR(384, FLOAT32), JSON check, WITHOUT OVERLAPS key
PASS  FOR PORTION OF BUSINESS_TIME update: one row became v1 [2026-01-01, 2026-05-01) and v2 [2026-05-01, open)
PASS  As-of date + vector search (March): 2026-03-10 -> v1, nearest first (cosine distance 0.0000)
PASS  Replay + vector search: SYSTEM_TIME + BUSINESS_TIME + VECTOR_DISTANCE in one query
PASS  SHA-256 in SQL (Unicode): HASH(expr, 2) equals Python SHA-256 for UTF-8 text
PASS  Hash chain via stored procedure: each row hash covers the previous row hash, computed inside Db2
PASS  Trigger blocks UPDATE: UPDATE rejected with SQLSTATE 75001
...
26/26 Db2 feature checks passed. Schema ASOF_CHECK was removed.
```

---

## AI / LLM Architecture

- **Framework:** LangChain. Structured output into strict Pydantic schemas, a custom `BaseRetriever` over the as-of query, and `langchain-db2`'s `DB2VS` vector store.
- **Model Provider & Model:**
  - Default: **OpenRouter** with `google/gemini-3.1-flash-lite`, chosen by a probe of 10 models on AsOf's own prompts (format validity, verdict and clause accuracy, verbatim quoting, prompt injection, latency). Results and reasoning are in [architecture.md](architecture.md#design-decisions).
  - No-key path: **Ollama** with `qwen2.5:7b-instruct`, running locally.
  - Any other OpenAI-compatible endpoint via `LLM_PROVIDER=openai_compatible`.
- **RAG / Tool Calling Workflow** ([src/asof/gate.py](src/asof/gate.py)):
  1. **Redact** emails, phone numbers, card numbers and booking references from the question and draft.
  2. **Extract** atomic policy claims (one LLM call, strict schema, at most 8).
  3. **Retrieve**, per claim, the clause versions in force on the customer's date (Db2 query above).
  4. **Judge** all claims in one LLM call. Claims and clauses go in as delimited, escaped data blocks that cannot close their tag or pose as instructions. The model must cite a clause that was retrieved and quote its deciding text **verbatim**, or the verdict drops to NOT_COVERED.
  5. **Rule check** ([src/asof/rules.py](src/asof/rules.py)): code compares amounts, percentages, durations, weights, counts and key permissions (for example `retroactive_allowed`) with the clause's `RULE_JSON`, and routes delay claims to the tier that applies. A mismatch forces CONTRADICTED even when the model said SUPPORTED; it can never turn a contradiction into a pass.
  6. **Decide.** All supported: PASS with policy references. Any contradiction: rewrite strictly from the cited clauses, re-check the rewrite from step 2, and release it only if every claim is supported. Claims no clause covers, timeouts, invalid output or any error: ESCALATED with a holding reply.
  7. **Record** the decision with `APPEND_LEDGER`. If the ledger cannot record it, the answer is withheld (HTTP 503).

  Every LLM call has a hard deadline and an output-token cap and returns a validated object or raises.

---

## Tech Stack
- **Backend / Core:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings
- **Database:** IBM Db2 12.1.5.0 Community Edition (Docker), `ibm_db`
- **AI:** LangChain, `langchain-db2`, `langchain-openai` (OpenRouter), `langchain-ollama`, `sentence-transformers/all-MiniLM-L6-v2` (local, CPU)
- **Frontend / UI:** server-rendered web UI (in progress)
- **Libraries & Tools:** Docker Compose, pytest

---

## Prerequisites
- **Python 3.11 or 3.12**
- **Docker** with Compose v2 (Docker Desktop, or Colima on macOS), and about 10 GB of free disk for the Db2 image and data
- **An LLM:** an [OpenRouter](https://openrouter.ai/keys) API key, or [Ollama](https://ollama.com) with `ollama pull qwen2.5:7b-instruct`
- **Apple Silicon:** the Db2 image is Intel-only and runs under emulation. With Colima: `colima start --cpu 4 --memory 6 --vz-rosetta`. Use the provided Compose file (named volume, not a bind mount: Db2 cannot create its home directories on a macOS-shared folder).

---

## Setup & Installation

```bash
cd submissions/asof

# 1. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e . --no-deps

# 2. Configuration: set DB2_ADMIN_PASSWORD, and OPENROUTER_API_KEY (or LLM_PROVIDER=ollama)
cp .env.example .env

# 3. Db2 (first start took about 6 minutes on an M-series MacBook Air under Rosetta)
docker compose up -d --wait db2

# 4. Schema, least-privilege users, seed data, grants, self-check
python -m asof.setup
```

`python -m asof.setup` is safe to re-run. It generates passwords for the two least-privilege users into `.env` (never printed), creates them inside the Db2 container, installs the schema, seeds the fictional data, applies grants, and finishes by proving, as the runtime user, that the as-of query works and that writes are refused.

### Why AsOf builds its own Db2 image

[docker-compose.yml](docker-compose.yml) builds a thin layer on top of IBM's image ([docker/db2/Dockerfile](docker/db2/Dockerfile)) because the stock image **silently fails its first-run setup on Apple Silicon**:

- Under Rosetta (Colima `--vz-rosetta`; the emulator is registered without the "preserve argv[0]" flag), `su - db2inst1 -c ...` does not start a login shell, so `db2profile` is never loaded.
- IBM's setup script then fails every `db2` command with "command not found", never starts the engine or creates `TESTDB`, and still prints **"Setup has completed"**.

The derived image fixes this and two follow-on problems. Each change is a no-op on a regular x86 Linux host:

1. **Login-shell wrapper** for the Db2 users, so `db2profile` always loads.
2. **Platform pinned in the Dockerfile** (`FROM --platform=linux/amd64`), because Docker's classic builder, used when the buildx plugin is absent, ignores Compose's `platform:` and looks for an arm64 image that IBM does not publish.
3. **Stale setup marker cleared on start**, so the healthcheck cannot pass on a marker from the previous boot while setup is re-running. `docker compose up --wait` returns only once setup has finished **and** `TESTDB` accepts connections.

### Using an existing Db2 instead

If you already run Db2 12.1.2+ (for example from the IBM Db2 VS Code extension), skip step 3. Point `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE` and `DB2_ADMIN_PASSWORD` at it and set `DB2_CONTAINER` to its container name, so setup can create the two OS users there. If setup cannot reach the container, it prints the exact `useradd` commands to run on the Db2 host.

---

## Configuration

All settings are environment variables, read from `.env` ([.env.example](.env.example) lists every one with dummy values). `.env` is gitignored.

| Variable | Purpose |
|---|---|
| `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_CONTAINER` | Where Db2 runs |
| `DB2_ADMIN_PASSWORD` | Owner account, used only by setup and the feature check |
| `ASOF_APP_PASSWORD`, `ASOF_EDITOR_PASSWORD` | Least-privilege users; generated by setup if empty |
| `LLM_PROVIDER` | `openrouter` (default), `ollama`, or `openai_compatible` |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Hosted model (default `google/gemini-3.1-flash-lite`) |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local model (default `qwen2.5:7b-instruct`) |
| `LLM_TIMEOUT_S`, `LLM_MAX_OUTPUT_TOKENS` | Hard per-call deadline and output cap; the gate fails closed when hit. Use `LLM_TIMEOUT_S=120` for Ollama on a laptop. |

> **Security:** never commit `.env`. Before every commit, `python scripts/check_secrets.py` compares the staged changes against the real values in your local `.env` and against common key patterns, and fails without printing anything secret.

---

## Running the Project

```bash
python -m asof.db2check      # verify the Db2 features AsOf needs (owner account)
python -m asof.setup         # schema, users, seed data, grants, self-check
python -m asof.api           # API on http://127.0.0.1:8000 (interactive docs at /docs)
```

**The Moffatt scenario, end to end.** Ask the naive demo assistant (which answers from a stale FAQ) and let AsOf check its draft, once for a March booking and once for a June booking:

```bash
curl -s -X POST localhost:8000/api/assistant/ask -H 'content-type: application/json' \
  -d '{"question": "My grandmother just died. Can I get the bereavement fare after I travel?", "as_of_date": "2026-03-10"}'
```

A real run with `gemini-3.1-flash-lite` (abridged):

| | March booking (`2026-03-10`) | June booking (`2026-06-02`) |
|---|---|---|
| Assistant draft | "You can request a bereavement discount retroactively ... within 90 days of your ticket issuance." | same promise |
| Retroactive claim | CONTRADICTED by **BRV-002 v1** (judge and rule check agree) | SUPPORTED by **BRV-002 v2** |
| Decision | **CORRECTED**: "Bereavement fares must be requested before travel begins. A bereavement fare cannot be applied retroactively once any part of the journey has been flown, and no refund of the fare difference is available after travel. Policy references: BRV-002 v1 (in effect from 2026-01-01)." | **PASS** with **BRV-002 v2** references when the draft is accurate, **CORRECTED** when it overstates the refund |
| In 5 consecutive live runs | CORRECTED 2 of 2 | PASS 2 of 3, CORRECTED 1 of 3 |

Other stale FAQ entries are caught the same way: a July question about the first bag fee is corrected from $35 to $40 (BAG-001 v2), and "you can transfer your ticket for a $50 name change fee" is corrected from CHG-004.

**Resetting the ledger for a demo (demo only).** The ledger is append-only by design: no user, not even the owner, can update or delete its rows. To start a recording from ledger entry 1, setup can drop and recreate the three ledger tables as the owner, which deletes every recorded decision and starts a new hash chain. Policy clauses, their history and the help-centre answers are kept. Never do this outside a demo.

```bash
python -m asof.setup --reset-ledger      # asks you to type "reset"; add --yes to skip
```

`python -m asof.setup --reset` goes further and rebuilds the whole schema from the seed data, including undoing policy changes made in the demo.

**API**

| Endpoint | Purpose |
|---|---|
| `POST /api/gate` | Check a draft: `question`, `draft_answer`, `as_of_date`, optional `channel`. Returns the decision, final answer, and per-claim verdicts with clause versions and quotes. |
| `POST /api/assistant/ask` | Ask the naive demo assistant, then check its draft |
| `GET /api/ledger`, `GET /api/ledger/{id}` | Recorded decisions and their claim citations |
| `GET /api/ledger/{id}/replay` | The clause rows a decision used, what Db2 held at that moment, and what applies today |
| `GET /api/chain/verify` | Run `VERIFY_CHAIN` over the whole ledger |
| `GET /healthz` | Db2 connectivity and the configured model |

**Drop it into an existing LangChain app**

```python
from asof import as_runnable

chain = assistant_prompt | llm | StrOutputParser() | as_runnable(as_of=booking_date)
answer = chain.invoke({"question": "Can I get a bereavement fare after I travel?"})
```

The runnable takes the assistant's draft and returns the checked answer, and every decision lands in the Db2 ledger.

---

## Evaluation

`python -m asof.eval --split test` runs the gate on 40 labelled cases and writes [docs/eval_results.md](docs/eval_results.md), with every per-case decision recorded in [docs/eval/](docs/eval/). The 40 test cases are new scenarios, none used while building or choosing the model. They were committed (`81b5b69`) before the first run and are frozen: a unit test pins their SHA-256 and the runner refuses to run them if it changes. The 20-case dev split holds the scenarios used while debugging. Each case is labelled with the decision it should get and the clause version its key claim must be checked against.

**Frozen test split, `google/gemini-3.1-flash-lite` via OpenRouter** (40 cases: 14 correct drafts, 26 wrong for their date):

| Metric | Result |
|---|---|
| **False-allow rate** (wrong drafts released as PASS) | **0.0%** (0 of 26) |
| False-block rate (correct drafts rewritten or escalated) | 7.1% (1 of 14) |
| Safe decisions | 97.5% |
| Ideal decisions | 92.5% |
| Citation accuracy (key claim checked against the right version) | 100% |
| Latency p50 / p90 | 5.9 s / 8.1 s, 3.6 LLM calls per case |

Categories: supported 8, contradicted numbers 6, contradicted eligibility 6, date boundaries (day before and day of a version change) 5, not covered 5, relative and implied counts against limits 4, multi-claim 3, prompt injection 3. Per-category numbers are in the report.

What went wrong, from the recorded runs (left unfixed so the numbers stay honest):

- **T33 (the false block):** the extractor turned the customer's own situation ("the delay was within our control") into a policy claim. No clause covers it, so a correct answer was escalated.
- **T31 and T36 (escalated instead of corrected):** the rewrite was right, but in the re-check the judge paraphrased its quote, the verbatim-quote rule downgraded that claim to NOT_COVERED, and the correction was held back. The strict quote rule trades some corrections for never trusting an unquoted verdict.

On the dev split the same model scored 0% false allow, 0% false block and 95% ideal decisions.

---

## Testing & Verification

```bash
pytest -q                                 # 182 tests: unit tests plus Db2 integration tests
pytest -q -m "not db2"                    # unit tests only, no database needed
ASOF_RUN_LLM_TESTS=1 pytest -q -m llm     # 4 live tests against the configured LLM (spends API calls)
```

Integration tests install everything into a throwaway `ASOF_TEST` schema, connect as the real least-privilege user, and drop the schema afterwards. They skip automatically when Db2 is unreachable. They cover:

- the same claim reaching `BRV-002` v1 for 2026-03-10 and v2 for 2026-06-02, and both sides of the 2026-04-30 / 2026-05-01 boundary
- replay with `FOR SYSTEM_TIME AS OF` after a policy change
- Db2 rejecting overlapping clause versions and malformed rule JSON
- the runtime user being refused `UPDATE`, `DELETE`, `INSERT`, `CREATE TABLE` and `DROP`, on policy and ledger tables alike
- SQL injection strings returning nothing instead of executing, and stored as plain text in the ledger
- the ledger: gapless IDs and linked hashes under three concurrent writers; triggers stopping even the owner; `VERIFY_CHAIN` catching an owner who drops a trigger and edits a row, edits a citation, or deletes the last row
- every gate decision path with a scripted LLM, including a manipulated judge that says SUPPORTED with a real quote (the rule check still overrides it), an invented quote, a clause not in force, timeouts and a ledger outage
- 61 rule-checker tests, mostly realistic claims against the real corpus rules, in both directions (real contradictions caught, situational numbers left alone)
- API validation (byte limits, dates, allow-listed `doc_id`, control characters, unknown fields), body cap, rate limit and security headers

> **Note on the submission validator:** `scripts/validate_submission.py` flags any `.env` or `*.pem` file under the folder, including your local `.env` and certificate files inside `.venv`. Neither is committed. Run the validator from a clean checkout to see what a reviewer sees.

---

## How AsOf compares

AsOf does not claim to have invented checking AI answers against policy.

- **Amazon Bedrock Automated Reasoning checks** already validate responses against policies, suggest corrections and log results.
- **NVIDIA NeMo Guardrails** fact-checking rails score an answer against retrieved text.
- **IBM watsonx.governance** measures RAG quality (faithfulness and related metrics).

What AsOf adds is time, inside the customer's own system of record: effective-dated policy versions (what was true on date X), bitemporal replay (what the database held at moment T), and change impact on past answers and published content. It is open source, runs locally, and keeps all of it in Db2.

---

## Known Limitations & Future Roadmap
- **Current Limitations:**
  - The LLM judge is probabilistic. Deterministic rule checks and the verbatim-quote rule bound its mistakes, but do not remove them.
  - All data is synthetic, and the demo is single-node.
  - Under emulation on Apple Silicon, Db2 is slower, and local Ollama models are slow while Db2 is busy.
  - On Apple Silicon under Rosetta, Db2 *fenced* routines crash, so AsOf deliberately uses only built-in SQL, triggers and SQL PL, which run inside the engine.
- **Next Steps:** see [Build status](#build-status).

---

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Jay Malhotra | [@JustJay7](https://github.com/JustJay7) | Everything: design, Db2, AI pipeline, UI |

- Case reference: *Moffatt v. Air Canada*, 2024 BCCRT 149 (BC Civil Resolution Tribunal, 14 February 2024).
- Licence: Apache 2.0 ([LICENSE](LICENSE)). Third-party software and its licences: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). IBM Db2 Community Edition is used under IBM's Community Edition licence.
