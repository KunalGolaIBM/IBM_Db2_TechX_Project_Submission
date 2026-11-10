# SupplyChain Sentinel

> **One-line pitch:** An IBM Db2-backed, LangGraph-orchestrated agentic control tower that detects manufacturing supply risks, traces their operational impact, and prepares evidence-backed recovery options for human approval.

## Problem statement
Manufacturers often keep purchase orders, inventory, supplier performance, shipment events, quality holds, and production demand in separate operational records. A late component can become a production interruption before a planner has reconciled all those records. Dashboards surface individual alerts, but do not consistently connect the alert to affected orders, inventory runway, policy constraints, and a traceable decision.

## Solution overview
SupplyChain Sentinel turns a disruption signal into a structured risk case:
1. **Monitor Agent** detects a shipment delay or low inventory signal.
2. **Db2 Investigator Agent** retrieves the relevant supplier, purchase order, inventory, shipment, quality, and production records using narrow, parameterized tools.
3. **Impact Analyst Agent** calculates inventory runway and identifies exposed production orders using deterministic business rules.
4. **Mitigation Planner Agent** ranks safe options such as expediting, partial allocation, alternate-source review, or schedule review.
5. **Evidence Verifier Agent** checks that recommendations are supported by retrieved records and clearly labels assumptions.
6. **Human approval** is required before an approval event is recorded. The demo never automatically issues purchase orders or changes production schedules.

## IBM Db2 integration
- **Edition/environment:** IBM Db2 Community Edition (Docker) or an accessible IBM Db2 instance.
- **Connector:** `ibm_db` Python driver.
- **Real Db2 path:** Set `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USERNAME`, and `DB2_PASSWORD`. The application then connects to Db2 and executes the SQL in `sql/schema_db2.sql` and `sql/seed_db2.sql`.
- **Tables:** `SUPPLIER`, `COMPONENT`, `INVENTORY`, `PURCHASE_ORDER`, `SHIPMENT_EVENT`, `QUALITY_INSPECTION`, `PRODUCTION_ORDER`, `RISK_CASE`, `RECOMMENDATION`, and `APPROVAL_AUDIT`.
- **Meaningful operations:** multi-table joins, aggregations for supplier delivery performance, parameterized lookups, risk-case persistence, and transactional approval audit writes.
- **Demo fallback:** If Db2 credentials are absent, a local SQLite demo store is used so the interface and workflow can be explored. This fallback is clearly marked and is **not a substitute for demonstrating the Db2 connection** during judging.

## AI / agent architecture
- **Framework:** LangGraph `StateGraph`.
- **Agent workflow:** `monitor -> investigate -> assess -> plan -> verify -> persist`.
- **Model role:** The core workflow uses deterministic, inspectable calculations so that the demo works without a paid model key. An optional LLM can be added for natural-language narrative, but the LLM must not invent quantities or override Db2 facts.
- **Tool boundary:** Agents can call only allow-listed repository methods. No unrestricted text-to-SQL is exposed.

## Tech stack
Python 3.11+, IBM Db2, `ibm_db`, LangGraph, Streamlit, Pandas, python-dotenv, pytest.

## Prerequisites
- Python 3.11+
- IBM Db2 Community Edition or a reachable IBM Db2 database for the full integration path
- Docker Desktop if running Db2 locally
- Optional: Git

## Setup & installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a local Db2 container, use IBM's official Db2 Community Edition image and its current setup instructions. Configure the environment variables in `.env`, then execute `sql/schema_db2.sql` followed by `sql/seed_db2.sql` using a Db2 SQL client.

For quick UI exploration without Db2 credentials, leave the Db2 variables empty; the app starts in explicitly labelled SQLite demo mode and creates synthetic sample records.

## Configuration
See `.env.example`. Never commit `.env` or real credentials.

## Running the project

```bash
streamlit run src/app.py
```

## Demo walkthrough
1. Open the dashboard and select **Investigate disruption**.
2. Use the seeded scenario `SHIP-1008` (delayed motor-controller shipment).
3. Review the Db2/SQLite mode indicator and the source records retrieved.
4. Inspect inventory runway, affected production orders, ranked mitigation options, and evidence checks.
5. Select an option and click **Record human approval** to persist an approval audit event.
6. Open the case history to inspect the saved investigation and approval trail.

## Testing & verification

```bash
pytest -q
```

Unit tests cover deterministic impact calculations and recommendation verification. To verify Db2 specifically, run the app with valid Db2 credentials and confirm the sidebar reports `IBM Db2 connected`; the seeded tables and parameterized repository queries are then exercised against Db2.

## Screenshots & demo
Add real screenshots captured from your running application to `docs/screenshots/` before final submission. Do not present mockups as live application screenshots.

## Known limitations & roadmap
- The included dataset is synthetic and designed for a reproducible hackathon demonstration.
- Supplier alternate-source feasibility is represented as a review recommendation; real qualification requires external supplier and compliance data.
- Future work: role-based approvals, ERP connectors, streaming shipment feeds, forecast uncertainty, and IBM watsonx.ai narrative synthesis.

## Individual participation
| Name | GitHub handle | Role |
|---|---|---|
| Bhumika Bhatt | bhattbhumika31-dotcom | Product design, Db2 integration, agent workflow and application |
