# ColdChain Guardian

> **One-Line Pitch:** An enterprise-grade agentic AI platform powered by IBM Db2, LangGraph, and CrewAI for real-time cold-chain monitoring, automated temperature excursion detection, and human-in-the-loop corrective action planning.

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
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement
- **Challenge:** Over $35B worth of temperature-sensitive pharmaceuticals, biologics, and food products are spoiled annually due to cold-chain excursions in transit. Failures are often identified only upon delivery when cargo is unsalvageable.
- **Target Audience:** Cold-chain logistics managers, quality assurance compliance officers, and pharmaceutical freight operators.
- **Existing Gaps:** Legacy data loggers only provide passive forensic reports after excursions occur; they lack real-time predictive risk quantification, multi-agent root-cause reasoning, and auditable corrective workflows.

---

## Solution Overview
ColdChain Guardian combines transactional database reliability with dual-tier agentic AI:
- **Real-Time Excursion Detection:** Evaluates continuous IoT temperature telemetry against product sensitivity limits stored in IBM Db2.
- **Deterministic Risk Scoring:** Computes bounded 0–100 risk scores through LangGraph workflow orchestration to guarantee consistent, zero-hallucination evaluations.
- **Collaborative Multi-Agent Reasoning:** Leverages CrewAI specialists (Risk Analyst, Domain Expert, Recommendation Specialist) for root-cause analysis and actionable mitigation plans.
- **Human-in-the-Loop Governance:** Generates prioritized recommendations that require explicit human approval (`APPROVED` / `REJECTED`) with an immutable audit trail in Db2.
- **Enterprise Dark-Theme UI:** Real-time operational dashboard with fleet telemetry, risk distributions, and approval controls.

---

## IBM Db2 Integration
- **Db2 Edition & Environment:** Db2 Community Edition (Docker containerized) / Db2 on Cloud.
- **Connector / Driver Used:** Official Python `ibm_db` driver with parameterized SQL execution and connection lifecycle management.
- **Database Schema / Data Models:**
  1. `PRODUCTS`: Product categories, strict `min_temperature`, `max_temperature`, and sensitivity ratings.
  2. `SHIPMENTS`: Origin, destination, vehicle metadata, and transit status.
  3. `SENSOR_READINGS`: Time-series temperature and humidity telemetry linked to shipments.
  4. `INCIDENTS`: Automated incident records generated upon excursion detection.
  5. `RISK_ASSESSMENTS`: Deterministic risk scores, risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and score breakdowns.
  6. `RECOMMENDATIONS`: Rule-generated and agent-augmented actions with approval statuses (`PENDING`, `APPROVED`, `REJECTED`).
  7. `KNOWLEDGE_DOCUMENTS`: Vector/SOP reference documents.
  8. `AUDIT_LOGS`: Immutable trail of automated agent actions and human operator decisions.
- **Key Queries & Operations:**
  - Fast single-pass `JOIN` queries across readings, shipments, and product thresholds.
  - Concurrency-safe identity retrieval using `SELECT IDENTITY_VAL_LOCAL() AS NEW_ID FROM SYSIBM.SYSDUMMY1`.
  - Conditional inserts preventing duplicate active incidents or recommendations.
  - Relational indexes on foreign keys (`idx_sensor_shipment`, `idx_incident_shipment`, `idx_risk_incident`, `idx_rec_incident`).

---

## AI / LLM Architecture
- **Frameworks Used:** **LangGraph** (LangChain ecosystem) + **CrewAI**.
- **Model Provider & Model:** Google Gemini (`gemini/gemini-1.5-flash` / `gemini/gemini-2.0-flash`).
- **Two-Tier Architecture:**
  1. *Deterministic Layer (LangGraph):* Orchestrates a directed acyclic graph (`Monitoring` → `Incident` → `Risk Assessment` → `Recommendation`). Normal readings exit safely; excursions trigger incident persistence.
  2. *Collaborative AI Layer (CrewAI):* Three collaborative agents:
     - **Cold Chain Risk Analyst:** Evaluates biochemical degradation urgency.
     - **Cold Chain Domain Expert:** Diagnoses equipment failure modes, ambient climate variables, and GDP compliance.
     - **Recommendation Specialist:** Formulates prioritized, actionable mitigation steps.
- **Graceful Fallback:** If LLM API keys are missing or quota-limited, CrewAI falls back to Db2-derived explanations without interrupting the primary workflow.

---

## Tech Stack
- **Backend:** Python 3.11, FastAPI, Uvicorn, Pydantic
- **Database:** IBM Db2, `ibm_db` driver
- **AI & Agents:** LangGraph, CrewAI, Google Generative AI
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Recharts, Lucide React
- **DevOps / Environment:** Docker, python-dotenv

---

## Prerequisites
- Docker (for IBM Db2 Community Edition container) or an active IBM Db2 database instance.
- Python 3.10+
- Node.js 18+ and npm
- (Optional) Google Gemini API key for CrewAI collaborative reasoning.

---

## Setup & Installation

```bash
# 1. Clone repository and navigate to backend
cd submissions/coldchain-guardian/backend

# 2. Create and activate Python virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd ../frontend
npm install
```

---

## Configuration

Configure environment variables using the provided templates:

```bash
# Backend configuration
cd submissions/coldchain-guardian/backend
cp .env.example .env
# Edit .env and supply DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USER, DB2_PASSWORD
# Optionally supply GEMINI_API_KEY for live AI analysis

# Frontend configuration
cd ../frontend
cp .env.example .env
# Default points to VITE_API_URL=http://localhost:8000
```

> **Security Warning:** Never commit `.env` or real credentials to Git.

---

## Running the Project

### 1. Start IBM Db2 (Docker)
```powershell
docker run -d --name db2server --restart=always `
  -e DB2INSTANCE=db2inst1 `
  -e DB2INST1_PASSWORD=your_password `
  -e DBNAME=COLDCHN `
  -e LICENSE=accept `
  -p 50000:50000 --privileged=true icr.io/db2_community/db2
```

### 2. Initialize Database & Seed Data
```bash
cd submissions/coldchain-guardian/backend
python -m app.database.run_schema
python -m app.database.seed_data
```

### 3. Run FastAPI Backend
```bash
uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`

### 4. Run React Frontend
```bash
cd ../frontend
npm run dev
```
- Web Application: `http://localhost:5173`

---

## Testing & Verification
```bash
# Verify Db2 connection
cd submissions/coldchain-guardian/backend
python verify_connection.py

# Verify deterministic rule logic
python test_rules.py

# Validate submission folder compliance
cd ../../..
python scripts/validate_submission.py submissions/coldchain-guardian
```

---

## Known Limitations & Future Roadmap
- **Current Limitations:** Vector embeddings currently use mock vectors; production vector search requires the `LANGCHAIN_DB2` extension package or Db2 Graph.
- **Next Steps:**
  - Integration with active onboard telematics (MQTT/Kafka streams).
  - IoT edge agent deployment for localized offline decision-making on refrigerated transit units.
  - Multi-tenant enterprise RBAC for pharmaceutical logistics carriers.

---

## Team Members & Credits
| Name | Role / Contribution |
|---|---|
| Yasaswini Yarraguntla | Full-stack Engineering, IBM Db2 Design, LangGraph Orchestration & CrewAI Integration |
