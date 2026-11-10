# AnnaSetu

> **One-Line Pitch:** AnnaSetu connects surplus-food donors, NGOs and volunteers through a Db2-backed rescue workflow that screens safety evidence, estimates feasibility, reserves partner capacity and records verified handoffs.

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup and Installation](#setup-and-installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing and Verification](#testing-and-verification)
- [Demo](#demo)
- [Known Limitations](#known-limitations)
- [Team](#team)

## Problem Statement
Usable surplus food is time-sensitive, while donors, receiving NGOs and volunteers need to coordinate evidence, distance, capacity and custody. Ad hoc messages make it difficult to see whether a batch is eligible, whether capacity is still available, who confirmed each handoff, and how much food was actually distributed. AnnaSetu is an operational hackathon MVP for those participants; it is not a regulator, food-safety certifier or live dispatch service.

## Solution Overview
The React console calls a FastAPI service. FastAPI stores operational records directly in IBM Db2 and applies role and lifecycle checks before changing them. The workflow includes five innovations:

1. **Food Safety Passport:** batch-linked preparation and use-by times, storage and temperature observations, allergen declarations, human review and event history. Deterministic evidence screening returns `HOLD`, `FEASIBLE` or `INFEASIBLE`; it is an estimate and never official certification.
2. **Intelligent Rescue Feasibility:** evaluates remaining declared time against straight-line distance, a labelled travel-speed assumption, handoff allowance, category, storage, expiry and receiving capacity, with explicit rejection reasons.
3. **NGO Capacity Matching:** filters verified active receivers and transactionally reserves available kilograms. A batch can be split across multiple NGOs; conditional updates prevent over-allocation, and unallocated quantity is returned.
4. **Verified Handoffs:** donor pickup, assigned-volunteer delivery and receiving-NGO distribution each require the next workflow stage and its one-time code. The distribution checkpoint records actual kilograms received. Hash-chained, append-only audit events retain actor and timestamp evidence.
5. **AI Policy Copilot:** LangChain `langchain-db2` retrieves matching policy passages from the IBM Db2 vector store and returns their titles, excerpts and source URLs. The current MVP uses deterministic local feature-hash embeddings and no generative model; answers are retrieved guidance, not fabricated policy interpretation.

The dashboard metrics are queried from Db2 operational records. Demonstration accounts and test fixtures are labelled; never use them as real donation or beneficiary records.

## IBM Db2 Integration
- **Edition:** IBM Db2 Community Edition 12.1.5.0 in the supplied Docker Compose configuration.
- **Operational path:** FastAPI connects directly to the configured Db2 database via `ibm_db` / `ibm_db_dbi`. No SQLite, file database or operational fallback is used.
- **Data:** user and partner profiles, food batches, safety observations, human reviews, rescue allocations, workflow checkpoints, audit-chain head/events and policy documents are persisted in Db2. LangChain's `DB2VS` stores and searches policy vectors in the same Db2 instance.
- **Consistency:** allocation and capacity reservations, handoffs and audit appends use Db2 transactions. Database triggers reject updates/deletes to audit events and the immutable observation/review records.
- **Verification:** `/api/health` executes a Db2 query and identifies the active database; `/api/policy/status` reports vector readiness. See [schema and transaction notes](docs/DATABASE_SCHEMA.md), [setup](docs/DB2_SETUP.md) and the evidence-based [test report](docs/TEST_REPORT.md).

## AI / LLM Architecture
LangChain's `DB2VS` performs similarity search against the Db2 vector table. The application embeds documents and queries with a deterministic local feature-hashing implementation, retrieves up to three passages and returns each passage's stored source citation. There is no configured LLM or model provider in this build. The copilot therefore does not claim generative reasoning, and retrieved advice does not alter safety eligibility or authorize a handoff.

## Tech Stack
- **Backend:** Python 3.11/3.12, FastAPI, Pydantic, Uvicorn.
- **Database:** IBM Db2 Community Edition, `ibm-db` / `ibm_db_dbi`.
- **Vector retrieval:** LangChain Core and `langchain-db2` `DB2VS`.
- **Frontend:** React, Vite, JavaScript and CSS.
- **Local runtime:** Docker Desktop / Docker Compose, PowerShell on Windows.

## Prerequisites
- Windows 11, Docker Desktop with the WSL 2 Linux engine, and Docker Compose v2.
- 64-bit Python 3.11 or 3.12; Python 3.12 is used in the verified local setup.
- Node.js 20.19+ or 22.12+ with npm.
- At least 8 GB of memory available to the Db2 container; first initialization takes several minutes.

## Setup and Installation
From a clone of the hackathon repository, open PowerShell and run:

```powershell
Set-Location submissions\annasetu\src
Copy-Item ..\.env.example .env
notepad .env
```

Set local values for `DB2_PASSWORD`, a unique `JWT_SECRET` of at least 32 characters, and a private `DEMO_PASSWORD`. Keep `.env` local and do not put credentials in `VITE_*` variables. For a fresh Db2 installation, the Compose file initializes the configured `ANNASETU` database and the API initializes its schema. The existing demo dataset is seeded only when appropriate for an empty database. Do not point a production database at synthetic tests.

Install backend and frontend dependencies and start the database:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r api\requirements.txt
npm ci --prefix frontend
docker compose up -d db2
docker compose ps
```

Wait until the `annasetu-db2` container is healthy before starting the API. The persistent Docker volume is named `annasetu-db2-data`; do not use `docker compose down -v` if its data must be preserved.

## Configuration
The safe placeholder file is [`../.env.example`](.env.example) (submission root). For the Compose/API launcher, copy it to `src\.env`. Variables and their roles are listed in [Db2 setup](docs/DB2_SETUP.md). Use a private local password; this package contains no `.env` or live credential. The frontend API base defaults to `http://127.0.0.1:8010/api` and must contain no secrets.

## Running the Project
With Docker healthy and dependencies installed, from `submissions\annasetu\src`:

```powershell
.\start-annasetu.ps1
```

The launcher targets `ANNASETU`, starts/reuses the existing Db2 container, FastAPI at `127.0.0.1:8010`, and Vite at `127.0.0.1:5175`; it writes local logs under `src\logs\`. Open `http://127.0.0.1:5175`. Verify the live Db2 connection and vector readiness at `http://127.0.0.1:8010/api/health`; interactive API docs are at `http://127.0.0.1:8010/docs`.

For an isolated integration suite, use a separate local Db2 database named `ANNATEST`, set `DB2_NAME=ANNATEST` and a private QA `DEMO_PASSWORD` in a local ignored `src\.env`, then run the opt-in command documented in [Db2 setup](docs/DB2_SETUP.md). The tests refuse to run against `ANNASETU` and leave clearly labelled synthetic QA rows in `ANNATEST`.

## Testing and Verification
The recorded local verification is summarized in [TEST_REPORT.md](docs/TEST_REPORT.md). It distinguishes the default suite's skipped live-Db2 cases from the opt-in live run; skipped tests are not counted as passes. To run the ordinary suite and production frontend build from `src`:

```powershell
.\.venv\Scripts\python.exe -m pytest api\tests -q -rs
npm --prefix frontend run build
```

The live integration command and required `ANNATEST` guard are documented in [DB2_SETUP.md](docs/DB2_SETUP.md). Confirm the active database at `/api/health`; an HTTP response alone does not verify Db2 connectivity.

## Demo
See the [five-minute judge walkthrough](docs/DEMO_GUIDE.md). Use only a dedicated QA database and records prefixed `SYNTHETIC QA |`. Demo account email addresses are listed in the application README; their local password is the private configured `DEMO_PASSWORD`. Do not publish or include that password in the submission.

## Known Limitations
- Rescue travel time is a deterministic straight-line estimate, not live routing, road distance, traffic or dispatch.
- Safety logic screens declared evidence and timing; it does not inspect food, replace a qualified human assessment, or issue official certification.
- OTP delivery is manual; the application does not send SMS automatically.
- The policy assistant performs cited Db2 retrieval without a generative model. Retrieved source passages are informational, not an official interpretation.
- This is a local hackathon MVP, not a high-availability production deployment. Authentication, secrets, retention and operational monitoring need deployment-specific review.

## Documentation
- [Architecture](architecture.md)
- [Db2 setup and environment](docs/DB2_SETUP.md)
- [API reference](docs/API_REFERENCE.md)
- [Database schema](docs/DATABASE_SCHEMA.md)
- [Test report](docs/TEST_REPORT.md)
- [Demo guide](docs/DEMO_GUIDE.md)

## Team
| Name | GitHub | Contribution |
|---|---|---|
| Rajat | [@rajatrajput2402](https://github.com/rajatrajput2402) | Project lead and full-stack / Db2 integration |

## Distribution Terms

No general open-source license is supplied with this project. No additional redistribution or reuse rights are granted by this submission; third-party components remain under their respective licenses. The submission is provided for hackathon review. See the upstream repository's Code of Conduct for participation expectations.
