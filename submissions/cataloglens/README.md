# CatalogLens
### Agentic Intelligence for Undocumented IBM Db2 Databases

CatalogLens helps developers understand enterprise database schemas by analyzing Db2 catalog metadata and presenting tables, columns, constraints, relationships, and database structure through an interactive interface.

## Problem
Enterprise databases often contain undocumented schemas. Understanding table structures and relationships manually can be time-consuming and error-prone.

## Solution
- Explore database schemas and tables.
- Inspect column types, primary keys, constraints, and indexes.
- Discover declared foreign-key relationships.
- Identify potential relationships using heuristics.
- Separate verified database facts from inferred candidates.

## Technology Stack
- IBM Db2 Community Edition
- Python and ibm_db
- FastAPI
- Streamlit
- LangGraph
- NetworkX and Plotly

Anthropic Claude is optional. Deterministic heuristic reasoning is available when no Claude API key is configured.

## Database
- Database: CATALOG
- Schema: ENTERPRISE
- Connection mode: Live Db2 (`DEMO_MODE=false`)
- Database records are synthetic sample data.

## Setup

Create an environment and install dependencies:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install ibm_db

Configure your local `.env` using `.env.example`. Never commit database passwords or API keys.

## Run

Start the backend:

    python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001

Start the frontend in another terminal:

    BACKEND_URL=http://127.0.0.1:8001 python3 -m streamlit run frontend/app.py --server.address 0.0.0.0 --server.port 8501

Open http://localhost:8501.

## Tests

    python3 -m pytest -q

## Screenshots

See `docs/screenshots/`.

## Evidence and limitations

Declared relationships come from Db2 foreign-key metadata. Inferred relationships are heuristic candidates and require manual verification; they are not confirmed database constraints.
