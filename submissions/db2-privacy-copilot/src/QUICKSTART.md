# Quick Start

This guide starts the demo with real IBM Db2, the FastAPI service, and the
Streamlit UI. The first Docker build downloads large application dependencies
and can take several minutes.

## Requirements

- Docker Desktop running with its Linux container engine and Compose v2
- 8 GB RAM recommended for the local demo; leave several GB of disk space for
  the Db2 image, application images, and build cache
- Python 3.11+ only if you want to run the test suite on your host

On Windows, Docker Desktop manages the Linux container environment. You do not
need to install Ubuntu or set up a separate Linux machine.

## Start the stack

In PowerShell:

```powershell
git clone https://github.com/dreameterftw/db2-privacy-copilot.git
cd db2-privacy-copilot
Copy-Item .env.example .env
notepad .env
```

Set unique values for `DB2_PASSWORD`, `API_SECRET_KEY`, and the three role
tokens (`VIEWER_TOKEN`, `ANALYST_TOKEN`, `DPO_TOKEN`) in `.env`. Keep that file
private; it is excluded from Git. Compose connects the application containers
to Db2 using the service name `db2`.

Build and start all three services:

```powershell
docker compose --profile app up -d
docker compose ps
docker compose logs -f db2
```

Wait until Db2 finishes initialization and the `db2` service is healthy. Then
create the application schema and synthetic demo records:

```powershell
docker compose exec api python -m app.bootstrap
docker compose exec api python -m eval.seed
```

Open:

- Streamlit UI: <http://localhost:8501>
- FastAPI docs: <http://localhost:8001/docs>
- Db2 API health: <http://localhost:8001/healthz>

The health endpoint returns the connected Db2 service level. The seed script
adds 100 synthetic patients and related clinic records. Run it once on a fresh
database; rerunning it adds more rows.

Sign in using a demo persona. Analysts and DPOs can submit requests; the DPO
role can review the stored plan and approve execution from **Rights Requests**.
Approval runs the deterministic SQL guardrail, writes the data change and audit
record in one Db2 transaction, and returns failed requests to pending review.

## Run tests

For host-side tests, install Python dependencies:

```powershell
.\setup.bat
.\.venv\Scripts\Activate.ps1
pytest -q
```

The test suite contains both database-independent tests and Db2 integration
tests. Run the local quality subset in mock mode with:

```powershell
$env:DB_MOCK = "1"
pytest -m "not integration" -q
Remove-Item Env:DB_MOCK
```

For real Db2 integration on Windows, use the Compose app container instead of
the native Windows Db2 driver. The Db2 driver may fail with an IBMOSauthclient
error on Windows even while the same credentials work from the Linux
application container.

## Stop the services

Stop the containers and preserve the database:

```powershell
docker compose --profile app down
```

Delete the Db2 data volume only when you intend to reset the demo database:

```powershell
docker compose --profile app down -v
```

## Troubleshooting

**Db2 is still starting:** inspect `docker compose logs -f db2` and wait for
the health status to become `healthy`. The first initialization takes longer
than later starts.

**A host port is occupied:** set `API_PORT_HOST` in `.env` to an unused port
and recreate the app services. Db2's host port can be changed in
`docker-compose.yml` if port 50000 is already in use.

**Certificate or corrupted package-download errors during Docker build:**
security software with HTTPS inspection can interfere with Docker downloads.
Keep TLS verification enabled. Use the security product's HTTPS scanning
setting or its documented certificate setup; do not add a TLS verification
bypass or commit a workstation-specific root certificate to the project.

**Reset the database:** `docker compose --profile app down -v` removes all
local Db2 data. Start again with `docker compose --profile app up -d`, then
rerun the bootstrap and seed commands.

Compose builds missing images on first start. After source changes, rebuild
with `docker compose --profile app up -d --build`.

For architecture, feature details, and deployment guidance, see
[README.md](README.md) and [deploy/README.md](deploy/README.md).
