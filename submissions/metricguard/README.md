# MetricGuard — Trustworthy AI Analytics on IBM Db2

> **Don't just trust the number. Verify the evidence.**
> Ask a business question in plain English. A Meta Muse Spark model turns it into a typed plan, deterministic code compiles read-only Db2 SQL from approved metric definitions, and the result is reconciled and written to an audit log in Db2.

![MetricGuard answering "Which region had the highest net revenue in Q2 2026?" with Meta muse-spark-1.3, verified on IBM Db2](docs/screenshots/desktop-03-top-region.png)

*A real run: Meta `muse-spark-1.3` planned it, the compiler wrote the SQL, Db2 12.1 ran it as a SELECT-only account, 11 of 11 checks passed.*

**▶ [Watch the 2:33 demo](https://youtu.be/8SpNxsvE32c)** (real screen recording: live Db2, live Meta API calls; narration is a synthetic voice).

| If you have... | Do this |
|---|---|
| 1 minute | Watch the video, then read [Problem Statement](#problem-statement) and [IBM Db2 Integration](#ibm-db2-integration) |
| 5 minutes, no Db2 and no API key | `cd src && make setup && make test` runs 156 unit tests with no database. Browse [`architecture.md`](architecture.md) and `docs/screenshots/` |
| 30 minutes, Docker or Colima | Follow [Setup](#setup--installation) through `make db-verify` to see Db2 reject writes and reproduce the $781,330.86 trap. Use `AI_PROVIDER=demo` (labelled, no AI) or a Meta key for the AI planner |

| Judging criterion | Where to look |
|---|---|
| IBM Db2 integration and depth | [IBM Db2 Integration](#ibm-db2-integration), `src/db/schema/`, `make db-verify` output in `src/evidence/` |
| Innovation and impact | [Problem Statement](#problem-statement): four reproducible naive-SQL traps |
| Architecture and AI integration | [AI / LLM Architecture](#ai--llm-architecture), [`architecture.md`](architecture.md) |
| Reproducibility and code quality | [Testing & Verification](#testing--verification): 173 backend + 55 frontend tests, clean-copy run |
| Documentation and presentation | This README, `docs/screenshots/`, the video |

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

A text-to-SQL system can return **valid SQL that runs without error and still reports the wrong business number.** Nothing fails, so nobody looks.

Here is one such case from this project's own data (Jan–Jun 2026, seeded dataset, `gross_revenue`):

| Query | Result |
|---|---:|
| Governed metric | **$667,622.16** |
| Plausible naive join: `ORDERS ⨝ ORDER_ITEMS ⨝ REFUNDS` on `ORDER_ID` | **$781,330.86** |
| Difference | +$113,708.70 (+17.0%) |

Both statements execute successfully on IBM Db2. The naive one is wrong because an order with *k* refund rows is repeated *k* times, and every order line on it is summed *k* times. The numbers come from `make db-verify` (`TRAP-01` in [`src/evidence/DB2_VERIFICATION.md`](src/evidence/DB2_VERIFICATION.md)) and are reproducible on the seeded data. The naive SQL is hand-written to mirror a common pitfall; we did not measure how often a model would write it.

Three more traps are checked by the same suite on the same data (`make db-verify`, governed value vs naive SQL):

| Trap | Governed | Naive | Why it is wrong |
|---|---:|---:|---|
| Net revenue ignoring order and refund status | $615,704.13 | $664,765.50 | counts cancelled orders and non-processed refunds |
| Shipping added after a line join | $667,622.16 | $672,368.22 | order-level shipping is summed once per line |
| January order count with `BETWEEN '2026-01-01' AND '2026-01-31'` | 394 | 383 | drops orders after midnight on Jan 31 |

**Who it is for:** analysts and data teams who let non-experts ask questions of a Db2 warehouse and need to know *which definition* produced a number, *which SQL* ran, and *whether it reconciles*.

**Why existing tooling falls short:** execution success says nothing about business correctness. Most text-to-SQL tools let the model write the SQL and the metric definition at the same time.

## Solution Overview

MetricGuard splits the job so the model never writes SQL.

| Step | Who does it | What happens |
|---|---|---|
| 1. Screen | deterministic code | Write intent, raw SQL, relative dates and bare "revenue" are caught first |
| 2. Plan | **LangChain + Meta Muse Spark 1.3** | Fills a closed, typed `PlannerOutput` (metrics, dimensions, filters, dates, sort, limit) |
| 3. Validate | deterministic code | Pydantic schema, approved-metric registry, SHA-256 definition hash checked against Db2 |
| 4. Compile | deterministic code | One parameterized `SELECT` built from the approved definitions; refunds are pre-aggregated per order line before the join |
| 5. Guard | deterministic code | Single `SELECT`, allow-listed tables, every value is a `?` marker |
| 6. Execute | IBM Db2 | Runs as `MGREADER`, a SELECT-only account |
| 7. Verify | Db2 + code | Group sums reconciled to an independent control query, completeness and NULL checks |
| 8. Audit | IBM Db2 | Question, plan, SQL, checks and timings stored through `MGAUDIT` (INSERT + SELECT only) |

Every answer shows the SQL, bound parameters, metric definitions with their hash status, 11 numbered checks, and who planned it. Vague or unsafe questions are **not** answered: "revenue last quarter" returns two clarifying options, and "delete every order" returns `BLOCKED` with *No SQL was executed*.

What the status `VERIFIED` means: approved definitions, governed read-only SQL and reconciled totals. It does **not** certify that the underlying data is correct, and MetricGuard does not claim to catch every wrong query.

## IBM Db2 Integration

| | |
|---|---|
| **Edition & environment** | IBM Db2 Community Edition **12.1.5.0** (`icr.io/db2_community/db2`), Docker, run on Apple Silicon through Colima with QEMU amd64 emulation. IBM Cloud Db2 is supported by configuration but was not tested |
| **Connector** | `ibm_db` 3.3.0 (native arm64 client), called from FastAPI. LangChain is used only for the model call, not for Db2 |
| **Business tables** | `ORDERS`, `ORDER_ITEMS`, `PRODUCTS`, `REFUNDS`: a deterministic seeded dataset (2,924 orders, 6,540 order lines, 40 products, 1,032 refunds; seed `20260107`) |
| **Metric definitions** | `METRIC_DEFINITIONS` holds 6 approved metrics with owner, grain, lifecycle status and a **SHA-256 hash**. The API refuses to run a metric whose runtime definition differs from the Db2 row (`REGISTRY_DRIFT`) |
| **Constraints** | `CHECK` constraints on status, region, channel, amounts and discounts; a composite foreign key ties each refund to a line of the *same* order; the data-quality suite finds 0 violations |
| **Queries** | CTE analytics with `DECIMAL` arithmetic, half-open date intervals, parameter markers for every value, 11 supporting indexes, `RUNSTATS` through `SYSPROC.ADMIN_CMD` |
| **Least privilege** | `MGREADER` has SELECT on the business and registry tables only; `MGAUDIT` has INSERT + SELECT on `QUERY_AUDIT_LOG` only and cannot read business data or update or delete audit rows. `make db-verify` proves it: Db2 rejects the writes with SQLSTATE 42501 |
| **Audit storage** | `QUERY_AUDIT_LOG` is append-only for the application: request, status, plan JSON, SQL, parameters, check results, planner provider and model, timings |

**Verify the Db2 integration** (about 1 minute, after setup): `make db-verify` writes `src/evidence/DB2_VERIFICATION.md` and exits non-zero on any failure. It runs 7 golden queries against an independent Python oracle (exact decimal equality), 4 naive-SQL traps, 15 reconciliations and the privilege checks. Last recorded run: PASS, 0 failures.

DDL: [`src/db/schema/`](src/db/schema/). Seed generator and oracle: [`src/backend/metricguard/seed/`](src/backend/metricguard/seed/).

## AI / LLM Architecture

- **Framework:** LangChain (`langchain-core`, `ChatOpenAI` with `with_structured_output(..., method="json_schema", strict=True)`).
- **Model:** **Meta Muse Spark 1.3** (`muse-spark-1.3`) through the Meta Model API, `reasoning_effort=low`. Select it with `AI_PROVIDER=meta` and `MODEL_API_KEY`.
- **What the model does:** returns a `PlannerOutput` that Pydantic and the registry validate. It cannot name tables or columns, and no model text ever reaches SQL.
- **No silent fallback:** if the Meta API fails, the API returns an error. It never swaps in the rule-based planner.
- **Two other modes, both labelled in the UI and the audit row:** `demo` (a rule-based planner, shown as "Demo planner") for offline use, and an optional Anthropic adapter that was only tested with mocks.
- **Prompt injection:** policy screens and the registry sit around the model. Of 12 hostile or screened prompts sent to the model alone, 10 were classified correctly and 2 were planned anyway; the deterministic layers still blocked both. This is evidence for two layers holding on these prompts, not a claim of universal protection.

Details: [`docs/AI_PROVIDER_CONFIGURATION.md`](docs/AI_PROVIDER_CONFIGURATION.md), [`architecture.md`](architecture.md).

## Tech Stack

- **Backend / core:** Python 3.12, FastAPI, Pydantic, Uvicorn
- **Database:** IBM Db2 Community Edition 12.1.5.0, `ibm_db` 3.3.0
- **AI:** LangChain 1.7, Meta Model API (`muse-spark-1.3`)
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts
- **Tooling:** Docker Compose, Colima (QEMU), `uv`, pytest, Vitest, Playwright

## Prerequisites

- macOS on Apple Silicon with Homebrew (the tested setup), about 10 GB free disk and 12 GB RAM for the VM
- `colima`, `docker`, `docker-compose`, `uv`, Node.js 20 or newer with `npm`
- A Meta Model API key for the AI planner ([dev.meta.ai](https://dev.meta.ai)); without one you can still run the labelled demo planner
- On x86_64 Linux you can skip Colima and run `docker compose` directly. This path was **not tested** here

```bash
brew install colima docker docker-compose uv
```

## Setup & Installation

All commands run from this submission's `src/` folder.

```bash
cd submissions/metricguard/src

make setup          # creates .venv (Python 3.12), installs the backend, copies .env.example to .env
# edit .env: set DB2_PASSWORD, DB2_READER_PASSWORD, DB2_AUDIT_PASSWORD (any local passwords)

make colima-up      # Colima VM with QEMU amd64 emulation, Rosetta OFF (see note below)
make db-up          # pulls IBM Db2 Community Edition, waits for "Setup has completed" (several minutes the first time)
make db-reader      # creates the SELECT-only account (local container only)
make db-audit-user  # creates the append-only audit account (local container only)
make db-init        # schema, seeded data, metric registry, RUNSTATS, grants (idempotent)
make db-verify      # live Db2 verification suite
```

```bash
cd frontend && npm ci
```

**Apple Silicon note.** IBM ships the Db2 image for `linux/amd64` only, so it runs under emulation. Use **QEMU, not Rosetta**: Rosetta's binfmt handler drops `argv[0]`, the image's `su - db2inst1` login shells never load `db2profile`, and `CREATE DATABASE` fails silently even though the log says "Setup has completed" (ADR-011). `make colima-up` already sets `--vz-rosetta=false`. If a shell exports `PYTHONHOME`, the Makefile clears it.

**Known emulation fix-up.** Under QEMU the file `sqllib/adm/.fenced` is missing, which makes fenced routines fail with SQL1646N. `make db-up` runs `scripts/db2_post_setup.sh`, which restores it. It does not change the application.

## Configuration

`cp .env.example .env` (done by `make setup`). `src/.env.example` is identical to the root `.env.example`.

| Variable | Meaning |
|---|---|
| `DB2_*`, `DB2_READER_*`, `DB2_AUDIT_*` | Local Db2 connection and the two least-privilege accounts (placeholders only) |
| `AI_PROVIDER` | `meta` (default here), `demo`, `anthropic`, or `auto` |
| `MODEL_API_KEY` | Meta Model API key. Keep it empty in Git; set it only in your local `.env` |
| `META_MODEL`, `META_BASE_URL` | `muse-spark-1.3`, `https://api.meta.ai/v1` |
| `META_REASONING_EFFORT` | `low` (recommended). Accepts `minimal, low, medium, high, xhigh, max` |
| `PLANNER_TIMEOUT_SECONDS`, `PLANNER_MAX_RETRIES` | 30 s per attempt, 1 retry (worst case about 61 s, under the browser's 90 s limit) |

> **Security:** never commit `.env`. The repository contains placeholders only. The validator and the packaging script both refuse any `.env` file.

## Running the Project

```bash
# terminal 1, from src/
make api                                   # FastAPI on http://localhost:8000/docs

# terminal 2
cd frontend && npm run build && npm run start
# open http://localhost:3000   (use localhost, not 127.0.0.1: CORS allows localhost:3000)
```

Check it: `curl -s localhost:8000/api/health | jq '.status, .planner'` should show `"ok"` and provider `meta`.

**Guided demo (the buttons under the question box):**

| # | Button | Expected result |
|---|---|---|
| 1 | Net revenue, June 2026 | VERIFIED **$111,093.25**, 10 passed, 1 skipped by design |
| 2 | Top region, Q2 2026 | VERIFIED **NA · $138,679.66**, 11 of 11 |
| 2b | Net revenue by region, Q2 | VERIFIED, total $325,270.33, four regions reconcile |
| 2c | Revenue last quarter | AMBIGUOUS: choose Net or Gross revenue |
| 3 | Unsafe instruction | BLOCKED `WRITE_INTENT`, no SQL, audit row stored |

Planning takes roughly 2–5 s per question with `low`. Meta latency varies.

## Testing & Verification

All tests live next to the code in `src/backend/tests/` and `src/frontend/tests/`; see [`tests/README.md`](tests/README.md).

```bash
cd submissions/metricguard/src
make test           # unit tests, no database or API key needed
make test-db2       # unit tests + live Db2 integration tests (needs the running Db2)
make eval           # 25-case benchmark through FastAPI + live Db2 with the rule-based planner
make db-verify      # Db2 verification suite
cd frontend && npm run typecheck && npm run lint && npm test
```

Optional and paid: `make test-live-llm` and `make eval-llm` call the real Meta API. Run them once, not in a loop.

**Recorded results (2026-11-07, see [`docs/FINAL_QA_REPORT.md`](docs/FINAL_QA_REPORT.md)):**

| Suite | Result |
|---|---|
| Backend pytest (live Db2) | 173 passed, 2 skipped (the 2 opt-in live-LLM tests) |
| Rule-based benchmark (no AI) | 25 / 25 |
| `make db-verify` | PASS, 0 failures |
| Meta `muse-spark-1.3` benchmark (37 cases, 25 + 12 unseen) | 37 / 37 outcomes; 20 / 20 executed results equal the oracle |
| Meta live end-to-end (4 questions) | 4 / 4 expected statuses; 2 / 2 executed results equal the oracle |
| Frontend Vitest / Playwright | 55 / 55 and 24 / 24 |
| TypeScript, ESLint, production build | clean |

**Read this honestly:** 37 cases are a smoke-sized sample, not a measure of general model accuracy. The rule-based 25 / 25 shows the governed pipeline works; it says nothing about any model. Meta failure modes (401, 429, 5xx, timeouts, malformed output) are covered with mock-provider tests, not live. Method and raw data: [`src/evaluation/benchmark-results.md`](src/evaluation/benchmark-results.md).

## Screenshots & Demo

All screenshots are from the current build with real Meta inference and live Db2.

| Verified answer | Ambiguous question | Unsafe request blocked |
|---|---|---|
| ![Verified](docs/screenshots/desktop-02-verified.png) | ![Ambiguous](docs/screenshots/desktop-04-ambiguous.png) | ![Blocked](docs/screenshots/desktop-05-blocked-unsafe.png) |

| Audit history stored in Db2 | Audit detail | Mobile (390 px) |
|---|---|---|
| ![Audit list](docs/screenshots/desktop-07-audit-list.png) | ![Audit detail](docs/screenshots/desktop-08-audit-detail.png) | ![Mobile](docs/screenshots/mobile-03-chart.png) |

More: `desktop-01-home`, `desktop-06-by-region-chart`, `tablet-01-chart`, and three `mock-*` images that show error states with stubbed HTTP (labelled as mocks).

## Known Limitations & Future Roadmap

**Limitations**
- **Latency:** nearly all time is the Meta call (about 2–5 s for clear questions, up to about 15 s for vague ones). Db2, verification and audit add under 0.15 s.
- **Ambiguity is model-dependent:** "Show our best-performing region." returned AMBIGUOUS once and BLOCKED on later runs. Both are safe, and it is excluded from the guided demo.
- **Audit history:** the audit endpoint returned HTTP 503 intermittently during development. It was not reproduced in 100 probe requests and the root cause is unknown. The UI shows a Retry button and a sanitized log line now records the SQLSTATE.
- **Evaluation scope:** 37 live cases and one seeded synthetic dataset. No confidence interval, no human study.
- **Scope of metrics:** six approved metrics, four dimensions. Anything else is refused, not guessed.
- **Environment:** single-host demo. CORS allows `http://localhost:3000` only, one Db2 connection per request, no pooling. Tested on macOS Apple Silicon only. Not production-certified.
- **Db2 features:** relational tables, constraints, indexes, CTEs and DECIMAL arithmetic. It does **not** use Db2 vector search, RAG or Db2 AI features.

**Next steps:** more metrics and a metric-approval workflow in Db2, connection pooling, streaming planner progress, a broader evaluation with a labelled question set.

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Jaehyup Shin | [@shin0343](https://github.com/shin0343) | Individual participant: design, Db2 schema and verification, backend, AI planner, frontend |

Submitted as an individual (solo) entry.

Built with assistance from AI coding tools (Claude Code). Licensed under Apache-2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)); dependency licenses are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). IBM Db2 Community Edition is pulled from IBM's registry and used under IBM's license terms.
