# CivicConnect – Smart Civic Complaint Management System

> **One-Line Pitch:** A full-stack municipal grievance platform where citizens report public infrastructure issues, IBM Db2 stores every complaint and audit record, and LangChain + IBM watsonx.ai automatically routes each ticket to the correct department with priority scoring.

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

Municipal corporations in India receive thousands of civic complaints daily — potholes, garbage overflow, water pipeline leaks, broken streetlights — through phone calls, emails, and paper forms. The process suffers from:

- **No centralised tracking**: Citizens have no visibility into complaint status once filed.
- **Manual triage**: Staff manually read each complaint and forward it to the right department, creating delays and mis-routing.
- **No audit trail**: There is no formal record of who acted on a complaint, when, and what note was left — making accountability impossible.
- **Siloed data**: Analytics on resolution times, category distribution, and department workload are unavailable in real time.

**Target audience:** Municipal commissioners (admin), department supervisors (staff), and ordinary citizens.

---

## Solution Overview

CivicConnect is a three-role civic platform:

| Role | Capability |
|---|---|
| **Citizen** | Submit complaints with photo, location, and description; track status in real time; rate resolution quality |
| **Staff** | View department-specific queue; update complaint status with notes; add resolution proof |
| **Admin** | Full complaint oversight; manage departments and categories; view analytics (by category, priority, resolution time) |

Core features:
1. **AI-Assisted Classification** — LangChain + IBM watsonx.ai classifies complaint title/description into one of 7 civic categories and assigns the correct municipal department.
2. **IBM Db2 Persistence** — Every complaint, status change, notification, and citizen feedback record is stored in IBM Db2 with a full relational schema.
3. **Real-Time Audit Trail** — Every status transition writes an immutable row to `COMPLAINT_UPDATES` with timestamp, actor, role, and note.
4. **Analytics Dashboard** — SQL aggregations over Db2 compute category-level complaint volume, average resolution hours, and department workload in real time.
5. **Firestore Sync** — A one-way `db2_sync.py` pipeline can migrate historical Firebase Firestore complaints into Db2 for unified analytics.

---

## IBM Db2 Integration

**Db2 Edition & Environment:** IBM Db2 Community Edition on Docker (`ibmcom/db2:11.5.9.0`) or IBM Db2 on Cloud.

**Connector / Driver Used:** `ibm_db` (native C driver, IBM-supported) + `ibm_db_dbi` (DB-API 2.0 wrapper for pandas/SQLAlchemy compatibility).

### Database Schema

```sql
-- 1. Municipal departments (seeded on startup)
CREATE TABLE CIVICCONNECT.DEPARTMENTS (
    DEPARTMENT_ID    VARCHAR(64)   NOT NULL PRIMARY KEY,
    NAME             VARCHAR(100)  NOT NULL,
    DESCRIPTION      VARCHAR(500),
    ACTIVE           SMALLINT      NOT NULL DEFAULT 1,
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Primary complaint store
CREATE TABLE CIVICCONNECT.COMPLAINTS (
    ID               VARCHAR(128)  NOT NULL PRIMARY KEY,
    COMPLAINT_ID     VARCHAR(64)   NOT NULL UNIQUE,   -- e.g. CCMS-2026-0001
    USER_ID          VARCHAR(128)  NOT NULL,
    CITIZEN_NAME     VARCHAR(100),
    CITIZEN_EMAIL    VARCHAR(150),
    TITLE            VARCHAR(200)  NOT NULL,
    DESCRIPTION      CLOB(32K),
    CATEGORY         VARCHAR(100),                    -- AI-assigned civic category
    DEPARTMENT_ID    VARCHAR(64),
    DEPARTMENT_NAME  VARCHAR(100),
    LOCATION         VARCHAR(255)  NOT NULL,
    LANDMARK         VARCHAR(255),
    IMAGE_URL        VARCHAR(1000),
    PRIORITY         VARCHAR(20)   NOT NULL DEFAULT 'medium',
    STATUS           VARCHAR(50)   NOT NULL DEFAULT 'Submitted',
    AI_SUMMARY       CLOB(8K),                        -- LangChain-generated summary
    AI_KEYWORDS      VARCHAR(500),
    REJECTION_REASON VARCHAR(1000),
    REOPEN_REASON    VARCHAR(1000),
    RESOLUTION_NOTES CLOB(8K),
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    RESOLVED_AT      TIMESTAMP
);

-- 3. Immutable audit log of every status transition
CREATE TABLE CIVICCONNECT.COMPLAINT_UPDATES (
    ID               VARCHAR(128)  NOT NULL PRIMARY KEY,
    COMPLAINT_ID     VARCHAR(64)   NOT NULL,
    PREVIOUS_STATUS  VARCHAR(50),
    NEW_STATUS       VARCHAR(50)   NOT NULL,
    UPDATED_BY       VARCHAR(100),
    UPDATED_BY_UID   VARCHAR(128),
    ROLE             VARCHAR(50),
    NOTE             CLOB(4K),
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. In-app notifications
CREATE TABLE CIVICCONNECT.NOTIFICATIONS ( ... );

-- 5. Citizen post-resolution ratings
CREATE TABLE CIVICCONNECT.CITIZEN_FEEDBACK ( ... );

-- 6. Pre-aggregated analytics snapshots
CREATE TABLE CIVICCONNECT.COMPLAINT_ANALYTICS ( ... );
```

### Key Queries & Operations

| Operation | SQL pattern |
|---|---|
| Complaint listing (latest-first) | `SELECT … FROM COMPLAINTS ORDER BY CREATED_AT DESC FETCH FIRST 500 ROWS ONLY` |
| Category analytics | `SELECT CATEGORY, COUNT(*), SUM(CASE WHEN STATUS='Resolved'…), AVG(TIMESTAMPDIFF(…))` |
| Department workload | `SELECT DEPARTMENT_NAME, COUNT(*) FROM COMPLAINTS WHERE STATUS NOT IN ('Resolved','Rejected') GROUP BY DEPARTMENT_NAME` |
| Status update + audit | Parameterised `UPDATE COMPLAINTS … SET STATUS = ?` followed by `INSERT INTO COMPLAINT_UPDATES …` in the same connection |
| Schema bootstrap | `CREATE TABLE IF NOT EXISTS` with explicit `CREATE SCHEMA CIVICCONNECT` guard |

---

## AI / LLM Architecture

**Framework:** LangChain (chain composition with `ChatPromptTemplate` + `JsonOutputParser`)

**Model Provider & Model:**
- Primary: IBM watsonx.ai `ibm/granite-13b-instruct-v2` via `langchain-ibm`
- Local fallback: `granite3.3:8b` via Ollama (`langchain-ollama`)
- Zero-dependency fallback: Built-in keyword heuristic (no LLM required)

**Workflow:**

```text
Citizen submits complaint title + description
        │
        ▼
FastAPI /api/ai/classify
        │
        ▼
LangChain chain: ChatPromptTemplate → WatsonxLLM → JsonOutputParser
        │
        ├── Returns: category, department, priority, keywords, summary
        │
        ▼
React frontend pre-fills form with AI suggestions
        │
        ▼
Citizen confirms and submits → FastAPI /api/complaints
        │
        ▼
ibm_db INSERT INTO CIVICCONNECT.COMPLAINTS  ←── IBM Db2
        │
        ▼
IBM Db2 COMPLAINT_UPDATES (audit row created)
```

The LangChain prompt is constrained to output strictly valid JSON matching the Db2 schema field names (`category`, `department`, `priority`), preventing hallucinated categories. If the LLM output fails JSON parsing or returns an unknown category, the response is sanitised against `CATEGORY_DEPARTMENT_MAP` before storage.

---

## Tech Stack

- **Backend / Core:** Python 3.11, FastAPI, ibm_db, ibm_db_dbi
- **Database:** IBM Db2 Community Edition (Docker) / IBM Db2 on Cloud
- **AI / LLM:** LangChain, langchain-ibm, IBM watsonx.ai Granite 13B
- **Frontend / UI:** React 19, TypeScript, TailwindCSS, Vite, Recharts
- **Auth:** Firebase Authentication (Google Sign-In) with role-based access
- **Libraries:** python-dotenv, uvicorn, pydantic, pytest

---

## Prerequisites

- **IBM Db2:** Docker Desktop (for local) OR IBM Db2 on Cloud credentials
- **Python** >= 3.11
- **Node.js** >= 18 (for React frontend)
- **IBM watsonx.ai API key** (or Ollama installed with `granite3.3:8b` for local fallback)
- **Docker** (for local Db2 container)

---

## Setup & Installation

### 1. Start IBM Db2 (local Docker)

```bash
docker run -itd --name civicconnect-db2 \
  -e LICENSE=accept \
  -e DB2INST1_PASSWORD=CivicPass1234 \
  -e DBNAME=SAMPLE \
  -p 50000:50000 \
  ibmcom/db2:11.5.9.0
```

Wait ~60 seconds for Db2 to initialise, then verify:
```bash
docker exec -it civicconnect-db2 bash -c "su - db2inst1 -c 'db2 connect to SAMPLE'"
```

### 2. Set up Python backend

```bash
cd submissions/civicconnect

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r src/backend/requirements.txt
```

### 3. Set up React frontend

```bash
# From the civicconnect root (or submissions/civicconnect/src/frontend)
npm install
```

---

## Configuration

Copy `.env.example` to `.env` inside `submissions/civicconnect/` and fill in credentials:

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Description |
|---|---|
| `DB2_HOST` | Db2 server hostname (default: `localhost`) |
| `DB2_PORT` | Db2 port (default: `50000`) |
| `DB2_DATABASE` | Database name (default: `SAMPLE`) |
| `DB2_USER` | Db2 username |
| `DB2_PASSWORD` | Db2 password |
| `WATSONX_API_KEY` | IBM watsonx.ai API key |
| `WATSONX_PROJECT_ID` | watsonx.ai Project ID |

> **Security:** Never commit `.env` to Git. The `.gitignore` already excludes it.

---

## Running the Project

### Start the Python/Db2 backend

```bash
cd submissions/civicconnect/src/backend

# Schema is auto-created on first run
uvicorn main:app --reload --port 8000
```

Backend API will be available at `http://localhost:8000`.

Test AI classification:
```bash
curl -X POST http://localhost:8000/api/ai/classify \
  -H "Content-Type: application/json" \
  -d '{"title": "Large pothole on MG Road", "description": "3 inch deep pothole causing accidents"}'
```

### Sync historical Firebase data to Db2 (optional)

```bash
python src/backend/db2_sync.py
```

### Start the React frontend

```bash
npm run dev
# App available at http://localhost:3000
```

The Vite dev server proxies `/api/*` calls to the FastAPI backend automatically.

---

## Testing & Verification

```bash
# From submissions/civicconnect/
pytest tests/ -v

# Run only unit tests (no Db2 connection required)
pytest tests/ -v -k "TestComplaintClassifier or TestAPIEndpoints"

# Run Db2 integration tests (requires live DB2_* env vars)
pytest tests/ -v -k "TestDb2Connection"
```

Expected output:
```
tests/test_db2_integration.py::TestComplaintClassifier::test_heuristic_pothole PASSED
tests/test_db2_integration.py::TestComplaintClassifier::test_heuristic_garbage PASSED
tests/test_db2_integration.py::TestComplaintClassifier::test_classify_returns_valid_keys PASSED
tests/test_db2_integration.py::TestComplaintClassifier::test_category_department_mapping PASSED
...
```

---

## Screenshots & Demo

- **Live Demo:** [https://civicconnect-ibm.vercel.app](https://civicconnect-ibm.vercel.app)
- **Demo Video:** _(attach link)_

### Demo Personas (no sign-up required)

| Role | Login | What you can do |
|---|---|---|
| Citizen | "Demo as Citizen" button | Submit complaint, track status, rate resolution |
| Admin | "Demo as Admin" button | View all complaints, manage departments, analytics |
| Staff | "Demo as Staff" button | Process department queue, update status |

---

## Known Limitations & Future Roadmap

**Current Limitations:**
- Firestore sync is one-directional (Firebase → Db2); changes made via Python API don't propagate back to Firestore.
- The `COMPLAINT_ANALYTICS` snapshot table requires a scheduled job (cron) to populate; currently only the live aggregation queries are used.
- Image storage uses Firebase Storage URLs; Db2 stores the URL reference only.

**Next Steps:**
- Vector embeddings of complaint descriptions stored in Db2 `VARBINARY` columns for semantic duplicate detection
- Replace Firestore as primary store with Db2-only mode (no Firebase dependency)
- Scheduled Db2 analytics snapshots for trend reporting
- LangChain `SQLDatabaseChain` for natural-language complaint search ("show me all urgent water issues in Ward 5")

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Kaushik Arya | [@kaushikarya06](https://github.com/kaushikarya06) | Full-Stack Developer, IBM Db2 Integration, AI Pipeline |
