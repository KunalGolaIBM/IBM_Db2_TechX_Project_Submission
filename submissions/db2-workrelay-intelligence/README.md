# Db2 WorkRelay Intelligence

> **One-Line Pitch:** An operational incident management and knowledge retrieval application that uses IBM Db2 to persist operational incidents, maintain immutable lifecycle audit logs, and provide deterministic retrieval of historical operational runbooks.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [Operational Runbook Knowledge Retrieval](#operational-runbook-knowledge-retrieval)
- [Implementation Status](#implementation-status)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [API Endpoints](#api-endpoints)
- [Testing & Verification](#testing--verification)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement
In modern microservice and hybrid-cloud enterprise environments, operational incidents (such as database connection exhaustion, deadlock spikes, memory saturation, and transaction log saturation) occur under urgent conditions.

Existing incident management approaches suffer from two major flaws:
1. **Unverifiable Black-Box AI Actions:** Unconstrained LLM agents executing commands directly in infrastructure create serious compliance and reliability risks when hallucinating remediation steps.
2. **Ephemeral or Scattered Incident History:** Incident post-mortems and diagnostic traces are fragmented across chat threads, ticket comments, and log dumps instead of residing in a unified, queryable enterprise relational database with strict transactional integrity.

---

## Solution Overview
**Db2 WorkRelay Intelligence** solves these challenges by combining deterministic reliability with automated operational intelligence:
- **FastAPI Core:** Exposes a high-throughput REST API for incident intake, lifecycle querying, and status updates.
- **IBM Db2 Persistence:** Acts as the authoritative single source of truth for all incident records, automated diagnostic logs, and multi-step remediation actions using native `ibm_db`.
- **Operational Runbook Retrieval:** Deterministic symptom and keyword overlap matching over operational post-mortems and runbooks to immediately recommend verified recovery steps for incoming symptoms.
- **Deterministic Workflows:** The system isolates triage and runbook recommendation from execution (controlled state machine transitioning through `CLASSIFYING -> INVESTIGATING -> REMEDIATING -> VERIFYING -> RESOLVED`).

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** IBM Db2 Community Edition (Docker / Cloud / On-Premises).
- **Connector / Driver Used:** Native `ibm_db` driver and `ibm_db_dbi` with parameterized query execution (`?` positional bindings).
- **Database Schema / Data Models:**
  - `incidents`: Central incident state (ID, title, description, service, severity, status, workflow, resolution).
  - `incident_events`: Chronological lifecycle audit trail with foreign key cascade to `incidents`.
  - `incident_actions`: Diagnostic telemetry and remediation actions with execution timestamps.
  - `incident_knowledge_docs`: Curated knowledge catalog of operational post-mortems and runbooks.
- **Schema Management:**
  - Native IBM Db2 DDL defined in `src/app/db/schema_db2.sql` using native Db2 datatypes (`CLOB(1M)`, `INT GENERATED ALWAYS AS IDENTITY`).
  - Automated health check executing `SELECT 1 FROM SYSIBM.SYSDUMMY1`.
  - Transaction safety: Managed context with explicit `commit()` on success and `rollback()` on exceptions.
  - Dual-mode connection manager: Connects directly to genuine IBM Db2 when credentials and drivers are present, with transparent in-memory SQLite fallback for offline test suites and resource-constrained CI environments.
  - Safe row mapping: Translates both `ibm_db_dbi` tuple responses (via `cursor.description`) and SQLite rows into standard lowercase dictionary mappings.

---

## Operational Runbook Knowledge Retrieval
- **Mechanism:** Symptom and keyword overlap matching with service context weighting over curated operational playbooks (e.g., Db2 `SQL0964C` transaction log exhaustion, `SQL30081N` connection timeouts, JWT authentication desync).
- **Output:** Prioritized remediation steps and operational commands mapped directly to the incident metadata.

---

## Implementation Status

> **Verification Notice:** Live Db2 verification has not yet been performed. The native Db2 integration code and two live integration tests are implemented, but execution against a running IBM Db2 server remains outstanding because a live Db2 instance was unavailable during development.

| Feature / Component | Status | Details |
|---|---|---|
| **FastAPI REST API** | **Implemented** | Endpoints for `/health`, `/incidents`, `/incidents/{id}`, `/knowledge/query`, `/knowledge/ingest`. |
| **Lifecycle State Machine** | **Implemented** | Transitions through `CLASSIFYING`, `INVESTIGATING`, `REMEDIATING`, `VERIFYING`, `RESOLVED`. |
| **Native IBM Db2 Driver Layer** | **Implemented** | `ibm_db` and `ibm_db_dbi` connection management with parameterized queries. |
| **Native Db2 DDL** | **Implemented** | `schema_db2.sql` with native Db2 types and constraints. |
| **Row Mapping Layer** | **Implemented** | Maps tuple results from `ibm_db_dbi` safely using `cursor.description`. |
| **Offline Test Fallback** | **Implemented** | SQLite in-memory mode for unit tests without live database dependency. |
| **Runbook Knowledge Matching** | **Implemented** | Deterministic keyword/token overlap matching against curated runbooks. |
| **Live Db2 Integration Tests** | **Environment-Dependent** | `tests/test_db2_live.py` executes when live Db2 credentials and driver are available; skips safely otherwise. |
| **Native Db2 Vector Search** | **Planned** | Future enhancement for Db2 12.1+ native vector embeddings. |
| **Generative LLM Synthesis** | **Planned** | Future enhancement for IBM watsonx.ai Granite. |

---

## Tech Stack
- **Backend / Core:** Python 3.10+, FastAPI, Uvicorn, Pydantic v2
- **Database Persistence:** IBM Db2 Community Edition (Docker / Cloud), native `ibm_db` / `ibm_db_dbi`
- **Knowledge Catalog:** Curated Operational Runbook Engine
- **Testing & Tooling:** Pytest, Docker, Docker Compose

---

## Prerequisites
- **Python:** Version 3.10 or higher.
- **Memory Recommendation:**
  - Application + Test Suite: ~500 MB RAM.
  - Optional IBM Db2 Community Edition Container: Minimum 4 GB RAM (8 GB+ recommended).

---

## Setup & Installation

```bash
# 1. Navigate to the submission directory
cd submissions/db2-workrelay-intelligence

# 2. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to configure your Db2 connection:
```ini
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=testdb
DB2_USER=db2inst1
DB2_PASSWORD=your_db2_password_here
DB2_USE_MOCK=false
```

---

## Running the Project

### Option A: Local Development & Verification (Offline Mock Mode)
```bash
# Run database initialization
python src/app/db/init_db.py

# Launch the FastAPI server
python -m app.main
```
The application will be accessible at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### Option B: Docker Compose (Full Stack with IBM Db2 Community Edition)
```bash
docker compose up -d
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check, Db2 connectivity probe, AI engine status |
| `POST` | `/incidents` | Register and auto-triage a new operational incident |
| `GET` | `/incidents` | List incidents with filtering (`status`, `severity`, `service`) and pagination |
| `GET` | `/incidents/{id}` | Retrieve incident details, audit events, and remediation actions |
| `PATCH` | `/incidents/{id}` | Update incident status, severity, resolution, or escalation reason |
| `POST` | `/knowledge/query` | Query matching operational runbooks by symptom description |
| `POST` | `/knowledge/ingest` | Ingest new post-mortem or runbook into knowledge base |

---

## Testing & Verification

Db2 WorkRelay Intelligence includes both offline mock tests and live Db2 integration tests:

```bash
# Execute unit and repository tests (offline mock mode)
PYTHONPATH=src pytest tests/ -v
```

### Test Suite Structure:
- **`tests/test_models.py`**: Unit tests validating Pydantic models, state transitions, and audit timestamps.
- **`tests/test_ai_retrieval.py`**: Unit tests validating runbook catalog indexing, query symptom matching, and custom ingestion.
- **`tests/test_db2_repository.py`**: Repository tests validating CRUD operations, filtering, audit event logging, and SQL injection safety via SQLite in-memory mock.
- **`tests/test_db2_internals.py`**: Unit tests validating Db2 connection failure handling, tuple-to-dictionary row mapping, and native schema SQL parsing.
- **`tests/test_api.py`**: API endpoint validation testing health check, incident intake, querying, status patching, and 404 structured errors.
- **`tests/test_db2_live.py`**: Integration tests that execute against a live IBM Db2 instance when configured; safely skips when unconfigured.

---

## Known Limitations & Future Roadmap
- **Current Scope:** Native Db2 persistence layer, deterministic lifecycle state machine, and curated runbook retrieval.
- **Future Enhancements:**
  - Native Db2 12.1+ `VECTOR(n, FLOAT32)` storage using IBM watsonx Granite embeddings directly within Db2 SQL.
  - WebSocket live stream for real-time incident event monitoring in the Operations Console.

---

## Team Members & Credits
| Name | GitHub Handle | Role |
|---|---|---|
| Yemmy | [@Yemmmyc](https://github.com/Yemmmyc) | Full-Stack Developer & Backend Integration Specialist |
