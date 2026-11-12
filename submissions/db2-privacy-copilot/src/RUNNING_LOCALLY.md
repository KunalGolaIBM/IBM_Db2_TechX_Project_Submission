# Running Locally

## Recommended application setup

The standard local application uses real IBM Db2, the FastAPI service, and the Streamlit workspace through Docker Compose. On Windows, use Docker Desktop with its Linux container backend.

Follow [QUICKSTART.md](QUICKSTART.md) to configure `.env`, start the three services, initialize the schema, and load synthetic clinic records. Compose explicitly sets `DB_MOCK=0` for the application containers. The application should fail clearly if the Db2 driver is unavailable rather than silently presenting an in-memory backend as a real database connection.

## Check the running services

```powershell
docker compose --profile app ps
docker compose logs --tail 80 db2
docker compose logs --tail 40 api
```

Open the UI at <http://localhost:8501>. Check <http://localhost:8001/healthz> and confirm it reports the Db2 service level before describing the session as connected to Db2.

## Verification

The latest successful GitHub Actions CI run verified both the quality job and live Db2 integration job for commit `be74dc2` on Nov 10, 2026. See [the run](https://github.com/dreameterftw/db2-privacy-copilot/actions/runs/42799280571). This run does not cover later local changes.

## Tests

Use the repository CI workflow as the authoritative live Db2 integration result. For host-side unit tests, install the development dependencies and explicitly set `DB_MOCK=1` for database-independent tests. That backend is only for tests and local development; it is not a Db2 connection and should never be presented as one.
