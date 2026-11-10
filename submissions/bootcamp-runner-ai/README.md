# Bootcamp Runner: AI CEO Edition

Run the AI world: a lightweight Three.js endless runner where players unlock fictionalized CEO-inspired characters, dodge futuristic hardware, collect coins and AI chips, and chase personal bests.

## Features

- Continuous delta-time 2.5D runner with three lanes, jumping, sliding, collisions, pause/resume, game-over, and replay.
- Five original, fictionalized character interpretations: Sam Altman, Jensen Huang, Elon Musk, Mark Zuckerberg, and Satya Nadella.
- Character unlocks, world unlocks, personal statistics, achievements, missions, combo scoring, and LocalStorage persistence.
- Four themed worlds: Silicon Valley, Neon AI City, AI Data Center, and GPU Factory.
- Keyboard, touch, and responsive mobile controls.
- FastAPI + IBM Db2 backend for player profiles, sessions, scores, unlocks, achievements, missions, leaderboards, and assistant challenges.
- Restricted LangChain tools with optional watsonx.ai execution. Offline gameplay never depends on the backend.

Characters are fictionalized game designs and are not official representations, endorsements, or company products.

## Run locally

```bash
npm install
npm run dev
```

For the optional backend:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r backend/requirements.txt
copy backend\.env.example backend\.env
uvicorn backend.main:app --reload --port 8000
```

Apply `backend/migrations/schema.sql` to a real remote IBM Db2 instance. Do not install a local Db2 server on the development laptop.

## Configuration

Frontend: `VITE_API_URL` may point to the backend. Backend Db2 and watsonx credentials are server-side only; see [backend/.env.example](backend/.env.example). Never commit `.env` files.

Offline mode supports all core running, scoring, unlock, dashboard, and persistence features. Db2-backed sync, global leaderboard data, and watsonx assistant challenges require configured services. Live services are not claimed as verified in this snapshot.

## Testing

```bash
npm test -- --run
npm run build
python -m pytest backend -q
python -m compileall -q backend
```

The browser gameplay was manually checked with the Vite dev server at desktop and mobile viewport sizes, including visible running animation, keyboard movement, jump/slide, touch buttons, pause/resume, collectibles, and game-over/restart.

## Documentation

- [architecture.md](architecture.md)
- [submission.json](submission.json)
- Existing gameplay screenshots: `frame.png`, `scene.png`, and `shot-before.png`.
