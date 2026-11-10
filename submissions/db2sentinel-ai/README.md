# Db2Sentinel AI
> **An Agentic AI-Powered Enterprise Database Security, Anomaly Detection & Incident Response Platform**  
> *From Database Events to Intelligent Security Decisions.*

[![IBM Db2](https://img.shields.io/badge/IBM%20Db2-11.5%20%7C%2012.1-blue?logo=ibm)](https://www.ibm.com/products/db2)
[![LangChain](https://img.shields.io/badge/AI%20Framework-LangChain%20%26%20LangGraph-green)](https://langchain.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-61DAFB?logo=react)](https://react.dev)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey)](LICENSE)

---

## 1. Project Title & Overview
**Db2Sentinel AI** is an intelligent enterprise database security platform submitted to the **IBM Db2 TechX Summit 2026 Hackathon (Round 2)**. It elevates **IBM Db2** from passive relational data storage into the active intelligence backbone of an autonomous Security Operations Center (SOC). By combining native Db2 audit facilities, the official `ibm_db` Python connector, deterministic anomaly detection, and **LangGraph** stateful multi-agent orchestration, Db2Sentinel AI detects threats, reconstructs attack timelines, and prepares human-verified containment actions in seconds.

---

## 2. Problem Statement
Enterprise databases store critical crown-jewel assets—financial records, customer PII, and administrative credentials. However, traditional database monitoring tools create significant operational bottlenecks:
- **Alert Fatigue & Noise:** Enterprise databases generate 10,000+ raw audit records daily. Security analysts waste 70%+ of their time triaging false positives.
- **Siloed Context:** Audit logs, connection telemetry, and query execution metrics reside in disjoint repositories.
- **The "Low-and-Slow" Threat Vector:** Sophisticated insiders and compromised accounts execute individually benign queries over weeks, slipping past static threshold alarms.
- **Investigation Latency:** Manually correlating cross-session database activity takes database administrators (DBAs) 4 to 6 hours per incident, delaying breach containment.

---

## 3. Proposed Solution
Db2Sentinel AI provides an autonomous, explainable, and human-governed investigation workflow:
1. **Continuous Telemetry Ingestion:** Captures native Db2 audit records (`db2audit`) and Activity Event Monitors (`WRITE TO TABLE`) via `ibm_db`.
2. **Dynamic Behavioral Baselines:** Tracks normal query fingerprints, active access windows, and expected row counts directly in Db2.
3. **Hybrid Detection Engine:** Blends 6 deterministic security rules with statistical standard deviation ($z$-score) algorithms.
4. **LangGraph Multi-Agent Investigation:** Orchestrates 6 specialized agents (Detection, Evidence, Investigation, Risk, Response, Report) across a stateful graph.
5. **Explainable Risk Scoring:** Computes a transparent 4-factor risk score (0–100) tied to immutable Db2 `event_id` citations.
6. **Human-in-the-Loop Governance:** Enforces strict checkpoint approval gates (`interrupt_before`) before any sensitive containment action is executed.

---

## 4. Key Features
- **Meaningful IBM Db2 Foundation:** Central persistence for 6 core security entities (`SENTINEL_EVENTS`, `SENTINEL_ALERTS`, `SENTINEL_INCIDENTS`, `SENTINEL_INVESTIGATIONS`, `SENTINEL_APPROVALS`, `SENTINEL_AUDIT_LOG`).
- **Official Python Connector (`ibm_db`):** Parameterized prepared statements, transaction management, and TLS encryption.
- **6 Deterministic Security Rules:**
  - Rule 1: Brute Force Authentication ($\ge 5$ failures from single source)
  - Rule 2: Password Spraying Campaign ($\ge 3$ distinct accounts targeted)
  - Rule 3: Privileged Activity & Catalog Reconnaissance (`SYSCAT.*`)
  - Rule 4: Unusual Query Frequency & Volume Spikes ($z$-score $\ge +3.0\sigma$)
  - Rule 5: Sensitive Object Access (`CUSTOMER_FINANCIAL_RECORDS`)
  - Rule 6: Suspicious Operating Window (Off-hours access)
- **Zero-Hallucination Evidence Provenance:** Every agent hypothesis links to an immutable `source_event_id` in Db2.
- **Human Approval Checkpoints:** No autonomous deletion, table drop, or user lockout; every remediation requires explicit DBA authorization.
- **Interactive SOC Command Centre:** React + TypeScript dashboard with real-time metrics, event timelines, risk gauges, and approval modals.
- **One-Click Security Demo:** Generates controlled baseline and multi-stage simulated attack telemetry.

---

## 5. Technology Stack
- **Database:** IBM Db2 Community Edition (Docker / Linux / Windows) / Db2 on Cloud
- **Database Driver:** Official `ibm_db` Python C-extension & DBI driver
- **Backend Framework:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn
- **AI & Multi-Agent Framework:** LangChain (mandatory framework), LangGraph (StateGraph orchestration)
- **LLM Support:** Google Gemini, OpenAI GPT-4o, Ollama (local), or deterministic rule-based fallback
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide Icons
- **Testing & Quality:** pytest, ESLint, official repository submission validator

---

## 6. Architecture Overview
```
[ IBM Db2 Engine ]
       │  (db2audit & Activity Event Monitors)
       ▼
[ Python Ingestion Service ]
       │  (Parameterized Inserts via ibm_db)
       ▼
[ SENTINEL_* Relational Tables in Db2 ]
       │
       ▼
[ Detection & Analytics Engine ] ──(Trigger)──► [ LangGraph Multi-Agent Team ]
                                                       │
                                                ┌──────┴──────┐
                                                ▼             ▼
                                         [ Evidence ]  [ Risk Engine ]
                                                │             │
                                                └──────┬──────┘
                                                       ▼
                                            [ Response Proposals ]
                                                       │
                                                       ▼
                                            [ Human Approval Gate ]
                                                       │
                                                       ▼
                                            [ Remediated Db2 State ]
```

---

## 7. Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** 18.0 or higher
- **Git:** Installed and configured
- **Docker:** (Optional, for running local IBM Db2 container)

---

## 8. IBM Db2 Installation Instructions

### Option A: Docker (Recommended)
```bash
# Pull official IBM Db2 Community Edition image
docker pull icr.io/db2_community/db2:11.5.8.0

# Start Db2 container with SENTINELDB database
docker run -d --name db2sentinel \
  --privileged=true \
  -p 50000:50000 \
  -e LICENSE=accept \
  -e DB2INSTANCE=db2inst1 \
  -e DB2INST1_PASSWORD=password \
  -e DBNAME=SENTINELDB \
  icr.io/db2_community/db2:11.5.8.0
```

### Option B: Local Installation on Windows/Linux
1. Download IBM Db2 Community Edition from IBM's official developer portal.
2. Install with default port `50000`.
3. Create database: `db2 create database SENTINELDB using codeset UTF-8 territory US`.

---

## 9. Configuration (`.env`)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure your Db2 connection and AI provider:
```ini
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=SENTINELDB
DB2_USERNAME=db2inst1
DB2_PASSWORD=password
DB2_SECURITY=NONE
DB2_DEMO_FALLBACK=true

LLM_PROVIDER=mock
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

---

## 10. Backend Setup & Run
```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Verify IBM Db2 connection
python scripts/check_db_connection.py

# 3. Initialize database schema
python scripts/initialize_db.py

# 4. Start the FastAPI backend server
python -m uvicorn src.backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
Backend API will be live at: `http://127.0.0.1:8000`  
Interactive OpenAPI Documentation: `http://127.0.0.1:8000/docs`

---

## 11. Frontend Setup & Run
```bash
# 1. Navigate to frontend directory
cd src/frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```
Frontend Security Console will be live at: `http://localhost:5173`

---

## 12. Automated Tests
Run the comprehensive automated test suite:
```bash
pytest tests/ -v
```
All 10 unit and integration tests validate:
- IBM Db2 connection & diagnostic verification
- Event CRUD operations
- Brute-force and privilege detection rules
- 4-factor mathematical risk scoring
- LangGraph stateful multi-agent execution
- Human-in-the-loop approval workflows

---

## 13. End-to-End Security Demonstration
Execute the automated CLI incident walkthrough:
```bash
python scripts/run_demo.py
```
This script:
1. Seeds controlled baseline and attack telemetry into Db2.
2. Runs the 6 deterministic detection rules.
3. Generates correlated security incident `INC-2026-0884`.
4. Orchestrates the LangGraph multi-agent team (Detection, Evidence, Investigation, Risk, Response, Report).
5. Displays the explainable risk score (87.5/100, Critical) and MITRE ATT&CK mapping (T1087, T1213, T1110).
6. Halts at the human approval gate and executes verified DBA sign-off.

---

## 14. Submission Validation
Run the official IBM Db2 TechX submission validator:
```bash
python scripts/validate_submission.py submissions/db2sentinel-ai
```

---

## 15. Extended Technical Documentation
Detailed engineering and operational documentation is available in [`docs/`](docs/):
- **[3-Minute Video Demo Script](docs/demo-script.md):** Exact 0:00–3:00 timeline script, visual cues, and recording checklist.
- **[Enterprise Security Model](docs/security-model.md):** Threat landscape, MITRE ATT&CK mapping, least-privilege architecture, prompt-injection defense, and human-in-the-loop governance.
- **[Installation & Setup Guide](docs/installation.md):** Comprehensive setup instructions for IBM Db2 (Docker/on-prem), FastAPI backend, and React command centre.
- **[Testing & Verification Guide](docs/testing.md):** Automated unit/integration test specifications, simulation scenarios, and validation checks.

---

## 16. Contributor Information
- **Project:** Db2Sentinel AI
- **Slug:** `db2sentinel-ai`
- **Framework Choice (Form):** LangChain
- **Orchestration:** LangGraph (StateGraph Multi-Agent Architecture)
- **Database Driver:** `ibm_db` (Official IBM Python Driver)
- **Competition:** IBM Db2 TechX Summit 2026 — Db2Hack Round 2
