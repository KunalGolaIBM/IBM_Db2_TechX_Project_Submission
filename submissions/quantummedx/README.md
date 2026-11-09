Demo Link:https://drive.google.com/file/d/1RQ9oRYnIZsjPyf7VkawrUNqG3vQIfYmH/view?usp=sharing
# QuantumMedX

> Agentic hybrid quantum-AI platform: five CrewAI agents run classical ML and a Qiskit variational quantum classifier over healthcare datasets, with IBM Db2 as the system of record for users, datasets, experiments, results, agent activity and reports.

Research and education prototype. It is not a clinically validated diagnostic tool and makes no claim of quantum advantage.

## How it works
1. A researcher registers, logs in and uploads a CSV (validated: extension, 10 MB limit, parse check). Data-quality statistics are stored in Db2.
2. Preprocessing fits imputer, scaler and feature selection on the training split only; the configuration is stored.
3. Logistic Regression, Random Forest and SVM baselines and a Qiskit VQC (local simulator) are trained; metrics, confusion matrix and timings are stored in Db2.
4. Five CrewAI agents (Data Intelligence, Clinical Data Analysis, Classical ML, Quantum ML, Research & Verification) call these backend functions as tools. Each tool call is written to Db2 (`AGENT_ACTIVITIES`).
5. A report is built from stored results. A guardrail checks every number in the agent-written narrative against Db2 and flags anything it cannot match. Only aggregate statistics are given to the LLM, never raw rows.

`DETERMINISTIC` mode runs the same tool pipeline without an LLM; the report states that no LLM was used. `CREWAI` mode requires an LLM key and refuses to start without one.

## IBM Db2 integration
- Edition: Db2 Community Edition (Docker). Driver: `ibm_db` / `ibm_db_dbi`.
- Schema (`database/schema/001_schema.sql`): 10 tables, identity keys, foreign keys with cascades, check constraints, indexes, CLOB columns.
- Connection pool, transactions with rollback, parameterized SQL only, `OFFSET/FETCH` pagination, `IDENTITY_VAL_LOCAL()` inside the insert transaction.
- `/api/system/db-status` performs a real round trip and returns HTTP 503 when Db2 is not configured or reachable.

## Setup
```bash
# 1. Db2
cd database && cp .env.db2.example .env.db2    # set a password
docker compose up -d && docker logs -f quantummedx-db2   # wait for "Setup has completed."

# 2. Backend
cd ../backend && python -m venv .venv && source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp ../.env.example ../.env                     # Windows PowerShell: Copy-Item ../.env.example ../.env
# edit ../.env: set DB2_PASSWORD (same as DB2INST1_PASSWORD in database/.env.db2) and JWT_SECRET (16+ random characters)
# the backend loads ../.env automatically
python scripts/init_db.py
uvicorn app.main:app --reload --port 8000      # API docs at http://localhost:8000/docs
```

### Alternative: run the backend in Docker
If the Windows `ibm_db` driver fails (`SQL1042C`), run the backend in a Linux container (needs `../.env` and `.env.db2` as above, and the `QMEDX` database to exist):
```bash
cd database
docker compose up -d --build
docker compose exec backend python scripts/init_db.py
docker compose exec backend pytest -v
```

## Frontend
```bash
cd frontend && npm install
echo 'VITE_API_URL=http://localhost:8000' > .env.local
npm run dev          # http://localhost:5173
npm test             # UI smoke tests (jsdom)
npm run build        # type-check + production build
```
Try it with `datasets/sample/breast_cancer_wdbc.csv` (target column: `target`). See `datasets/README.md` for the source and licence.

Screens: sign in/register, datasets (upload, data quality, preview, delete), experiments (classical and quantum runs, stored-results table and chart, circuit diagram), AI agents (start run, live activity timeline), reports (verified markdown reports). Every screen reads from the API; empty, loading, error and Db2-unavailable states are shown honestly.

## Testing
```bash
cd backend && pytest -v
```
- `test_ml_core.py`: analysis, leakage-safe preprocessing, classical models and a real VQC run.
- `test_api_logic.py`, `test_agents.py`: API, auth, upload validation, user isolation, agent pipeline and report grounding, run against an in-memory stand-in for the repository (these do not prove Db2 behaviour).
- `test_crew_build.py`: builds the real CrewAI crew (5 agents, 5 tasks, tool wiring) without calling an LLM.
- `test_db2_integration.py`: real Db2 insert/read/delete; skipped unless `DB2_PASSWORD` points at a live Db2.

## Help
`docs/TROUBLESHOOTING.md` covers common Db2 and setup errors. `docs/DEMO_SCRIPT.md` is a 3-minute demo-video script.

## Known limitations
- Binary classification targets only; the VQC uses at most 6 qubits and a small training subset.
- Live CrewAI runs depend on the chosen LLM provider and were not exercised with a real key during development.
- The frontend is deliberately small (5 working screens). It has been type-checked, built and smoke-tested in jsdom; add real screenshots of your own running instance to `docs/screenshots/`.
