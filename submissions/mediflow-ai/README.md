# MediFlow AI

> **One-line pitch:** MediFlow AI helps hospital and pharmacy inventory teams spot medicine stockout and batch-expiry risks, then prepare explainable reorder drafts backed by IBM Db2 records and a LangGraph workflow.

## Problem statement

Hospitals, clinics and pharmacies often manage medicine stock across disconnected spreadsheets, billing exports and supplier records. A stock count alone does not show whether current stock can last until the next delivery, which batches may expire soon, or what quantity should be considered for replenishment. Inventory managers need an auditable view of risk and a clear rationale for proposed action. MediFlow AI is an operational decision-support prototype; it is not a clinical system and does not make treatment recommendations.

## Solution overview

The application reads medicine, inventory, batch, usage and supplier lead-time records. Its workflow calculates estimated days of cover, detects stockout and expiry exposure, drafts a suggested reorder quantity with supporting reasons, and waits for a named human reviewer to approve or reject it. No order is sent to a supplier.

Core capabilities:
- Inventory snapshot with stock, daily usage, supplier lead time and expiry exposure.
- Stockout risk when estimated cover falls below supplier lead time plus a three-day buffer, or stock is below reorder level.
- Near-term expiry flags for batches expiring within 30 days.
- Draft reorder quantity based on a target coverage window.
- Human review boundary and an approval-event audit trail.
- Explicit synthetic-data demo mode and configurable Db2 mode.

## IBM Db2 integration

- **Edition/environment:** IBM Db2 Community Edition using IBM's official Docker image `icr.io/db2_community/db2`. This is the intended local development/test environment; the container must be started on the developer/reviewer's machine.
- **Connector:** Python `ibm_db` driver with bound SQL parameters.
- **Tables:** `MEDICINES`, `SUPPLIERS`, `INVENTORY`, `BATCHES`, `USAGE_HISTORY`, `RECOMMENDATIONS`, and `APPROVAL_EVENTS`.
- **Operations:** Read inventory and batch data; insert workflow recommendations; update review status; append review/audit events.
- **Setup:** See `docs/DB2_SETUP.md` and `src/db/schema.sql`.

The default `DATA_BACKEND=demo` uses clearly labelled synthetic in-memory records. Set `DATA_BACKEND=db2` only after the local Db2 container is running, the schema is initialised and seed rows have been inserted. The live adapter is included but has not yet been verified against a running Db2 instance.

## AI / LLM architecture

- **Framework:** LangGraph state graph.
- **MVP model strategy:** Deterministic Python risk and reorder calculations; no external LLM is called in this version.
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
- Docker Desktop with the Linux container engine enabled (or Docker Engine in Linux/WSL2).
- For Db2 mode: at least 4 GB RAM available to the Db2 container and sufficient free disk space for the image and database volume.
- IBM Db2 Community Edition Docker image is intended for non-production development/testing.

## Setup & installation

```powershell
cd submissions/mediflow-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a strong local `DB2_PASSWORD`. Do not commit `.env`.

## Configuration

For synthetic demo mode, keep `DATA_BACKEND=demo`.

For Db2 mode, set:
- `DATA_BACKEND=db2`
- `DB2_HOST=127.0.0.1`
- `DB2_PORT=50000`
- `DB2_DATABASE=MEDIFLOW`
- `DB2_USER=db2inst1`
- `DB2_PASSWORD` to the same local password used by the Db2 container
- `DB2_SECURITY=false` for the local non-TLS development container

## Running the project

### Start IBM Db2 Community Edition

From this project directory, after Docker Desktop is running and `.env` has been configured:

```powershell
docker compose -f docker-compose.db2.yml up -d
docker logs -f mediflow-db2
```

Wait for the Db2 setup-complete message before proceeding. Initial startup can take several minutes.

### Initialise schema and seed test data

```powershell
python -m src.db.init_db
```

Then follow the synthetic seed SQL instructions in `docs/DB2_SETUP.md`.

### Start the application

```powershell
streamlit run src/ui.py
```

Start the API in a second terminal:

```powershell
uvicorn src.api:app --reload --port 8000
```

API endpoints: `GET /health`, `GET /inventory`, `POST /recommendations/run`, and `POST /recommendations/{id}/review`.

## Testing & verification

```bash
python -m pytest -q
```

The included unit tests cover stockout/expiry assessment, recommendation draft status and the demo repository review boundary. They do not prove connectivity to a live Db2 server. Test database reads and writes separately against the local Db2 container before claiming live Db2 verification.

## Screenshots & demo

- Live deployment: not deployed.
- Demo recording: not recorded.
- Capture genuine UI screenshots after running the app and save them under `docs/screenshots/`.
- Follow `docs/DEMO_SCRIPT.md` for a short walkthrough.

## Known limitations & future roadmap

- Sample data is synthetic and not validated against a real facility.
- Demand rate is a simple average input, not a statistically validated forecast.
- Live Db2 connectivity still needs environment-specific integration testing.
- Authentication, role-based permissions and production deployment are not included.
- No procurement order is placed and no clinical recommendation is made.

Roadmap: validate calculations with inventory professionals, add role-based access control, evaluate demand forecasting on de-identified data, add supplier integrations, and deploy against a secured Db2 environment.

## Individual contributor

| Name | GitHub | Contribution |
|---|---|---|
| Ayush Kumar Singh | [@DevAyushTech](https://github.com/DevAyushTech) | Individual project: design, backend, Db2 adapter and workflow |
