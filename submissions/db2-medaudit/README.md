# DB2 MedAudit — AI Clinical Test Verification & Lab Kickback Detection

> **One-Line Pitch:** An intelligent medical prescription audit platform powered by **IBM Db2** and **LangChain / Gemini** that detects unnecessary diagnostic tests prescribed by doctors with potential lab kickback agreements, protecting patients from financial exploitation and medical overtreatment.

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

Diagnostic lab kickbacks are a pervasive problem across healthcare systems worldwide. Doctors with undisclosed commission contracts with diagnostic laboratories over-prescribe expensive and often unnecessary tests — MRIs, CT scans, full blood panels — to earn kickback percentages of 25–40%. Patients bear the cost without knowing the tests are clinically unwarranted.

- **Target audience:** Hospital compliance officers, health insurance auditors, patient advocacy groups, and independent healthcare watchdogs.
- **Why existing tooling is insufficient:** Current EMR systems lack automated cross-referencing of prescriptions against evidence-based clinical guidelines (NICE, WHO, ICMR) and have no awareness of doctor-lab commission contract databases.

---

## Solution Overview

DB2 MedAudit is a full-stack web application and AI agent that:

1. **Ingests prescription data** (symptoms, chief complaint, ordered tests, assigned doctor and lab).
2. **Cross-references against IBM Db2** — querying `CLINICAL_GUIDELINES` for evidence-based indicated / unwarranted tests for the detected condition, `DOCTORS` for the prescribing doctor's suspicion score, and `LAB_COMMISSION_CONTRACTS` for active kickback agreements.
3. **Runs a LangChain + Gemini AI audit agent** that synthesises the structured Db2 query results into a natural-language audit report — flagging each over-prescribed test, estimating patient savings, and calculating an alert severity.
4. **Displays results** in an interactive React dashboard with a Kickback Matrix, Audit Workspace, and DB2 Studio (live SQL query runner).

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 Community Edition 11.5.8 on Docker (`ibmcom/db2:11.5.8.0`); also compatible with Db2 on IBM Cloud.
- **Connector / Driver Used:** `ibm_db >= 3.2.0` (native Python driver), `ibm_db_sa >= 0.4.0` (SQLAlchemy dialect), and the LangChain `SQLDatabase` wrapper for agent tool integration.
- **Database Schema — `CLINICAL_INTELLIGENCE` schema:**

| Table | Purpose |
|---|---|
| `CLINICAL_GUIDELINES` | NICE / WHO / ICMR evidence-based indicated and unwarranted tests per condition |
| `DIAGNOSTIC_LABS` | Lab registry with accreditation, city, and average markup % |
| `DOCTORS` | Physician profiles: suspicion score and unnecessary order rate |
| `LAB_COMMISSION_CONTRACTS` | Documented doctor–lab kickback contracts with commission % |
| `TEST_CATALOG` | Benchmark and fair-market pricing for standard diagnostic tests |
| `AUDIT_LOGS` | Patient encounter audit trails, savings calculated, and kickback alerts |

- **Key Queries & Operations:**
  - `SELECT` clinical guidelines for the detected condition to obtain indicated vs unwarranted test lists.
  - `JOIN` `DOCTORS` → `LAB_COMMISSION_CONTRACTS` → `DIAGNOSTIC_LABS` to determine whether the prescribing doctor has an active commission contract with the referred lab.
  - `INSERT` into `AUDIT_LOGS` after each audit run to persist findings.
  - `SELECT` sorted by `POTENTIAL_SAVINGS DESC` for the Kickback Matrix leaderboard view.

---

## AI / LLM Architecture

- **Framework:** LangChain `create_sql_agent` with a custom `SQLDatabaseToolkit`
- **Model Provider & Model:** Google Gemini `gemini-1.5-pro` via `langchain-google-genai`
- **RAG / Tool Calling Workflow:**
  1. User submits a prescription (symptoms + ordered tests + doctor/lab IDs).
  2. The LangChain SQL agent issues structured Db2 queries to retrieve guidelines and commission data.
  3. Retrieved context (guidelines, doctor suspicion score, active kickback contracts) is assembled into a prompt template.
  4. Gemini generates a structured audit report: flagged tests, clinical justification, savings estimate, and a risk alert level.
  5. The audit result is written back to `AUDIT_LOGS` in Db2 for compliance trail.

---

## Tech Stack

- **Backend / Core:** Node.js 18+ / Express (API server + Vite middleware), TypeScript
- **Database:** IBM Db2 Community Edition 11.5 (Docker) + `ibm_db` Python driver
- **AI Agent:** Python 3.10+ / LangChain + LangChain-Google-GenAI + Gemini 1.5 Pro
- **Frontend / UI:** React 19 + Vite + TailwindCSS 4 + Lucide React
- **Libraries & Tools:** Docker, SQLAlchemy, `ibm_db_sa`, `python-dotenv`, `motion`

---

## Prerequisites

- **Docker** (to run the local IBM Db2 container)
- **Node.js >= 18** and **npm**
- **Python >= 3.10** and `pip`
- A **Google Gemini API key** (free tier at [aistudio.google.com](https://aistudio.google.com))

---

## Setup & Installation

### 1. Start IBM Db2 Container
```bash
docker run -itd --name db2server \
  --restart=always \
  -e LICENSE=accept \
  -e DB2INST1_PASSWORD=db2password123 \
  -e DBNAME=MEDAUDIT \
  -p 50000:50000 \
  --privileged=true \
  ibmcom/db2:11.5.8.0
```

Wait ~60 seconds for Db2 to initialise, then load the schema:
```bash
docker exec -i db2server su - db2inst1 -c "db2 connect to MEDAUDIT && db2 -tvf -" \
  < src/scripts/schema_ibm_db2.sql
```

### 2. Install Node.js Dependencies
```bash
cd submissions/db2-medaudit
npm install
```

### 3. Install Python Dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r src/scripts/requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `DB2_HOST` | Db2 hostname (default: `localhost`) |
| `DB2_PORT` | Db2 port (default: `50000`) |
| `DB2_USER` | Db2 user (default: `db2inst1`) |
| `DB2_PASS` | Db2 password |
| `DB2_DB` | Db2 database name (default: `MEDAUDIT`) |

> **Security Warning:** Never commit `.env` or real credentials to Git!

---

## Running the Project

### Web Application (React + Express)
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000)

### Python LangChain Audit Agent (standalone)
```bash
export GEMINI_API_KEY="your-key"
export DB2_HOST="localhost" DB2_PORT="50000"
export DB2_USER="db2inst1" DB2_PASS="db2password123" DB2_DB="MEDAUDIT"

python src/scripts/medaudit_langchain_agent.py
```

---

## Testing & Verification

1. Open the web UI at `http://localhost:3000`.
2. Navigate to **Audit Workspace** → enter a sample prescription (e.g. chief complaint: "mild cough", ordered tests: "CT Chest, Full Blood Panel, MRI Brain").
3. Click **Run Audit** — the system should flag MRI Brain and CT Chest as unwarranted for a mild cough presentation and show estimated savings.
4. Navigate to **DB2 Studio** to run live SQL queries against the `CLINICAL_INTELLIGENCE` schema.
5. Check **Kickback Matrix** for the doctor suspicion leaderboard.

---

## Screenshots & Demo

- **Live Demo Link:** [https://github.com/aradhyaawasthi2006-hue/MedAudit](https://github.com/aradhyaawasthi2006-hue/MedAudit)
- **Source Repository:** [https://github.com/aradhyaawasthi2006-hue/MedAudit](https://github.com/aradhyaawasthi2006-hue/MedAudit)
- Screenshots are in `docs/screenshots/`.

---

## Known Limitations & Future Roadmap

- **Current Limitations:**
  - Mock prescription data used in the frontend; full EMR integration is not yet implemented.
  - The Python LangChain agent requires a locally running or cloud Db2 instance; a mock DB mode is available in the React app.
  - No multi-tenant support yet.
- **Next Steps:**
  - FHIR/HL7 EMR adapter for real patient record ingestion.
  - Db2 Vector Search integration for semantic guideline retrieval.
  - Multi-language prescription support (Hindi, Tamil).
  - Fine-tuned medical domain LLM on watsonx.ai.

---

## Team Members & Credits

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Aradhya Awasthi | [@aradhyaawasthi2006-hue](https://github.com/aradhyaawasthi2006-hue) | Full-Stack Developer, IBM Db2 Integration, AI Agent |
