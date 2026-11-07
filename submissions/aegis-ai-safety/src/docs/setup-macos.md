# macOS Apple Silicon Setup

This guide is the portable, VS Code-friendly setup for AEGIS. It assumes an existing
local IBM Db2 instance at `localhost:50000` and does not require Conductor.

## 1. Prerequisites

Install:

- **Python 3.11+** (`python3 --version`)
- **Node.js 20.19+** and npm (`node --version`); `.nvmrc` pins `20.19.0`
- **Git**
- Access to **IBM Db2** at `localhost:50000`, database `TESTDB`, user `db2inst1`
- An **OpenAI-compatible LLM** key, or Ollama for a local model

Optional, only if you do not already have Db2:

```bash
brew install podman
podman machine init
podman machine start
```

IBM does not ship a native macOS arm64 Db2 server. Use your existing Db2
container/instance, a remote Db2 host, or the optional `linux/amd64` container below.

## 2. Clone

```bash
git clone https://github.com/sakethdonepudi/aegis-ai-safety.git
cd aegis-ai-safety
```

## 3. Configure environment

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

```dotenv
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=TESTDB
DB2_USERNAME=db2inst1
DB2_PASSWORD=your-existing-db2-password
DB2_SCHEMA=AEGIS
```

Set the LLM values too. Hosted example:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
LLM_BASE_URL=
```

Local Ollama example:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b-instruct
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
```

Next.js reads environment files from `frontend/`, not the repository root. The default
API URL already works for local development. To override it:

```bash
cp frontend/.env.example frontend/.env.local
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`.env` and `frontend/.env.local` are gitignored. Never commit them.

## 4. Install dependencies

```bash
make install
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd frontend
npm install
cd ..
```

If `ibm_db` fails to build, install Xcode Command Line Tools
(`xcode-select --install`) and retry with Python 3.11. The prebuilt wheel normally
works on Apple Silicon.

## 5. Initialize Db2

Verify connectivity:

```bash
nc -vz localhost 50000
```

Create the `AEGIS` schema and six tables:

```bash
make db-init
```

This is idempotent: existing tables and indexes are skipped. If it fails with an
authorization error, use a Db2 user with `CREATE SCHEMA` privilege or have an
administrator create schema `AEGIS` first. If your tables live in another schema, set
`DB2_SCHEMA` in `.env` accordingly.

Seed the synthetic demo evidence (optional):

```bash
make db-seed
```

Load the real-paper demo evidence (optional, downloads two arXiv PDFs):

```bash
make demo-papers
```

### Optional: Db2 container

Only if you do not already have a Db2 instance:

```bash
export DB2_PASSWORD='choose-a-local-password'   # same value as .env
podman run -d --name aegis-db2 --platform linux/amd64 --privileged=true \
  -p 50000:50000 \
  -e LICENSE=accept \
  -e DB2INST1_PASSWORD="$DB2_PASSWORD" \
  -e DBNAME=TESTDB \
  -e ARCHIVE_LOGS=false \
  icr.io/db2_community/db2:12.1.5.0
```

Wait for `(*) Setup has completed.`:

```bash
podman logs -f aegis-db2
```

Then rerun `make db-init`. Under Apple Silicon the amd64 image runs with emulation and
startup can take several minutes.

## 6. Start the application

Run the backend and frontend in **two separate terminals** from the repository root.

### Terminal 1 — FastAPI

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend: <http://localhost:8000>  
API docs: <http://localhost:8000/docs>

Or from the root:

```bash
make dev-backend
```

### Terminal 2 — Next.js

```bash
cd frontend
npm run dev
```

Frontend: <http://localhost:3000>

Or from the root:

```bash
make dev-frontend
```

### Verify

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/db/health
```

`/api/db/health` must report `"connected": true` and all six tables.

## 7. Use AEGIS

1. Open <http://localhost:3000>.
2. Click **Paper demo** to load the real arXiv papers (run `make demo-papers` first) or
   **Synthetic** for the fictional SolarCell-X example.
3. Upload a PDF/TXT/MD evidence document or paste evidence.
4. Click **Verify research claims**.
5. Inspect each claim, its evidence passage, page reference, explanation, numeric
   check, and limitations. Download JSON/Markdown reports or reopen the session from
   **Verification history**.

## 8. Run tests

```bash
make test                 # unit/API tests; Db2 integration skips by default
make test-integration     # full pipeline against the configured Db2
cd frontend
npm run typecheck
npm run lint
npm run build
```

`make test-integration` sets `AEGIS_TEST_DB2=1`; it requires `.env` and an initialized
schema. It uses a scripted LLM, so it does not call a provider.

## 9. VS Code workflow

1. Open the repository folder in VS Code.
2. Run **Python: Select Interpreter** and choose `.venv/bin/python`.
3. Open two terminals.
4. Terminal 1:

   ```bash
   source .venv/bin/activate
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

5. Terminal 2:

   ```bash
   cd frontend
   npm run dev
   ```

No `.vscode` settings are required; the repository is plain Python + Node.js.

## 10. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `DB2_PASSWORD is not configured` | Create `.env` from `.env.example` and set `DB2_PASSWORD` |
| `/api/db/health` returns 503 | Check Db2 is running, port 50000 is open, password matches the existing instance |
| `SQLCODE -551` / authorization | Use a Db2 user that can create schema `AEGIS` and its tables |
| `ModuleNotFoundError: app` | Start Uvicorn from `backend/` as shown above |
| CORS error in the browser | Add your frontend origin to `AEGIS_CORS_ORIGINS` in `.env` and restart the API |
| LLM 401/429/insufficient funds | Check `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, and provider quota |
| Next.js talks to the wrong API | Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` and restart `npm run dev` |
| `ibm_db` segfaults on arm64 | Do not use `exec_immediate` with parameter markers; AEGIS uses prepared statements and frees them |
| Node engine warning | Use Node 20.19+ (`nvm install 20.19.0 && nvm use`) |
| Local model request times out | Raise `AEGIS_REQUEST_TIMEOUT_SECONDS` in `.env` (default 600) or use a smaller/faster model |

## 11. What was not tested in this build environment

- A hosted LLM provider call: the available free quota was exhausted and the paid
  account had insufficient funds. Hosted configuration is implemented but unverified.
- A completely fresh macOS install: dependencies were installed in this workspace,
  not on a clean machine.
- Real PDF upload through the browser: PDF parsing and validation are unit-tested, but
  no real PDF was submitted through the UI.
- Public hosting with a remote Db2 instance.
- Windows/Linux runtime beyond Ubuntu GitHub Actions unit tests.
