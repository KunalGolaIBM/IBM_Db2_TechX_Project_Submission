# Db2 Privacy Copilot

> **Find personal data in IBM Db2, plan privacy actions, and keep people in control of approval.**

Db2 Privacy Copilot is a working privacy-operations demo for teams that use IBM Db2. It brings database discovery, personal-data classification, consent history, and data-removal planning into one web application. AI-assisted tools can suggest what to review; deterministic guardrails and human approval control sensitive execution.

## The problem

Personal information can be spread across related database tables. Privacy teams need to know where it is, whether consent applies, and which records may need action when a person makes a rights request. Doing this by hand can be slow and make decisions harder to explain or audit.

## The solution

The application connects directly to Db2, maps tables and foreign-key relationships, and identifies columns that may contain personal data. It supports consent records, dry-run erasure plans, SQL safety checks, and an audit trail so a reviewer can understand a proposed action before it is approved.

## Features

- **Discover a schema:** Read Db2 catalog metadata and map tables, columns, and foreign-key relationships.
- **Identify personal-data candidates:** Combine value-pattern checks with semantic matching of column names to privacy labels.
- **Track consent over time:** Store consent with business-time and system-time history.
- **Plan data-rights actions:** Build reviewable erasure or anonymisation plans using relationship and retention context.
- **Check proposed SQL:** Apply deterministic checks for unsafe statements, missing filters, and tables outside the approved plan.
- **Record actions:** Store events in a SHA-256 hash-linked audit log and verify the chain.

Agents are planning assistants. They do not receive an erasure-execution tool. A sensitive action requires an authorized human approval and passes the deterministic guardrail before execution.

## IBM Db2 integration

The demo runs against IBM Db2 Community Edition in Docker. The Python connector (`ibm_db` and `ibm_db_dbi`) handles database connections. The app reads Db2 catalog views to discover schema metadata and stores clinic records, consent history, requests, PII classifications, retention rules, and audit events in Db2 tables.

For semantic classification, LangChain's `langchain-db2` integration uses Db2's DB2VS vector store to compare column-name embeddings with privacy-taxonomy labels. Sentence Transformers creates embeddings locally. This vector workflow requires Db2 12.1.2 or newer. The local demo was verified with Db2 12.1.5.0.

## Technology

- Python 3.11+, SQL
- Streamlit UI and FastAPI REST API
- IBM Db2 Community Edition, `ibm_db`, `ibm_db_dbi`
- CrewAI planning agents; LangChain and `langchain-db2` / DB2VS
- Sentence Transformers, NetworkX, pytest, Ruff
- Docker and Docker Compose

## Setup and run (Windows with Docker Desktop)

Docker Desktop provides the Linux-container environment used by the Db2 and Python images. You do not need to install Ubuntu separately. The first image build downloads large dependencies and may take several minutes and multiple gigabytes of disk space.

From this submission folder, create a local environment file and set unique values for `DB2_PASSWORD` and `API_SECRET_KEY`:

```powershell
Copy-Item .env.example src/.env
notepad src/.env
```

Keep `src/.env` private; never commit it. Start the stack from `src`:

```powershell
Set-Location src
docker compose --profile app up -d
docker compose ps
docker compose logs -f db2
```

Wait for Db2 to finish initialization and become healthy. Then create the application schema and synthetic clinic data:

```powershell
docker compose exec api python -m app.bootstrap
docker compose exec api python -m eval.seed
```

Open the Streamlit workspace at <http://localhost:8501>. API docs are at <http://localhost:8001/docs>; <http://localhost:8001/healthz> reports the connected Db2 version. Seeding adds 100 synthetic patients and related records. Run it once on a fresh database; each run adds more rows.

Stop the stack while preserving database data with `docker compose --profile app down`. To delete the local demo database too, use `docker compose --profile app down -v`.

## Testing

For database-independent tests on Windows, install the development environment from `src` and run the mock-mode quality subset:

```powershell
Set-Location src
.\setup.bat
.\.venv\Scripts\Activate.ps1
$env:DB_MOCK = "1"
pytest -m "not integration" -q
```

Real Db2 connectivity was tested through the Linux application container because the native Windows Db2 driver can fail with an IBMOSauthclient authentication error even when the same credentials work from the container. During preparation, the API health endpoint returned Db2 12.1.5.0 and the Streamlit page returned HTTP 200.

## Limitations

- This is a prototype for selected privacy workflows, not legal advice or a complete compliance solution.
- Demo sign-in roles are not production-grade identity and access management.
- Retention rules start as unverified and must be reviewed by qualified owners.
- Use only synthetic demo data; do not point this setup at production or real personal or health data.
- No public demo URL or video is included.

## Source layout

The application and tests are in [src/](src/). See [architecture.md](architecture.md) for the component diagram and Db2 data flow. The project is distributed under the MIT License; see [src/LICENSE](src/LICENSE).

