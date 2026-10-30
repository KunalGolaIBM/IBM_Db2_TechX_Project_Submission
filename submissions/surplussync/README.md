# Predictive Community Food Rescue

> **One-Line Pitch:** SurplusSync helps donors route surplus food to eligible community recipients through explainable feasibility checks, rescue planning, and volunteer coordination. SQLite runs the operational workflow; an optional IBM Db2 and LangChain path analyzes a privacy-minimized snapshot.

---

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
Community food donors and recipient organizations need a practical way to coordinate perishable surplus before pickup deadlines. A candidate can appear suitable while lacking capacity, accepting a different food category, being unavailable, or having too little time for pickup. Human food-handling and local-rule checks also cannot be inferred safely by software.

SurplusSync is intended for donors, recipient organizations, volunteers, and administrators coordinating local rescue workflows. Its rules make candidate eligibility and blockers visible; they do not replace responsible human safety checks.

## Solution Overview
The React interface calls a FastAPI service that stores operational records in SQLite. For each listing, the backend evaluates recipient availability, accepted food categories, configured capacity after active reservations, simulated travel time against the pickup deadline, and required human-entered safety verification. It ranks feasible candidates and saves candidate results and rejection explanations in a rescue plan. Its risk assessment is a transparent weighted rules score, not a trained predictive model.

An eligible donor can propose a rescue to a recipient. The recipient accepts or rejects; rejection records a reason and allows a later proposal to another candidate. The rescue lifecycle records status transitions and notes. Donors/admins can assign an approved volunteer; volunteers can view assigned work and update collection/delivery progress. Volunteer schedules are not live-tracked, and travel estimates are fictional static demo values.

## IBM Db2 Integration
- **Db2 Edition & Environment:** Optional IBM Db2 instance reachable from the backend. The repository does not establish that a live Db2 instance is connected; `/api/ai/db2/status` reports connection state at runtime.
- **Connector / Driver Used:** IBM `ibm_db` Python driver (`ibm-db` requirement), using parameterized driver statements. No SQLAlchemy connector is used.
- **Data flow:** `POST /api/ai/db2/analyze` first reads a listing and its latest saved `candidate_evaluations` plus recipient attributes from operational SQLite. It whitelists a compact listing snapshot and candidate evaluation data, excluding account identifiers, contacts, and verifier names. It then writes that snapshot to Db2, reads it back, and verifies that the retrieved records match before using them as analysis context. Db2 errors return an explicit 503; this workflow has no silent SQLite fallback for the Db2 analysis.
- **Db2 storage:** The integration creates `SURPLUSSYNC_AI_RECORDS` in the current schema if absent. Its columns are `RECORD_TYPE VARCHAR(32)`, `RECORD_KEY VARCHAR(120)`, `RECORD_JSON CLOB(1M)`, and `UPDATED_AT TIMESTAMP`; `(RECORD_TYPE, RECORD_KEY)` is the primary key. Record types are `LISTING`, `CANDIDATE`, and, when no saved evaluations exist, `ASSESSMENT`. A listing analysis replaces that listing's keyed snapshot transactionally, upserts each record, and validates read-back. This is a JSON snapshot table, not a vector store.
- **Status endpoint:** Authenticated, approved donor/admin: `GET /api/ai/db2/status`. Returns `configured`, `connected`, `watsonx_configured`, database and table information (or missing configuration/error class). It does not claim connectivity unless the live `VALUES 1` check succeeds.
- **Analysis endpoint:** Authenticated, approved donor/admin: `POST /api/ai/db2/analyze` with `{ "listing_id": 1, "question": "..." }`. Donors may analyze only their own listing. Success includes `db2_write_read_verified`, retrieved count, candidate count, and recommendation generation mode. Missing Db2 configuration, unavailable Db2, or unavailable LangChain returns an explicit 503.
- **Connection configuration:** Supply `DB2_CONNECTION_STRING`, or all of `DB2_DATABASE`, `DB2_HOSTNAME`, `DB2_PORT`, `DB2_UID`, and `DB2_PWD`. `DB2_SECURITY` must be `SSL`; direct connection strings are required to use/receive `SECURITY=SSL`.

## AI / LLM Architecture (if applicable)
- **Framework:** LangChain Core prompt/runnable composition; `langchain-ibm` `ChatWatsonx` when credentials are complete.
- **Provider/model:** The code defaults to IBM watsonx.ai model ID `ibm/granite-3-3-8b-instruct` and URL `https://us-south.ml.cloud.ibm.com`, overridable with `WATSONX_MODEL_ID` and `WATSONX_URL`. Watsonx credentials are not configured in the supplied example, so generation is not asserted as working.
- **Grounding and fallback:** After Db2 snapshot read-back, the context is serialized into a prompt. With both `WATSONX_API_KEY` (or legacy `WATSONX_APIKEY`) and `WATSONX_PROJECT_ID`, the LangChain watsonx chain attempts a response. Otherwise, a LangChain `RunnableLambda` produces a deterministic rules-only summary from retrieved Db2 records. If model invocation fails, it logs only the exception class and also uses that rules-only summary. The prompt explicitly avoids food-safety certification claims. Neither path changes operational SQLite state.

## Tech Stack
- **Backend / Core:** Python, FastAPI, Pydantic
- **Database:** SQLite is the operational source of truth; IBM Db2 is an optional analysis snapshot store.
- **Frontend / UI:** React 18 and Vite
- **Libraries & Tools:** `ibm_db`, LangChain Core, `langchain-ibm`, `python-dotenv`

## Prerequisites
- Python 3.10 or newer and pip
- Node.js and npm
- Optional: network-reachable IBM Db2 with a user/schema permitted to create and update `SURPLUSSYNC_AI_RECORDS`
- Optional for generated watsonx explanations: IBM watsonx API key and project ID

## Setup & Installation

```bash
cd submissions/surplussync/src
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
npm install --prefix frontend
```

## Configuration
The source loads an optional local `.env` from `submissions/surplussync/src/`. The submission-level `.env.example` lists the IBM Db2 and watsonx variables actually read by the integration. Copy it to that source directory as `.env` only when configuring a private environment; use secret storage for deployed credentials. Blank values are placeholders, not credentials. Do not commit `.env`.

`DB2_CONNECTION_STRING` takes precedence over the individual Db2 fields. Configure either it or the five required individual fields; the connection must use SSL. For watsonx generation, set `WATSONX_API_KEY` (or compatibility alias `WATSONX_APIKEY`) and `WATSONX_PROJECT_ID`. `WATSONX_URL` and `WATSONX_MODEL_ID` have code defaults. Db2 analysis remains unavailable until Db2 is configured and reachable.

Other source settings include `SURPLUSSYNC_DB_PATH` (SQLite file), `SURPLUSSYNC_CORS_ORIGINS`, SMTP/reset-mail settings, and demo/upload controls. See `src/.env.example` for their exact names. No email address or credential is required by this submission's IBM integration.

## Running the Project
From `submissions/surplussync/src`:

```bash
uvicorn backend.main:app --reload
npm run dev
```

The API listens at `http://127.0.0.1:8000`; Vite serves the frontend and proxies `/api` to it. `GET /api/health` reports API health, not Db2 connectivity. Use the authenticated Db2 status endpoint to check the optional integration.

## Testing & Verification
From `submissions/surplussync/src`, run `pytest backend/tests`. Tests cover feasibility rules, API workflows, and Db2/LangChain behavior using test doubles; mocked tests do not establish live Db2 or watsonx connectivity.

## Screenshots & Demo
- **Live Demo Link:** Not supplied
- **Demo Video Link:** Not supplied
- No screenshot asset is included in this submission directory.

## Known Limitations & Future Roadmap
- Db2 is optional and runtime connection status must be checked; current credentials are not supplied here.
- Watsonx credentials are not configured; generated responses cannot be claimed as verified. Rules-only mode is available only when Db2 snapshot retrieval and LangChain are operational.
- Matching uses configured data and simulated travel minutes, not live routing. Volunteer availability is not a live schedule.
- Human-entered verification gates operational feasibility; the application does not certify food safety.
- The rules-based risk score is explainable but is not a trained predictive model.

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Rajat Rajput | [@rajatrajput2402](https://github.com/rajatrajput2402) | Creator; SurplusSync implementation |

**Team:** HyperX
