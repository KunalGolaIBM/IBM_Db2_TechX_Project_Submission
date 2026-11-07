# Deployment

AEGIS is built for local verification first. A public deployment requires a hosted,
privately reachable IBM Db2 instance. A backend running in the cloud cannot reach a
Db2 instance that only listens on a developer's Mac.

## Components

```text
Vercel / static Next.js frontend
        │  NEXT_PUBLIC_API_BASE_URL
        ▼
FastAPI backend (Python 3.11 host or container)
        │
        ├── HTTPS LLM provider (or private Ollama)
        └── IBM Db2 on a private network
```

## Frontend — Vercel

1. Import the repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework preset: Next.js.
4. Set environment variable:

   ```dotenv
   NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com
   ```

5. Deploy. `next.config.mjs` adds basic security headers.
6. Add the Vercel origin to the backend's `AEGIS_CORS_ORIGINS`.

`NEXT_PUBLIC_*` values are embedded at build time; redeploy after changing them.

## Backend

The backend is a standard FastAPI application. Suitable hosts include Render, Fly.io,
Railway, a container platform, or a small VM.

- Root directory: `backend`
- Python: 3.11
- Install: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Health check: `GET /health`
- Database check: `GET /api/db/health`
- Initialize schema once against the hosted Db2:
  `python database/init_db.py --stats`

Required environment variables:

```dotenv
AEGIS_ENV=production
AEGIS_CORS_ORIGINS=https://your-frontend.example.com
DB2_HOST=private-db2-host
DB2_PORT=50000
DB2_DATABASE=TESTDB
DB2_USERNAME=db2inst1
DB2_PASSWORD=...
DB2_SCHEMA=AEGIS

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=...
LLM_BASE_URL=
LLM_TIMEOUT_SECONDS=90
AEGIS_REQUEST_TIMEOUT_SECONDS=600
```

Note: `AEGIS_ENV=production` adds `SECURITY=SSL` to the Db2 DSN. The hosted Db2
endpoint must support SSL. If it does not, use a private network without this flag
(or change the DSN explicitly) and document the decision.

## IBM Db2

For production:

- Use an authenticated Db2 instance managed by IBM Cloud, a private VM, or a managed
  container platform.
- Never expose port 50000 to the public internet.
- Use TLS, private networking/VPC peering, and a least-privilege application user.
- The application user needs access to schema `AEGIS`. `init_db.py` needs permission to
  create the schema and tables, or an administrator must pre-create them.
- Back up the database and restrict who can read `SUBMITTED_TEXT` and passage content.
- Run migrations with `python database/init_db.py --stats`; it adds missing columns and
  indexes idempotently.

## LLM provider

Any OpenAI-compatible chat model can be used. The model receives the submitted research
response and the top-K retrieved passages, not complete documents. Review the
provider's data-retention policy before using confidential research.

For private deployments, point `LLM_BASE_URL` at an internal OpenAI-compatible gateway
or a self-hosted Ollama instance. Do not expose Ollama publicly without authentication.

## What can be deployed as-is

- Frontend to Vercel.
- Backend as a Python service/container.
- Database schema and initialization scripts.

## What is not included

- Authentication, user accounts, or tenant isolation.
- A hosted Db2 instance or credentials.
- Secret manager integration.
- Container image definitions.
- A verified public deployment or public benchmark.

Do not represent a mocked database or a local-only setup as a production integration.
