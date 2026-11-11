# Db2 Ops Copilot

**Hybrid RAG + guardrailed text-to-SQL copilot over IBM Db2** — built for the
IBM Db2 TechX Summit 2026.

Ask questions in natural language. The copilot either retrieves grounded
answers from a knowledge base stored *inside* Db2 (RAG via `DB2VS` vector
search) or generates **validated, read-only** Db2 SQL — every statement must
pass an AST-based safety gate before it is even shown, and every request is
audited into a Db2 table.

> **Status — M3 work in progress** (branch `feature/m2-core-integrations`):
>
> - **Implemented & offline-tested**: the mock-mode app — chat, SQL
>   validate/execute/EXPLAIN, DBA tools, audit, deterministic allow-listed
>   action proposals, approval API and UI, and mock-only knowledge ingestion.
> - **Implemented but UNVERIFIED** — no live service was ever available on
>   this machine: genuine Db2 / Ollama / `DB2VS` adapters, LangChain
>   orchestration (partial — retrieval legs only), and the Db2 migrations
>   (authored, never executed).
> - **Not implemented:** autonomous LangChain/LangGraph agent execution.
>   Proposal creation is a deterministic, explicitly supplied action batch;
>   privileged execution only follows a human approval and remains disabled
>   by default for real Db2.
>
> Mock mode (the default) runs fully offline with deterministic adapters and
> never fabricates real-service results. See `HANDOFF.md` for full status.

## Quick start (offline — zero services required)

```bash
# 1. Backend (mock mode is the default)
python -m venv .venv && .venv\Scripts\pip install -r requirements-dev.txt
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend (dev server with /api proxy → :8000)
cd frontend
npm install
npm run dev            # http://127.0.0.1:5173
```

Or run the backend only and open **http://127.0.0.1:8000** — it serves the
built frontend automatically when `frontend/dist` exists (`npm run build`).

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness + per-adapter probes (200 even when services are down) |
| `GET /api/v1/status` | Dashboard: database, vector store, LLM, embeddings |
| `GET /api/v1/config` | Effective **non-secret** configuration |
| `POST /api/v1/chat` | Copilot flow (RAG / text-to-SQL, auto-routed) — works in mock mode; in `ADAPTER_MODE=real` it requires the integration stack (`requirements-integration.txt` + live Ollama) and fails closed with 503 otherwise (never falls back to mock data) |
| `POST /api/v1/sql/validate` | The SQL safety gate, exposed for the UI |
| `POST /api/v1/sql/execute` | Validated, row-capped, timed, audited read-only execution |
| `POST /api/v1/sql/explain` | EXPLAIN a validated SELECT (real Db2 plan or labelled mock; graceful fallback) |
| `GET /api/v1/dba/tools` · `POST /api/v1/dba/tools/{id}/run` | Fixed SYSCAT catalog + `MON_GET_*` monitoring tools — [`docs/DBA_TOOLS.md`](docs/DBA_TOOLS.md) |
| `POST /api/v1/agent/propose` | Validate allow-listed action proposals and create pending approvals; never executes them |
| `GET /api/v1/approvals` · `GET /api/v1/approvals/{id}` | List pending approvals or retrieve approval details |
| `POST /api/v1/approvals/{id}/decision` | Explicitly approve/reject; approval execution uses the separate admin gate |
| `POST /api/v1/knowledge/documents` | Bounded mock-mode document ingestion for offline demonstrations |
| `GET /api/v1/ready` | Readiness gate (503 when any probe is not ok) |
| `GET /api/v1/audit` | Recent audit entries |

Interactive docs: http://127.0.0.1:8000/docs · Full contract: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)

### Demonstrate the approval workflow (offline)

1. Start the backend in its default `ADAPTER_MODE=mock` and open
   **http://127.0.0.1:8000** (after `npm run build`) or the frontend dev server.
2. Open **Approvals**, choose RUNSTATS or CREATE INDEX, fill in identifiers,
   and create a proposal. Review its ID and exact statement preview.
3. Reject it, or approve it. Mock mode records a clearly labelled simulation;
   it does not connect to Db2 or execute SQL. The pending list refreshes after
   either decision.
4. The same operations are available in Swagger at **/docs**. Proposal payloads
   accept `actions` with `action_type`, `params`, and `rationale`; action count
   is bounded by `AGENT_MAX_TOOL_CALLS`.

## Architecture at a glance

```
UI (React SPA) → FastAPI /api/v1 → Services → Adapter registry
                                                 ├── mock adapters  (offline, deterministic)
                                                 └── real adapters  (Db2 · Ollama · LangChain)
 every generated SQL ──▶ sqlglot/db2 AST gate (SELECT-only, fail-closed) ──▶ read-only DB account
 every request        ──▶ APP_AUDIT (Db2) / in-memory audit (mock)
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Security defaults documented there too.

## Configuration

Copy `.env.example` to `.env` and fill in locally — **never commit `.env`**
(gitignored and CI-verified). Every variable is documented inline. Key switch:

| Variable | Values | Effect |
|---|---|---|
| `ADAPTER_MODE` | `mock` (default) / `real` | Mock = fully offline, deterministic. Real = genuine Db2 + Ollama adapters (**implemented but unverified** — see status note above) |

## Going real (M2 — on an infrastructure-enabled machine)

1. Install IBM Db2 Community Edition (Docker, `icr.io/db2_community/db2`, ≥ 12.1.2) — see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
2. Install Ollama + pull `granite4.2:3b` and `nomic-embed-text:v1.5`.
3. `pip install -r requirements-integration.txt` (pinned `ibm_db`, LangChain stack).
4. Apply `database/migrations/` in order (see [`database/README.md`](database/README.md)).
5. Set `ADAPTER_MODE=real` in `.env`.

## Testing

```bash
.venv\Scripts\python -m pytest -q                  # 389 passed, 1 skipped (opt-in)
cd frontend && npm run build                      # strict TS + production bundle
```

See [`docs/TESTING.md`](docs/TESTING.md) for the test taxonomy — a green run
proves **offline/mock behavior only**. Real-service integration tests are
opt-in (`@pytest.mark.integration`) and **not verified**: the single existing
one (native-driver dialect load) cannot run on this machine (Application
Control blocks the `ibm_db` DLL), and live Db2/Ollama/DB2VS behavior remains
untested.

Mock knowledge ingestion is implemented through `POST
/api/v1/knowledge/documents`; real Db2/Ollama ingestion is intentionally
disabled until that path is verified. Approvals are in-memory for the running
process (audit transitions are recorded using the configured audit adapter);
they are not durable across restarts.

## Repository layout

```
backend/app/          FastAPI app: api/ core/ services/ agent/ adapters/ security/ schemas/
backend/tests/        Offline test suite (pytest)
frontend/             React 19 + TypeScript + Vite SPA
database/migrations/  Db2 SQL scripts (authored, never executed — real Db2 unverified)
docs/                 Architecture, API contract, development, testing, deployment
```

## License

MIT — see [LICENSE](LICENSE).
