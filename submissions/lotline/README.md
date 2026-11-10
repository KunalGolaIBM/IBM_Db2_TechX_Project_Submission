# LOTLINE — Agentic Recall Intelligence & Closed-Loop Recall Execution

> **One-Line Pitch:** An evidence-grounded recall intelligence and closed-loop execution platform that leverages IBM Db2 12.1 as the single source of truth to trace raw material contamination, quantify exposure, coordinate human-governed mitigations, and maintain an immutable regulatory audit trail.

---

## Synthetic Benchmark Scenario Notice

> **Important Disclosure:** This project demonstrates an incident investigation using synthetic benchmark scenario `INC-2026-001` (source lot `RAW-204`, supplier GreenLeaf Foods, Maharashtra, India). All company names, lot identifiers, shipment routes, and regulatory records are synthetic demonstration data for the **IBM Db2 TechX Summit 2026** competition. This software does not represent a real-world food safety contamination or an official filing with FSSAI or the FoSCoS portal.

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

When a pathogen like *Salmonella* is detected in a raw agricultural intake, food manufacturers face severe operational and regulatory challenges:
1. **Traceability Delays:** Traditional ERPs store multi-tier processing (Raw -> WIP -> Finished Goods) in fragmented tables, requiring hours of manual SQL joins or spreadsheets to identify which commercial product lines are contaminated.
2. **Exposure Miscalculation:** Operators frequently conflate raw mass (`KG`) with packaged consumer units (`UNIT`), or mistake warehouse-held quarantined inventory for market recovery, leading to flawed risk assessments.
3. **Logistics Interception Gaps:** Shipments already on the road or delivered to retail consignees require immediate, auditable intervention. Without real-time coordination, contaminated food reaches consumer shelves.
4. **Regulatory Audit Burden:** India's FSSAI (Food Recall Procedure) Regulations, 2017 require immediate formal notification within a strict statutory 24-hour awareness window and complete Schedule-I documentation across 14 distinct statutory fields.
5. **AI Hallucination Risks:** Generative AI solutions often invent batch numbers, fabricate supplier addresses, or alter recall quantities, creating unacceptable legal liabilities.

---

## Solution Overview

LOTLINE solves these critical challenges by combining **IBM Db2 12.1** with **LangGraph** multi-agent reasoning:

- **Recursive SQL Lineage Tracing:** Single-query recursive CTE traverses the entire production genealogy from raw intake lot `RAW-204` through intermediate WIP batches (`WIP-301..303`) to finished packaging runs (`FIN-401..403`).
- **Deterministic Exposure Intelligence:** Accurately separates warehouse-contained stock (`1,350` units, 56.25%) from distributed market exposure (`1,050` units = 850 delivered + 200 in transit). Raw material intake mass (`500.0 KG`) is maintained strictly separate from packaged finished goods counts (`2,400 UNIT`).
- **Closed-Loop Recall Execution Control Tower:**
  - *Mass Reconciliation:* Surfaces an unexplained `50.0 KG` raw mass difference as `UNRECONCILED` rather than silently balancing inventory.
  - *Consignee Communications:* Manages formal notice lifecycles (`DRAFT` -> `APPROVED` -> `SENT` -> `DELIVERED` -> `ACKNOWLEDGED`) across 4 retail partners.
  - *Logistics Interception:* Coordinates real-time carrier halting for active in-transit shipments (`SHP-002`, 200 units of `FIN-401`).
  - *Physical Recovery Matrix:* Distinguishes warehouse containment from verified market returns.
  - *Controlled Dispositions:* Requires human operator authorization and certificate proof before recording destruction.
  - *FSSAI Schedule-I Checklist:* Maps all 14 statutory fields with verification states and tracks the 24-hour awareness countdown.
  - *Effectiveness & Closure Governance:* Rejects recall closure attempts while market exposure or unverified blockers remain.
- **Human-in-the-Loop Governance:** AI agents propose actions; only certified human safety officers can authorize execution. All state changes are bound in ACID transactions with an append-only audit trail.
- **Official 6-Page A4 PDF Dossier:** Generates vector PDF documentation stamped with a two-pass SHA-256 tamper-evident digest.

---

## IBM Db2 Integration

- **Db2 Edition & Environment:** IBM Db2 Community Edition v12.1.5.0 running containerized in Podman on Linux x86_64.
- **Connector / Driver:** Official Python `ibm_db` (version 3.3.0).
- **Schema & Data Models:** Dedicated `LOTLINE_APP` schema comprising 14 relational tables:
  - `INCIDENTS`, `SUPPLIERS`, `FACILITIES`, `LOTS`, `LOT_LINEAGE`, `INVENTORY`, `SHIPMENTS`, `RECALL_ACTIONS`, `RECALL_COMMUNICATIONS`, `LOGISTICS_INTERVENTIONS`, `PRODUCT_RECOVERIES`, `PRODUCT_DISPOSITIONS`, `REGULATORY_SUBMISSIONS`, and `AUDIT_LOG`.
- **Advanced Db2 Features Utilized:**
  - *Recursive CTEs:* Evaluates multi-tier genealogy in a single recursive query.
  - *ACID Transactions:* Enforces atomic multi-table updates (`ibm_db.autocommit = False`) linking action status updates with audit trail insertion.
  - *Parameterized SQL:* 100% of database queries use parameter placeholders (`?`), preventing SQL injection.
  - *Forensic Mass Balance:* Computes material consumption balance across raw and intermediate lots.

---

## AI / LLM Architecture

- **Orchestration Framework:** LangGraph state graph coordinating four specialized agents:
  1. **Intake Agent:** Assesses hazard severity and matches discovery records.
  2. **Traceability Agent:** Interprets recursive Db2 genealogy.
  3. **Risk Assessment Agent:** Evaluates commercial retail distribution exposure.
  4. **Response Planning Agent:** Drafts targeted mitigation actions (`ACT-001..004`).
- **Model Provider & Model:** Google Gemini 3.5 Flash via official `google-genai` SDK.
- **Strict Grounding & Hallucination Prevention:**
  - Gemini receives only verified database evidence tuples.
  - Server-side validation rejects any invented supplier, batch, or modified quantity.
  - Deterministic fallback engine ensures full operational availability if offline.

---

## Tech Stack

- **Database:** IBM Db2 Community Edition 12.1.5.0
- **Backend:** Python 3.14, FastAPI, Uvicorn, ibm_db, LangGraph, Pydantic, ReportLab, PyMuPDF
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Canvas WebGL2 (Soffit 002)
- **Testing & Verification:** Pytest, Pytest-Asyncio, Playwright, Hypothesis

---

## Prerequisites

- **Python:** Version 3.10 or higher (tested on Python 3.14)
- **Node.js:** Version 18 or higher (tested on Node.js v20)
- **IBM Db2:** Running instance of IBM Db2 12.1 with schema `LOTLINE_APP` created via `src/database/schema.sql`
- **Optional:** Google Gemini API key for live AI narrative synthesis (not required for deterministic fallback)

---

## Setup & Installation

```bash
# 1. Clone repository and navigate to submission directory
git clone https://github.com/ankush-dev-eng/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission/submissions/lotline

# 2. Set up Python virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd src/frontend
npm install
cd ../..
```

---

## Configuration

Copy `.env.example` to `.env` in `src/backend/` and configure your credentials:

```bash
cp .env.example src/backend/.env
```

Key environment settings:
```ini
DB2_HOST=127.0.0.1
DB2_PORT=50000
DB2_DATABASE=testdb
DB2_SCHEMA=LOTLINE_APP
DB2_USER=db2inst1
DB2_PASSWORD=your_db2_password_here
GEMINI_API_KEY=your_optional_gemini_key_here
GEMINI_MODEL=gemini-2.5-flash
APP_PORT=8000
```

---

## Running the Project

### Start Backend API
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir src/backend
```
The API documentation is available at `http://127.0.0.1:8000/docs`.

### Start Frontend UI
```bash
cd src/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
Open `http://127.0.0.1:5173` in any modern web browser.

---

## Testing & Verification

LOTLINE features a comprehensive test suite of 47 automated tests verifying database grounding, recursive CTE lineage, hallucination rejection, ACID transactions, and closed-loop control tower operations:

```bash
# Run full backend test suite
python -m pytest src/backend/tests/test_agents_and_api.py -v
```

Expected result:
```text
======================== 47 passed in 7.29s ========================
```

### Validate Submission Format
```bash
# From repository root
python scripts/validate_submission.py submissions/lotline
```

---

## Screenshots & Demo

- **Demo Video:** `docs/demo/LOTLINE_DEMO_VIDEO.mp4` (Duration: 2:19, 1080p, H.264/AAC)
- **Verified Evidence Screenshots:** Indexed in `docs/screenshots/README.md` and packaged in `docs/screenshots/lotline_screenshots.zip`:
  1. `01-overview-desktop.png` — Operational Recall Dashboard (1920×1080)
  2. `02-overview-mobile.png` — Responsive Mobile Interface (390×844)
  3. `03-traceability-lineage.png` — Recursive SQL Lineage Graph
  4. `04-agent-findings.png` — LangGraph Multi-Agent Verification
  5. `05-agent-action-plan.png` — Mitigation Action Governance (ACT-001..004)
  6. `06-human-approval-gate.png` — Human-in-the-Loop Safety Authorization Gate
  7. `07-audit-timeline.png` — Immutable Db2 Audit Evidence Trail
  8. `08-control-tower-mass-reconciliation.png` — 50 KG Unreconciled Raw Mass Discrepancy
  9. `09-control-tower-logistics.png` — Active In-Transit Shipment Interception
  10. `10-control-tower-recovery-disposition.png` — Physical Recovery Matrix
  11. `11-control-tower-fssai-tracker.png` — 14 Schedule-I Statutory Items
  12. `12-control-tower-closure.png` — 12 Effectiveness Indicators & Closure Blockers
  13. `13-dossier-page-1.png` .. `18-dossier-page-6.png` — 6-Page A4 PDF Dossier

---

## Known Limitations & Future Roadmap

- **Current Scope:** Configured for single-plant / single-incident investigation with synthetic benchmark scenario `INC-2026-001`.
- **FoSCoS Portal Integration:** Currently functions as an internal preparation and readiness tracker; direct FoSCoS API submission requires live FSSAI government gateway credentials.
- **Future Roadmap:**
  - Multi-tenant enterprise Db2 deployment with role-based access control (RBAC).
  - Integration with IoT temperature sensor telemetry across refrigerated transport fleets.
  - Native IBM watsonx.ai Granite model integration alongside Gemini.

---

## Team Members & Credits

- **Author & Developer:** Ankush Shahu ([@ankush-dev-eng](https://github.com/ankush-dev-eng))
- **Event:** IBM Db2 TechX Summit / Db2Hack 2026
- **Category:** AI / RAG / Data Engineering / Analytics
- **License:** Apache License 2.0
