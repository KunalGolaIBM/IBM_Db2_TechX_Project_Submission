# Aethel — AI Wellbeing Companion

Aethel is a human-centered wellbeing companion prototype built for IBM Db2Hack 2026. It combines a FastAPI web application, IBM Db2 persistence, and a LangGraph/LangChain conversational workflow. People can save profile preferences, create their own reminders, chat with a supportive companion, and leave public community notes.

> **Important:** Aethel is a prototype, not a medical device or emergency service. It does not diagnose, prescribe, recommend medication/doses, or verify medication ingestion.

## Technology stack

- **Backend:** Python, FastAPI, Pydantic, Starlette sessions
- **Database:** IBM Db2 using the `ibm_db` / `ibm_db_dbi` driver
- **Agentic AI framework:** LangGraph
- **LLM orchestration:** LangChain + `ChatOpenAI`
- **Frontend:** Jinja2, HTML, CSS, vanilla JavaScript
- **Testing:** Python `unittest`, FastAPI `TestClient`, GitHub Actions

## Features

- Private browser-session profile and time-zone preferences
- User-authored pill and wellbeing reminders, with time-zone and daylight-saving validation
- Due-reminder polling while the Companion page is open
- LangGraph contextual analysis followed by a LangChain-generated supportive response
- Conversation history persistence
- Public community feedback board
- Architecture walkthrough and service health endpoints

## Architecture and IBM Db2 usage

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the system flow, LangGraph diagram, table descriptions, and storage-mode boundaries.

The Db2 adapter persists four data groups:

| Db2 table | Stored data |
|---|---|
| `AETHEL_PROFILE` | Session-scoped name, time zone, and check-in preference |
| `AETHEL_TASK` | Reminders, due timestamps, notification claim state, completion status |
| `AETHEL_LOG` | User and assistant conversation turns |
| `AETHEL_REVIEW` | Public community notes |

The FastAPI layer loads profile/history from the configured store, passes them as context into the LangGraph workflow, and persists the resulting conversation turn through the same Db2 adapter. SQL values are parameterized.

**For the hackathon submission, run with `REQUIRE_DB2=true`.** This makes startup fail instead of silently using temporary memory when Db2 is unavailable. The local-memory fallback is intended only for UI development and is not evidence of Db2 persistence.

## Project layout

```text
backend/
  app.py                    # FastAPI routes, validation, sessions, lifecycle
  init_db.py                # Creates Aethel tables in Db2
  companion/
    db.py                   # IBM Db2 adapter + local development fallback
    agent.py                # LangGraph and LangChain workflow
  tests/                    # API and agent tests
frontend/
  templates/                # Home, Companion, Architecture, Community
  static/                   # CSS and browser-side interactions
  assets/                   # Supplied visual assets and architecture diagram
docs/
  ARCHITECTURE.md
  ROUND2_SUBMISSION.md
.github/
  workflows/tests.yml
  PULL_REQUEST_TEMPLATE.md
.env.example                # Safe configuration template; copy to .env
```

## Requirements

- Python 3.10+ (CI currently tests Python 3.11)
- IBM Db2 server/database reachable from the machine running the app
- Db2 user permitted to create tables and read/write the Aethel tables
- OpenAI API key for the live conversational AI feature

## Local setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally. Set your real Db2 host, port, database, username, and password; create a random `SESSION_SECRET` of at least 32 characters; and add `OPENAI_API_KEY` if you want live chat. **Never commit `.env`.**

### Run in Db2 mode (required for Round 2 evidence)

```powershell
# Ensure REQUIRE_DB2=true in .env
python -m backend.init_db
python -m backend.check_db2
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Confirm the database is genuinely active:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected response when Db2 is live:

```json
{"status":"ok","db2":true,"storage_mode":"db2"}
```

Do not submit a screenshot showing `storage_mode: "local"` as Db2 integration proof.

### Run in local UI-development mode only

Set `REQUIRE_DB2=false` and leave Db2 unconfigured. The application can use in-memory storage for UI testing, but all data is lost when the process restarts. The interface reports this as local memory mode.

## Main routes

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/prototype` | Profile, reminders, companion workspace |
| `/architecture` | Interactive architecture walkthrough |
| `/community` | Public community-note board |
| `/api/docs` | Interactive API documentation in development |
| `/api/status` | Service and storage mode status |
| `/api/health` | Health/readiness check |

## API overview

- `GET /api/status`, `GET /api/health`
- `GET /api/profile`, `PUT /api/profile`
- `GET /api/tasks`, `POST /api/tasks`
- `GET /api/reminders/due`, `POST /api/tasks/{task_id}/complete`
- `GET /api/history`, `POST /api/chat`
- `GET /api/reviews`, `POST /api/reviews`

`python -m backend.init_db` creates `AETHEL_PROFILE`, `AETHEL_TASK`, `AETHEL_LOG`, and `AETHEL_REVIEW` in the configured Db2 user's default schema. Run it with a user authorized to create tables.

## Tests

```powershell
python -m unittest discover -s backend\tests -v
```

The LangGraph integration test is skipped when optional AI packages have not been installed. The GitHub Actions workflow installs `requirements.txt` and runs the complete suite. Automated tests use test doubles for application storage; a real Db2 connection must additionally be verified using `/api/health` and an end-to-end profile/reminder round trip as described above.

## Round 2 submission

See [`docs/ROUND2_SUBMISSION.md`](docs/ROUND2_SUBMISSION.md) for the final checklist, evidence requirements, and GitHub fork/pull-request steps. The PR template is at `.github/pull_request_template.md`.

## Reminder onboarding troubleshooting

A reminder requires a saved profile in the same browser session because the profile's IANA time zone is used to interpret the selected local reminder time. If the app says **"Complete onboarding before adding reminders"**:

1. Open `/prototype` and save the name, time zone, and check-in preference in **Profile & preferences**.
2. Wait for the saved confirmation.
3. Add the reminder without switching browser profiles or opening a different hostname for the app.
4. In a multi-worker deployment, configure the same stable `SESSION_SECRET` on every instance.

## Operational and privacy boundaries

- Due reminders are polled every 30 seconds while the Companion page is open; they are not delivered while it is closed. No background scheduler, SMS, or push delivery is implemented.
- There is no account system or cross-device identity linking; the signed browser session scopes private records.
- Community notes are public. A production deployment needs moderation, rate limiting, retention, privacy notices, and a deletion process.
- Before handling real health data, complete a privacy/security and regulatory review and configure Db2 encryption, consent, retention, and access controls.
- Production deployment requires HTTPS, `APP_ENV=production`, `REQUIRE_DB2=true`, `COOKIE_SECURE=true`, a stable high-entropy session secret, trusted `ALLOWED_HOSTS`, and secret management outside source control.
