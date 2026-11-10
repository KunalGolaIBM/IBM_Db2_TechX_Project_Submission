# SupplyChain Sentinel
### An Agentic AI Control Tower for Intelligent Supply Chain Risk Detection & Recovery

<p align="center">

**Detect Early. Investigate Intelligently. Recover Confidently.**

</p>

<p align="center">

[🚀 Live Demo](https://bhatt-submissionssupplychain-sentinelsrcapp-wm4kdi.streamlit.app/) · [🎥 Watch Demo Video](https://youtu.be/B6Wv24nLZPc?si=g40h9UImbcTebczA) · [💻 GitHub Repository](https://github.com/bhattbhumika31-dotcom/IBM_Db2_TechX_Project_Submission)

</p>

---

## Overview

**SupplyChain Sentinel** is an AI-powered supply chain risk management platform designed to help manufacturers identify disruptions, understand their operational consequences, and evaluate evidence-backed recovery strategies.

Manufacturing operations depend on interconnected processes involving suppliers, purchase orders, inventory, shipments, quality inspections, and production schedules. When these systems operate in isolation, even a small delay can escalate into a significant production disruption.

SupplyChain Sentinel addresses this challenge through an agentic workflow powered by **LangGraph and an IBM Db2-oriented data architecture**.

Instead of simply displaying alerts, it investigates the underlying records, calculates operational impact, generates mitigation options, and maintains a traceable human approval process.

## 🚀 Live Project

| Resource | Link |
|---|---|
| Live Application | [Open SupplyChain Sentinel](https://bhatt-submissionssupplychain-sentinelsrcapp-wm4kdi.streamlit.app/) |
| Demo Video | [Watch on YouTube](https://youtu.be/B6Wv24nLZPc?si=g40h9UImbcTebczA) |
| GitHub Repository | [View Source Code](https://github.com/bhattbhumika31-dotcom/IBM_Db2_TechX_Project_Submission) |

## Problem Statement

Manufacturers frequently manage purchase orders, supplier performance, inventory, shipment events, quality holds, and production demand through separate operational records.

A delayed shipment may appear as an isolated alert, while its actual consequences remain hidden:

- Which production orders depend on the delayed component?
- How much usable inventory is available?
- How long can production continue?
- Which suppliers or orders are exposed?
- What recovery options are feasible?
- What evidence supports the recommended action?

SupplyChain Sentinel connects these operational signals to help planners make informed decisions before disruptions escalate.

## 💡 Our Solution

SupplyChain Sentinel transforms a disruption signal into an explainable risk investigation.

### Agentic AI Workflow

The application follows a structured multi-agent workflow orchestrated using LangGraph.

1. **Monitor Agent** – Identifies potential supply disruptions, including delayed shipments and low inventory.
2. **Db2 Investigator Agent** – Retrieves relevant supplier, purchase order, inventory, shipment, quality, and production records.
3. **Impact Analyst Agent** – Calculates inventory runway and identifies potentially affected production orders.
4. **Mitigation Planner Agent** – Evaluates and ranks recovery options such as expediting, partial allocation, alternate-source review, and schedule review.
5. **Evidence Verifier Agent** – Checks whether proposed recommendations are supported by retrieved records and labels assumptions.
6. **Human Approval Layer** – Allows an authorized human decision-maker to review and record an approval event.

**Workflow:**

`Monitor → Investigate → Assess → Plan → Verify → Persist`

The platform does not automatically issue purchase orders or modify production schedules. Human oversight remains central to operational decisions.

## 🏗️ Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3.11+ |
| Database | IBM Db2 |
| Database Driver | ibm_db |
| Agent Orchestration | LangGraph |
| Application Framework | Streamlit |
| Data Processing | Pandas |
| Configuration | python-dotenv |
| Testing | pytest |
| Demo Fallback | SQLite |

## IBM Db2 Integration

IBM Db2 is the intended primary database backend for SupplyChain Sentinel.

The application is designed to use the `ibm_db` Python driver to connect to an IBM Db2 instance through environment-based configuration.

### Database Schema

The database design includes the following operational tables:

- `SUPPLIER`
- `COMPONENT`
- `INVENTORY`
- `PURCHASE_ORDER`
- `SHIPMENT_EVENT`
- `QUALITY_INSPECTION`
- `PRODUCTION_ORDER`
- `RISK_CASE`
- `RECOMMENDATION`
- `APPROVAL_AUDIT`

### Database Operations

The repository includes SQL scripts and application logic for:

- Multi-table relational queries and joins.
- Supplier delivery performance analysis.
- Parameterized database lookups.
- Risk investigation persistence.
- Recommendation records.
- Human approval audit events.

**Database configuration:** Set the required Db2 connection variables in `.env`:

`DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USERNAME`, and `DB2_PASSWORD`.

The application also provides an explicitly labelled SQLite demonstration fallback when Db2 credentials are not configured. This fallback supports local exploration but does not replace demonstrating a real Db2 connection.

## ✨ Key Features

- **Early Disruption Detection:** Identify potential supply chain risks.
- **Operational Impact Analysis:** Connect shipment delays to inventory and production exposure.
- **Inventory Runway Calculation:** Estimate available inventory coverage.
- **Explainable Recommendations:** Present mitigation options supported by retrieved evidence.
- **Multi-Agent Investigation:** Coordinate specialized agents through LangGraph.
- **Human-in-the-Loop Approval:** Keep important operational decisions under human control.
- **Investigation History:** Maintain traceable risk cases and approval records.
- **Reproducible Demo:** Includes database scripts, sample data, setup instructions, and tests.

## 🖥️ Running the Project Locally

### Prerequisites

- Python 3.11 or later
- Git
- IBM Db2 instance for the full database integration
- Docker Desktop if running Db2 locally

### 1. Clone the repository

```bash
git clone https://github.com/bhattbhumika31-dotcom/IBM_Db2_TechX_Project_Submission.git

cd IBM_Db2_TechX_Project_Submission
```

### 2. Navigate to the project

```bash
cd submissions/supplychain-sentinel
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Copy `.env.example` to `.env` and configure the required settings.

Never commit actual database credentials or secrets.

### 6. Prepare the database

For the Db2 integration path, execute:

```text
sql/schema_db2.sql
sql/seed_db2.sql
```

Use a compatible Db2 SQL client and a configured Db2 instance.

### 7. Launch the application

```bash
streamlit run src/app.py
```

The application opens in your browser.

## 🎬 Demo Walkthrough

The demonstration uses the seeded scenario:

**Scenario: `SHIP-1008` — Delayed Motor-Controller Shipment**

The demo showcases:

1. Opening the SupplyChain Sentinel dashboard.
2. Starting a disruption investigation.
3. Reviewing the database mode and retrieved source records.
4. Examining inventory runway and affected production orders.
5. Exploring ranked recovery recommendations.
6. Reviewing evidence verification.
7. Recording a human approval event.
8. Inspecting the investigation and approval history.

**Watch the complete demonstration:**  
[SupplyChain Sentinel – Project Demo](https://youtu.be/B6Wv24nLZPc?si=g40h9UImbcTebczA)

## 🧪 Testing

Run the available test suite using:

```bash
pytest -q
```

The tests cover deterministic impact calculations and recommendation verification.

For Db2-specific verification, configure valid Db2 credentials, run the application, and confirm that the application reports a successful IBM Db2 connection.

## 🔐 Responsible AI & Human Oversight

SupplyChain Sentinel is designed around explainability and controlled decision-making.

- Database records remain the source of operational facts.
- Business calculations use inspectable deterministic rules.
- Recommendations are checked against retrieved evidence.
- Assumptions are explicitly identified.
- Human approval is required before an approval event is recorded.
- The system does not autonomously change production schedules or issue purchase orders.

## 🔭 Future Scope

Potential enhancements include:

- Real-time shipment tracking and event streaming.
- ERP and procurement platform integrations.
- Role-based approval workflows.
- Supplier reliability forecasting.
- More advanced uncertainty-aware risk prediction.
- IBM watsonx.ai integration for evidence-grounded natural-language explanations.

## 👩‍💻 Individual Participation

**Project:** SupplyChain Sentinel  
**Participant:** Bhumika Bhatt  
**GitHub:** [@bhattbhumika31-dotcom](https://github.com/bhattbhumika31-dotcom)  
**Institution:** Graphic Era Deemed to be University

**Contribution:** Project design, database integration, agent workflow development, application implementation, and documentation.

---

## Final Note

SupplyChain Sentinel demonstrates how relational enterprise data and agentic AI workflows can work together to move beyond isolated alerts toward explainable, evidence-backed supply chain decisions.

**Built for IBM Db2 TechX Summit – Db2Hack 2026.**
