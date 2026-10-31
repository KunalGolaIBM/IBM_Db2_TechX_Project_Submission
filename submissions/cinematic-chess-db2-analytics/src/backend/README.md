# IBM Db2 chess backend

This is a synchronous FastAPI service for the single-user IBM TechX demo. It stores real data in IBM Db2 through `ibm_db`; it never falls back to SQLite or an in-memory database.

## Setup

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt

export DB2_DSN='DATABASE=BLUDB;HOSTNAME=...;PORT=50001;PROTOCOL=TCPIP;SECURITY=SSL;'
export DB2_USER='...'
export DB2_PASSWORD='...'
export DB2_SCHEMA='CHESS'

python -m backend.scripts.init_db
uvicorn backend.app.main:app --reload --port 8000
```

The existing Vite server remains independent at `http://localhost:5173`. CORS defaults to that origin and can be changed with `API_CORS_ORIGINS`.

## API

- `GET /api/v1/health`
- `POST /api/v1/games` (client UUID is the idempotency key)
- `GET /api/v1/games?limit=20&offset=0`
- `GET /api/v1/games/{game_id}`
- `GET /api/v1/analytics/summary`
- `POST /api/v1/coaching`

The server parses PGN and derives move rows itself. A game, its moves, validated analysis, and the opening-statistics projection are committed together. `CHESS_GAMES` is authoritative; rebuild the derived projection with:

```bash
python -m backend.scripts.rebuild_opening_stats
```

Run the reproducible HTTP demonstration after starting the service:

```bash
python -m backend.scripts.demo_api
```

## Optional coaching

Normal gameplay, saved games, and analytics need no LLM package or API key. Coaching defaults to disabled.

For local Ollama:

```bash
pip install -r backend/requirements-llm.txt
export COACH_PROVIDER=ollama
export COACH_MODEL=llama3.2
```

For OpenAI, set `COACH_PROVIDER=openai`, `COACH_MODEL`, and `OPENAI_API_KEY`. Provider imports happen only when the coaching endpoint is called.

## Tests

```bash
pytest -c backend/pytest.ini backend/tests
```

Live Db2 tests are skipped unless `DB2_TEST_DSN` is set. They use `DB2_TEST_USER`, `DB2_TEST_PASSWORD`, and `DB2_TEST_SCHEMA`; they never silently substitute SQLite. Use a disposable schema because integration tests may create and delete test rows.
