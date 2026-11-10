# IBM Db2 Setup (Windows)

AnnaSetu uses IBM Db2 as the only operational database. FastAPI connects directly using IBM's `ibm-db` / `ibm_db_dbi`; there is no SQLite fallback. LangChain's Db2 vector store uses the same Db2 service.

## Prerequisites

- Windows 11, Docker Desktop with WSL 2 Linux engine, Docker Compose v2.
- 64-bit Python 3.11 or 3.12 and Node.js 20.19+ or 22.12+ with npm.
- At least 8 GB of memory available to Db2.

## Configure

From the repository root:

```powershell
Set-Location submissions\annasetu\src
Copy-Item ..\.env.example .env
notepad .env
```

Set a private `DB2_PASSWORD`, a random `JWT_SECRET` of at least 32 characters and a private `DEMO_PASSWORD`. Set `DB2_NAME=ANNASETU` for the operational demo database. The example file contains placeholders only. Never commit `src\.env`, paste secret values in issue comments, or place credentials in `VITE_*` frontend variables.

## Start Db2 and install dependencies

From `submissions\annasetu\src`:

```powershell
docker compose up -d db2
docker compose ps
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r api\requirements.txt
npm ci --prefix frontend
```

Wait until container `annasetu-db2` is healthy. First startup can take several minutes. Compose creates/reuses the `ANNASETU` database and keeps files in Docker volume `annasetu-db2-data`. The API initializes missing schema objects; it does not drop or reset the database. Do not use `docker compose down -v` when retaining the Db2 data is important.

## Start and verify the application

```powershell
.\start-annasetu.ps1
```

The launcher targets `ANNASETU`, starts FastAPI at `127.0.0.1:8010` and Vite at `127.0.0.1:5175`, and writes logs to `src\logs\`. Open `http://127.0.0.1:5175`. The health endpoint executes a database query and returns the actual active Db2 database name and vector readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
Invoke-RestMethod http://127.0.0.1:8010/api/policy/status
```

OpenAPI docs: `http://127.0.0.1:8010/docs`.

## Isolated live integration tests

Use a dedicated Db2 database called `ANNATEST`, not `ANNASETU`. The current project report records a live run on `ANNATEST`; on a new installation create that QA database only after verifying it is absent. Preserve a private local QA `DEMO_PASSWORD`. To run tests, temporarily set `DB2_NAME=ANNATEST` in `src\.env`, then:

```powershell
Set-Location submissions\annasetu\src
$env:ANNASETU_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest api\tests -q -rs
Remove-Item Env:ANNASETU_INTEGRATION
```

The suite checks that its configured target is exactly `ANNATEST` and refuses to run against operational `ANNASETU`. It uses `SYNTHETIC QA |` batch labels and synthetic partner data. It appends test rows to ANNATEST and does not delete records; for repeatable runs, use a dedicated disposable QA database. Restore `DB2_NAME=ANNASETU` before using `start-annasetu.ps1`.

## Environment variables

| Variable | Purpose |
|---|---|
| `DB2_HOST`, `DB2_PORT` | Db2 address; local Compose uses `127.0.0.1:50000`. |
| `DB2_NAME` | Database name, normally `ANNASETU`; integration test target must be `ANNATEST`. |
| `DB2_USER`, `DB2_PASSWORD` | Db2 account and private local password. |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | Token signing key (32+ random characters recommended) and token lifetime. |
| `DEMO_PASSWORD` | Private local password for reserved demo identities on a fresh seed. |
| `ENVIRONMENT` | Runtime mode; development enables the restricted demo-account selector. |
| `SEED_DEMO_DATA` | Whether the API seeds sample data on a fresh database. |
| `CORS_ORIGINS` | Explicit local frontend origins allowed by FastAPI. |
| `VITE_API_BASE` | Optional browser API base URL; contains no credentials. |

## Database scope and limitations

`ANNASETU` and `ANNATEST` are database names, not schemas. Select the database before starting FastAPI and verify it in `/api/health`. The checked-in Compose configuration persists Db2 data. Keep backups outside this submission package. Db2 Community Edition and the single-node local setup are for development and demonstration, not a high-availability deployment.
