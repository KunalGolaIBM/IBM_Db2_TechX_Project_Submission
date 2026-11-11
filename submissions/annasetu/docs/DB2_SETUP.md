# IBM Db2 setup

AnnaSetu uses IBM Db2 as its only operational database. FastAPI connects through IBM's `ibm-db` driver; there is no SQLite fallback. Run the API from the project root so it reads the root `.env` file.

## Local requirements

- Windows 11 with Docker Desktop using the WSL 2 Linux engine.
- Docker Compose v2.
- Python 3.11 or 3.12 (64-bit) and Node.js 20.19+ or 22.12+.
- 8 GB RAM available to the Db2 Community container; first startup can take several minutes.

## Configure and start Db2

From `C:\Users\mr.rajat\Desktop\AnnaSetu` in PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` locally. Set `DB2_PASSWORD` to the local Db2 instance password, `JWT_SECRET` to a random value of at least 32 characters, and a private `DEMO_PASSWORD` for the local ANNASETU demo accounts. Use a separate password in ignored `.env.qa` for ANNATEST. Existing production accounts are not reset on ordinary startup; if the private password changes, update only the reserved demo hashes through an explicitly authorized maintenance action. Do not commit local environment files or copy their values into logs or screenshots.

Start the existing Db2 service and wait for its health check:

```powershell
docker compose up -d db2
docker compose ps
docker compose logs -f db2
```

The Compose service uses IBM Db2 Community Edition 12.1.5.0, publishes port 50000, and persists database files in the `annasetu-db2-data` volume. Do not use `docker compose down -v` if the local database should be retained; `-v` removes the persistent database volume.

To check the active database from the container without printing a password:

```powershell
docker exec annasetu-db2 su - db2inst1 -c 'db2 connect to ANNASETU'
docker exec annasetu-db2 su - db2inst1 -c 'db2 "values current server"'
```

Set `DB2_NAME` in `.env` if the API should target a different database. The database name configured for the API must already exist in the container.

## Start FastAPI and the frontend

Install backend packages once:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r api\requirements.txt
```

Start the existing Db2 container, FastAPI, and Vite together from the project root:

```powershell
.\start-annasetu.ps1
```

The launcher targets operational `ANNASETU`, reuses `annasetu-db2`, starts FastAPI at `127.0.0.1:8010` and Vite at `127.0.0.1:5175`, and writes logs to `logs\`. It will not stop an unverified process occupying a required port. The API creates missing tables, indexes, and append-only triggers without dropping tables or resetting rows. A fresh database receives its configured sample dataset. An existing `ANNATEST` repairs only the four reserved demo identities; existing non-QA user rows and operational records are left unchanged. Vector readiness is reported separately.

Check the active Db2 database and vector readiness at `http://127.0.0.1:8010/api/health`; API docs are at `http://127.0.0.1:8010/docs`. Open the dashboard at `http://127.0.0.1:5175`.

For manual development startup only, from the project root:

```powershell
python -m uvicorn api.app.main:app --host 127.0.0.1 --port 8010
```

From `frontend`, run `npm run dev -- --host 127.0.0.1 --port 5175`. Vite defaults to `http://127.0.0.1:8010/api`; never put credentials in a Vite variable because frontend variables are included in the browser bundle.

## Isolated integration-test database

The live integration suite refuses to run unless `DB2_NAME=ANNATEST`. `ANNATEST` already exists in this workspace; create it only on a new Db2 installation where the database catalog confirms it is absent:

```powershell
docker exec annasetu-db2 su - db2inst1 -c 'db2 create database ANNATEST'
$qa = @{}
Get-Content .env.qa | ForEach-Object { if ($_ -match '^(DB2_NAME|DEMO_PASSWORD)=(.*)$') { $qa[$Matches[1]] = $Matches[2] } }
$env:DB2_NAME = $qa['DB2_NAME']
$env:DEMO_PASSWORD = $qa['DEMO_PASSWORD']
$env:ANNASETU_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest api\tests -q -rs
Remove-Item Env:DB2_NAME,Env:DEMO_PASSWORD,Env:ANNASETU_INTEGRATION
Remove-Variable qa
```

Integration cases use `SYNTHETIC QA` food and NGO names. They never point at `ANNASETU` and never delete records. They leave QA rows in `ANNATEST`; run against a dedicated disposable test database when a clean baseline is needed. Do not put a real donation or beneficiary record in a test run.

## Environment variables

| Variable | Purpose | Example in `.env.example` |
|---|---|---|
| `DB2_HOST`, `DB2_PORT` | Db2 host and DRDA port | `127.0.0.1`, `50000` |
| `DB2_NAME` | Active database | `ANNASETU` |
| `DB2_USER`, `DB2_PASSWORD` | Db2 instance user and local password | `db2inst1`, placeholder only |
| `JWT_SECRET` | Signs API bearer tokens; use a unique 32+ character random value | placeholder only |
| `DEMO_PASSWORD` | Private local demo password; QA uses a separate value from ignored `.env.qa` | local secret |
| `JWT_EXPIRE_MINUTES` | Token lifetime | `720` |
| `ENVIRONMENT` | Enables development-only demo-account listing | `development` |
| `SEED_DEMO_DATA` | Seeds a full sample dataset on an empty database; ensures only the reserved demo users on an existing `ANNATEST` | `true` |
| `CORS_ORIGINS` | Explicit browser origins allowed by FastAPI | localhost and 127.0.0.1 Vite origins |
| `VITE_API_BASE` | Optional frontend API root; never store credentials here | `http://127.0.0.1:8010/api` |

The checked-in `.env.example` is the environment-variable source of truth for the backend. Keep generated secrets and live values local.
