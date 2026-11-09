# MediFlow AI

> **One-line pitch:** MediFlow AI helps hospital and pharmacy inventory teams spot medicine stockout and batch-expiry risks, then prepare explainable reorder drafts backed by IBM Db2 records and a LangGraph workflow.

## Problem statement

Hospitals, clinics and pharmacies often manage medicine stock across disconnected spreadsheets, billing exports and supplier records. A stock count alone does not show whether current stock can last until the next delivery, which batches may expire soon, or what quantity should be considered for replenishment. Inventory managers need an auditable view of risk and a clear rationale for proposed action. MediFlow AI is an operational decision-support prototype; it is not a clinical system and does not make treatment recommendations.

## Solution overview

The application reads medicine, inventory, batch, usage and supplier lead-time records. Its workflow calculates estimated days of cover, detects stockout and expiry exposure, drafts a suggested reorder quantity with supporting reasons, and waits for a named human reviewer to approve or reject it. No order is sent to a supplier.

Core capabilities:
- Inventory snapshot with stock, daily usage, supplier lead time and expiry exposure.
- Stockout risk when estimated cover falls below supplier lead time plus a configurable three-day buffer, or stock is below reorder level.
- Near-term expiry flags for batches expiring within 30 days.
- Draft reorder quantity based on a target coverage window.
- Human review boundary and an approval-event audit trail.
- Explicit synthetic-data demo mode and configurable Db2 mode.

## IBM Db2 integration

- **Edition/environment:** IBM Db2 Community Edition or a compatible Db2 instance. A live hosted Db2 environment is not bundled with this repository.
- **Connector:** Python `ibm_db` driver with bound SQL parameters.
- **Tables:** `MEDICINES`, `SUPPLIERS`, `INVENTORY`, `BATCHES`, `USAGE_HISTORY`, `RECOMMENDATIONS`, and `APPROVAL_EVENTS`.
- **Operations:** Read inventory and batch data; insert workflow recommendations; update review status; append review/audit events.
- **Setup:** See `docs/DB2_SETUP.md` and `src/db/schema.sql`.

Set `DATA_BACKEND=db2` to use the database adapter. The default `DATA_BACKEND=demo` uses clearly labelled synthetic in-memory records. Demo mode is not represented as Db2 integration. The live adapter and SQL are included but still require validation against an actual Db2 instance.

## AI / LLM architecture

- **Framework:** LangGraph state graph.
- **MVP model strategy:** Deterministic Python risk and reorder calculations; no external LLM is called in this version. A generated narrative explanation can be added later.
- **Workflow:** `assess_risk → draft_recommendations`. Nodes receive validated structured records from the repository layer; agents do not have unrestricted SQL access.
- **Human control:** Recommendations begin as `PENDING_REVIEW`; reviewer approval/rejection is a separate explicit operation.

## Tech stack

- Python 3.11+
- FastAPI API
- Streamlit reviewer UI
- IBM Db2 and `ibm_db`
- LangGraph
- Pydantic and pytest

## Prerequisites

- Python 3.11 or newer.
- For demo mode: Python package installation only.
- For Db2 mode: access to a disposable IBM Db2 database and any OS-specific Db2 client/runtime prerequisites required by `ibm_db`.

## Setup & installation

```bash
cd submissions/mediflow-ai
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env`. Keep the actual `.env` file local and never commit database passwords or API keys.

- Demo: `DATA_BACKEND=demo`.
- Db2: `DATA_BACKEND=db2` and set `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USER`, `DB2_PASSWORD`, and `DB2_SECURITY`.

## Running the project

Start the Streamlit interface:

```bash
streamlit run src/ui.py
```

Start the API in a second terminal:

```bash
uvicorn src.api:app --reload --port 8000
```

API endpoints: `GET /health`, `GET /inventory`, `POST /recommendations/run`, and `POST /recommendations/{id}/review`.

For Db2 mode, initialise the tables with `python -m src.db.init_db` and add synthetic seed rows as described in `docs/DB2_SETUP.md` before launching the app.

## Testing & verification

```bash
python -m pytest -q
```

The included unit tests cover stockout/expiry assessment, recommendation draft status and the demo repository review boundary. They do not prove connectivity to a live Db2 server. Test database reads and writes separately against a disposable Db2 instance.

## Screenshots & demo

- Live deployment: not deployed.
- Demo recording: not recorded.
- Capture genuine UI screenshots after running the app and save them under `docs/screenshots/`. Do not present wireframes or mockups as evidence of a running system.
- Follow `docs/DEMO_SCRIPT.md` for a short walkthrough.

## Known limitations & future roadmap

- Sample data is synthetic and not validated against a real facility.
- Demand rate is a simple average input, not a statistically validated forecast.
- Live Db2 connectivity still needs environment-specific integration testing.
- Authentication, role-based permissions and production deployment are not included.
- No procurement order is placed and no clinical recommendation is made.

Roadmap: validate calculations with inventory professionals, add role-based access control, evaluate demand forecasting on de-identified data, add supplier integrations, and deploy against a secured Db2 environment.

## Team members & credits

| Name | GitHub | Contribution |
|---|---|---|
| Ayush Kumar Singh | [@DevAyushTech](https://github.com/DevAyushTech) | Project design, backend, Db2 adapter and workflow |
