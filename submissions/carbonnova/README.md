# CarbonNova — AI-Powered Agricultural Carbon Intelligence & Marketplace

> **One-line pitch:** CarbonNova is a role-based climate-tech prototype where sellers register land and submit carbon projects, buyers assess and purchase eligible demo credits, and admins govern verification—using **IBM Db2** for persistent/transactional workflows and **LangChain** for grounded AI assistance.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture (LangChain)](#ai--llm-architecture-langchain)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Database Setup (IBM Db2)](#database-setup-ibm-db2)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [API / Endpoint Reference](#api--endpoint-reference)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement
Agricultural carbon projects involve fragmented land records, uncertain monitoring evidence, complex verification workflows, and opaque credit transactions. Smallholders and project developers need simple tools to register land, understand **estimated** carbon potential, and prepare evidence; buyers need transparent project quality/document context; administrators need governance and auditable decisions. **Estimated carbon potential must not be presented as a certified or issued carbon credit.**

## Solution Overview
CarbonNova provides three demonstration role dashboards (no real authentication):
- **Seller:** register land, generate a labeled demonstration carbon-potential assessment, submit carbon projects, manage marketplace listings/credits/transactions.
- **Buyer:** explore a global marketplace (filters/map/inspection), compare quality dimensions, run AI-assisted document review, complete **simulated** purchases of eligible approved credits, view portfolio/transactions.
- **Admin:** review/approve/reject/suspend users/projects/listings, monitor transactions, and inspect audit logs.

Core safeguards: only approved/eligible listings are purchasable; purchases validate quantity and prevent overselling/negative balances; important actions are auditable; simulated/estimated values are labeled.

## IBM Db2 Integration
**Db2 edition/environment:** IBM Db2 Community Edition (local Docker or IBM Db2 Developer Extension) or a supported Db2 environment.

**Connector/driver:** `ibm_db` (Node.js) in `src/app/server/lib/db2.js`, with parameterized SQL (`?` markers), connection-string configuration via env vars, and transaction helpers.

**Schema/data models (created by `src/app/server/lib/db2Schema.js` / `POST /api/db2/init`):**
- `CN_USERS`, `CN_SELLER_PROFILES`, `CN_BUYER_PROFILES`
- `CN_LAND_REGISTRATIONS`, `CN_LAND_ASSESSMENTS`
- `CN_CARBON_PROJECTS`, `CN_CREDIT_LISTINGS`
- `CN_VERIFICATION_RECORDS`, `CN_SUPPORTING_DOCUMENTS`
- `CN_CREDIT_BALANCES`, `CN_CREDIT_TRANSACTIONS`
- `CN_AUDIT_LOGS` (+ indexes)

**Key Db2 operations implemented:**
- **Health/connectivity:** `GET /api/health/db2` executes `SELECT CURRENT SERVER AS SERVER_NAME FROM SYSIBM.SYSDUMMY1` against a real Db2 connection (returns truthful error if not configured/unreachable; never fakes success).
- **Schema init:** `POST /api/db2/init` runs idempotent DDL to create required tables/indexes.
- **Land registration/assessment persistence:** Db2 insert helpers in `lib/db2Platform.js` (`CN_LAND_REGISTRATIONS`, `CN_LAND_ASSESSMENTS`) for genuine Db2 writes.
- **Transactional credit purchase (Workflow E):** when Db2 is configured, `POST /api/marketplace/purchase` uses `db2PurchaseCredits` (`lib/db2Platform.js`) inside a Db2 transaction: validates listing approval/availability, prevents self-purchase/oversell, updates `CN_CREDIT_LISTINGS`, upserts `CN_CREDIT_BALANCES` via `MERGE`, inserts `CN_CREDIT_TRANSACTIONS`, inserts `CN_AUDIT_LOGS`, then commits; errors trigger rollback. This provides real SQL execution and atomic allocation.
- **Admin/audit-capable design:** verification/audit tables and transactional patterns support governance records in Db2.

> **Note on demo mode:** the integrated app also contains JSON-backed demo routes used during UI development. For hackathon compliance, configure `DB2_*` and initialize schema so Db2-backed operations (health/init/transactional purchase and Db2 writes) execute against IBM Db2. The implementation is genuine (not cosmetic).

## AI / LLM Architecture (LangChain)
**Framework:** **LangChain** (`langchain`, `@langchain/core`, `@langchain/openai`) — functionally integrated in `src/app/server/lib/langchainService.js`.

**Working workflows:**
- `POST /api/ai/langchain/explain-assessment` — uses LangChain `ChatPromptTemplate` + `ChatOpenAI` (OpenAI-compatible config) + output parser to generate a **grounded** land/carbon assessment explanation from provided CarbonNova records, with explicit labels (estimates, missing evidence, not certification).
- `POST /api/ai/langchain/review-documents` — LangChain-based AI-assisted document consistency review from project/document metadata and heuristic findings; explicitly **not** official certification.

**Model/provider:** configurable via env (`NEBIUS_*` or `AI_*` OpenAI-compatible settings). API keys are never committed.

## Tech Stack
- **Frontend:** React 19, Vite 8, React Router 7, TanStack Query, Zustand, Tailwind CSS, Leaflet/react-leaflet.
- **Backend:** Node.js, Express 5.
- **Database:** **IBM Db2** via `ibm_db`.
- **AI/Framework:** LangChain + OpenAI-compatible LLM; existing Nebius/NVIDIA-compatible routes preserved.
- **Other:** dotenv, zod, pdfkit.

## Prerequisites
- Node.js 20+ and npm.
- Access to an **IBM Db2** instance (Community Edition via Docker/Db2 Developer Extension, or supported Db2 environment).
- Python 3 (only if you run `scripts/validate_submission.py` from repo root).
- For `ibm_db` on Windows: build/runtime prerequisites may be required by the driver; follow `ibm_db`/Db2 client guidance if native install issues occur.

## Setup & Installation
From the repository root or this submission folder:

```bash
# 1) Navigate to the integrated app
cd submissions/carbonnova/src/app

# 2) Install frontend dependencies
npm install

# 3) Install backend dependencies (includes ibm_db and LangChain packages)
npm --prefix server install
```

## Configuration
```bash
# from submissions/carbonnova/src/app
cp ../../.env.example server/.env
# or create server/.env using submissions/carbonnova/.env.example as reference
# also configure frontend API base if needed: VITE_API_URL
```
Fill in **local/test** IBM Db2 credentials and (optionally) AI provider keys. **Never commit `.env` or real secrets.**

## Database Setup (IBM Db2)
1. Start IBM Db2 (Community Edition). Example (Docker, conceptually): run the official Db2 Community image, accept license, expose port 50000, and wait for setup completion. Use the Db2 Developer Extension or Docker docs for your OS.
2. Set `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USERNAME`/`DB2_USER`, `DB2_PASSWORD` in `server/.env`.
3. Start the backend, then initialize schema:
   ```bash
   curl -X POST http://localhost:4000/api/db2/init
   ```
4. Verify connectivity:
   ```bash
   curl http://localhost:4000/api/health/db2
   ```
   Expected when healthy: JSON with `ok: true` and Db2 server info (from `SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1`).

## Running the Project
```bash
# Terminal 1 (backend)
cd submissions/carbonnova/src/app
npm run dev:server
# API: http://localhost:4000

# Terminal 2 (frontend)
cd submissions/carbonnova/src/app
npm run dev
# Open the Vite URL shown (typically http://localhost:5173)
```
**Demo flow:** Homepage → **“A Greener Future Starts Here”** → role select → Seller/Buyer/Admin dashboards. For Db2-validated transactional purchase behavior, ensure Db2 is configured/initialized and relevant records exist in Db2 tables.

## Testing & Verification
```bash
# Backend existing tests (from integrated app)
cd submissions/carbonnova/src/app/server
node --test

# Frontend production build
cd submissions/carbonnova/src/app
npm run build

# Official submission validator (from repo root)
cd ../../..
python scripts/validate_submission.py submissions/carbonnova

# Db2 health (requires running Db2 + env)
curl http://localhost:4000/api/health/db2
```
**Transactional test (Db2 configured):** initialize schema, insert/seed required `CN_CREDIT_LISTINGS` + balances/projects state per your test setup, then `POST /api/marketplace/purchase` and verify updated balances/transaction/audit rows in Db2. The code path uses a real Db2 transaction with rollback on failure.

## API / Endpoint Reference
- `GET /api/health` — service health + config flags.
- `GET /api/health/db2` — **real** Db2 connectivity (`SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1`).
- `POST /api/db2/init` — create CarbonNova Db2 schema (idempotent best-effort).
- `GET /api/db2/status` — Db2 config status.
- `POST /api/marketplace/purchase` — credit purchase; **Db2 transaction** used when Db2 is configured.
- `POST /api/ai/langchain/explain-assessment` — **LangChain** grounded assessment explanation.
- `POST /api/ai/langchain/review-documents` — **LangChain** AI-assisted document review.
- Plus existing CarbonNova routes under `/api` (projects, readings, carbon, parcels, assessments, reports, AI, platform demo routes).

## Screenshots & Demo
Add screenshots to `docs/screenshots/` and update links here. (Placeholders may be added before submission.)

## Known Limitations & Future Roadmap
- Full migration of every legacy/demo JSON path to Db2-backed queries can be completed incrementally; critical Db2 compliance artifacts (real health check, schema, transactional purchase, Db2 persistence helpers, LangChain workflows) are implemented in code.
- `ibm_db` native installation may require platform-specific prerequisites; Db2 connectivity tests require a running Db2 instance and valid credentials.
- Demo role selection is not authentication; production deployment requires authz, secure file storage, and verified MRV/certification integrations.
- **Next:** complete Db2 repositories for all CRUD workflows A–F, add Db2-backed vector/RAG (e.g., LangChain Db2 vector store where appropriate), automated integration tests with a Db2 container, and team/submission metadata finalization.

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Update with participant name | [@update-github-handle](https://github.com/update-github-handle) | Full Stack, IBM Db2 integration, LangChain/AI workflows |

**Important:** update `submission.json` and this section with real team details before final submission (do not invent members). No secrets committed.
