# Cinematic Chess 3D – IBM Db2 AI Chess Analytics

> **One-Line Pitch:** Cinematic 3D chess with IBM Db2 saved matches, opening analytics and optional statistics-grounded coaching.

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture (if applicable)](#ai--llm-architecture-if-applicable)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

## Problem Statement

Chess learners need persistent match history and interpretable results across games. This project extends an existing cinematic chess experience with a relational game library and opening analytics.

## Solution Overview

The existing React/Three.js game, animations, chess rules, PGN import/export, heuristic opponent and Stockfish post-game analysis are preserved. The upgrade adds Save Game, My Games, aggregate results, opening statistics and optional coaching. The complete application is included under `src/`; frontend source is `src/src/` and backend is `src/backend/`.

**Live Db2 testing is pending.** Hosted database credentials are not configured. No successful live save, database query or Db2 deployment is claimed.

## IBM Db2 Integration

- **Db2 Edition & Environment:** Hosted IBM Db2, intended target; live verification pending.
- **Connector / Driver Used:** Python `ibm_db`, prepared SQL and bound parameters.
- **Database Schema / Data Models:** Four tables for games/PGN CLOBs, server-parsed moves, per-ply analysis and opening statistics. See [DDL](src/backend/schema.sql).
- **Key Queries & Operations:** Atomic saves, UUID idempotency, rollback, paginated history, result aggregates and ranked openings. Schema identifiers are validated. No SQLite fallback.

## AI / LLM Architecture (if applicable)

Stockfish 18 evaluates positions in a browser worker. The existing playing opponent remains heuristic. Optional LangChain coaching retrieves Db2 statistics and selected-game facts before prompting a configurable Ollama or OpenAI provider. Coaching defaults to disabled; gameplay and persistence require no paid API. Live LLM calls are unverified. No vector-search or autonomous SQL-agent claim is made.

## Tech Stack

- **Backend / Core:** Python 3.11+, FastAPI, Pydantic, python-chess, ibm_db.
- **Database:** IBM Db2.
- **Frontend / UI:** React, TypeScript, Vite, Three.js, React Three Fiber, GSAP, chess.js.
- **Libraries & Tools:** Stockfish, optional LangChain, pytest, Playwright and Node test runner.

## Prerequisites

Node.js 22.12+, npm, Python 3.11+, Playwright Chromium for browser tests, and a Db2 instance with a writable assigned schema. Ordinary gameplay requires no database or LLM.

## Setup & Installation

From the submission repository:

```bash
cd submissions/cinematic-chess-db2-analytics/src
npm ci
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npx playwright install chromium
```

## Configuration

From the application directory above:

```bash
cp ../.env.example .env
chmod 600 .env
```

Fill `DB2_DSN`, `DB2_USER`, `DB2_PASSWORD` and the assigned `DB2_SCHEMA` locally with IBM Cloud service credentials. Use the actual hostname, TLS port and database name. Hosted Free/Lite may permit only the assigned schema. The backend automatically loads `.env`; process variables take precedence. Never commit secrets or put them in `VITE_*` variables.

## Running the Project

```bash
npm run db:init
npm run backend:dev
# Second terminal, same application directory:
npm run dev
```

Frontend: http://localhost:5173. Backend: http://localhost:8000. OpenAPI: http://localhost:8000/docs. Allowed browser origins use `API_CORS_ORIGINS`.

## Testing & Verification

```bash
npm run test:unit
npm run test:backend
npm run test:browser
npm run build
# Requires a configured, initialized real Db2 database and running backend:
npm run demo:api
```

Verified in the source workspace: 9 frontend tests passed; 19 backend tests passed and 2 live Db2 checks skipped; production build passed with the existing large Three.js bundle warning; browser gameplay smoke completed four player moves. After correcting the Stockfish WASM path and stale timer, a real Chromium check evaluated nine positions at depth 10 without browser errors. A fresh-install run of this packaged copy is pending.

The two live tests require `DB2_TEST_DSN`, `DB2_TEST_USER`, `DB2_TEST_PASSWORD`, and `DB2_TEST_SCHEMA`; they check connectivity and table presence. The HTTP demo writes a real game, repeats its UUID, retrieves history and queries analytics. Neither has passed against a live Db2 instance. SQL/CLOB behavior, persistence, rollback, duplicates and UI reload remain unverified.

Official structural validation, from submission repository root:

```bash
python3 scripts/validate_submission.py submissions/cinematic-chess-db2-analytics
```

## Screenshots & Demo

- **Live Demo Link:** https://cinematic-chess-game3d.vercel.app/ — original gameplay only; does not demonstrate the Db2 upgrade.
- **Demo Video Link:** Not available.
- **Project repository:** https://github.com/srjay999-giT/cinematic-chess-game3D
- Existing gameplay screenshots: [src/assets/screenshots](src/assets/screenshots). These are not evidence of live Db2 functionality.

## Known Limitations & Future Roadmap

Live Db2 verification and updated deployment are pending. This single-user demo has no authentication or tenant isolation. Optional coaching needs separately installed provider packages and a running/configured provider. Opening recognition covers a limited repertoire. Next steps are live database verification, deployment, a recorded database demo and authentication before multi-user hosting.

## Team Members & Credits

**Team:** Cinematic Chess AI — individual submission.

| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Jay K. Gadage | [@srjay999-giT](https://github.com/srjay999-giT) | Game, frontend, Db2 backend and analytics |

Public email intentionally omitted. Original application copyright/distribution terms remain in [src/README.md](src/README.md). Stockfish is GPLv3; see [COPYING.txt](src/public/engine/COPYING.txt) and upstream source https://github.com/nmrugg/stockfish.js (npm stockfish 18.0.8). Other dependencies retain their respective licenses.
