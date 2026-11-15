# Odyssey - Db2-powered productivity planning

> **One-Line Pitch:** Odyssey turns a brain dump into a focused next action, with optional LangChain planning and IBM Db2 persistence for captured work.

## Problem Statement

People often have tasks, deadlines, and habits scattered across notes. Odyssey is for students and knowledge workers who need to convert that context into a practical plan without losing the underlying capture.

## Solution Overview

The React/Vite application provides the Capture -> Understand -> Plan -> Execute workflow. Its existing deterministic planner works offline, while the submission adds a Python integration service that:

1. Parses a capture into structured tasks.
2. Uses a LangChain prompt/model chain when an OpenAI-compatible API key is configured.
3. Persists captures and task metadata in IBM Db2 with parameterized `ibm_db` statements.
4. Falls back to deterministic priority ordering when no model key is configured.

## IBM Db2 Integration

- **Environment:** IBM Db2 Community Edition or a Db2 instance with TCP/IP access.
- **Connector:** Python `ibm-db` driver.
- **Schema:** `backend/schema.sql` creates `ODYSSEY_TASKS`, storing the original capture, task title, category, priority, and timestamps.
- **Operations:** `Db2TaskStore.save_capture()` uses a prepared INSERT statement; no credentials or user input are interpolated into SQL.

## AI / LLM Architecture

- **Framework:** LangChain Core and `langchain-openai`.
- **Model:** Any configured OpenAI-compatible chat model, defaulting to `gpt-4o-mini`; an IBM watsonx-compatible endpoint can be supplied through `OPENAI_BASE_URL`.
- **Workflow:** `ChatPromptTemplate -> ChatOpenAI -> StrOutputParser`. Without `OPENAI_API_KEY`, the same task list is planned deterministically so the workflow remains usable offline.

## Tech Stack

- React 19, TypeScript, Vite, Tailwind CSS
- Python 3.10+, LangChain, `ibm-db`, python-dotenv
- IBM Db2

## Prerequisites

- Node.js 20+ and npm for the web application
- Python 3.10+ for the Db2/LangChain service
- Optional: a reachable IBM Db2 instance and an OpenAI-compatible model endpoint

## Setup & Installation

### Web application

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

### Db2/LangChain service

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Apply `backend/schema.sql` in the target Db2 database. Fill in the Db2 values in `backend/.env`; keep the password local.

## Running the Project

From `backend`, preview a plan without external services:

```powershell
python -m src.odyssey_db2 "Finish report, email mentor, practice DSA"
```

Persist the parsed tasks in Db2:

```powershell
python -m src.odyssey_db2 "Finish report, email mentor" --save
```

The web UI continues to use its existing Supabase configuration for authentication and application persistence. The Db2 service is independently runnable for the hackathon integration demonstration.

## Testing & Verification

```powershell
cd backend
python -m unittest discover -s tests -p "test_*.py"
cd ..
npm test
npm run build
python ..\..\scripts\validate_submission.py .
```

The Python tests cover parsing, priority ordering, and LangChain prompt input without requiring Db2 credentials or a model API key.

## Known Limitations & Future Roadmap

- The Db2 service currently persists captures but does not yet expose an HTTP endpoint to the React client.
- The default model adapter is OpenAI-compatible; a first-class watsonx adapter and authenticated API route are natural next steps.
- Future work can query historical captures from Db2 to improve recurring-goal recommendations.

## Team Members & Credits

| Name | GitHub Handle | Role |
|---|---|---|
| Vi-kaash | [@Vi-kaash](https://github.com/Vi-kaash) | Application, LangChain, and Db2 integration |

## License

Apache-2.0. See [LICENSE](LICENSE).
