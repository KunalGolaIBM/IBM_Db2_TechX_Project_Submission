# Bootcamp Runner AI

Bootcamp Runner AI is an adaptive educational endless runner. Players answer quiz questions through a fast three-lane game, while a FastAPI agent analyzes saved performance in IBM Db2 and recommends the next topics and difficulty.

## Features

- Procedural Three.js 2.5D runner with keyboard and touch controls.
- Explore and Flow modes, three difficulties, characters, lives, coins, streaks, and JSON question-pack import.
- Db2-backed learner history, quiz attempts, topic profiles, and AI recommendations.
- LangChain tools for retrieving history, analyzing topics, recommending difficulty, generating practice guidance, and saving recommendations.
- Learning dashboard and adaptive Flow sessions.
- Explicit offline mode: the game remains playable when the backend or Db2 is unavailable.

## Stack

- Frontend: React, TypeScript, Vite, Three.js, lucide-react.
- Backend: Python, FastAPI, Pydantic, LangChain.
- Database: IBM Db2 through `ibm_db`.
- Model provider: IBM watsonx.ai when configured; deterministic fallback is marked as offline and is used only when no model configuration exists.

## Run locally

### Frontend

```bash
npm install
npm run dev
```

Set `VITE_API_URL` if the backend is not running on `http://localhost:8000`.

### Backend

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r backend/requirements.txt
copy backend\.env.example backend\.env
uvicorn backend.main:app --reload --port 8000
```

Configure a real remote IBM Db2 instance and watsonx.ai credentials in the untracked `.env`. Do not run or install a local Db2 server for this lightweight project. Apply `backend/migrations/schema.sql` to the configured Db2 database before using database-backed features.

## Environment

The backend reads Db2 and model credentials only from environment variables. The frontend receives only the API base URL; Db2 credentials never enter the browser. See [backend/.env.example](backend/.env.example).

## Testing

```bash
npm test -- --run
npm run build
python -m pytest backend/tests -q
python -m compileall -q backend
```

The checked-in tests cover game rules, API validation, parameterized repository calls, agent tools, and explicit database failure handling. Live Db2 and watsonx verification requires the operator's configured remote services and is not claimed by this repository snapshot.

## Screenshots

Existing gameplay screenshots are retained in the project root: `frame.png`, `scene.png`, and `shot-before.png`.

## Submission

The official Db2Hack submission metadata and architecture documentation are maintained alongside this source in [submission.json](submission.json) and [architecture.md](architecture.md).
