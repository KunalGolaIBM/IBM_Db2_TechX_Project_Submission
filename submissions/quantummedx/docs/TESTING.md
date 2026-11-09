# Testing status

| Area | How it is tested | Status when last run |
|---|---|---|
| Data analysis, preprocessing (train-only fit), classical models, real Qiskit VQC run | `backend/tests/test_ml_core.py` | passed |
| API routes: auth, rate limit, upload validation, user isolation, training, comparison | `backend/tests/test_api_logic.py` (in-memory stand-in for the repository) | passed |
| Agent pipeline, activity logging, report grounding, number verifier, CrewAI mode refusal without a key | `backend/tests/test_agents.py` (in-memory stand-in) | passed |
| CrewAI crew construction: 5 agents, 5 sequential tasks, tool wiring | `backend/tests/test_crew_build.py` (no LLM call) | passed |
| Frontend render smoke tests | `frontend/npm test` (jsdom, mocked API) | passed |
| Frontend type-check and production build | `frontend/npm run build` | passed |
| Official submission validator | `python scripts/validate_submission.py submissions/quantummedx` | passed |
| **Real Db2: insert, read, delete, health check** | `backend/tests/test_db2_integration.py` | **skipped unless a live Db2 is configured; record your own run below** |
| **Live CrewAI run with a real LLM** | manual: `POST /api/agents/run` with mode `CREWAI` | **record your own run below** |

The in-memory tests prove application logic only. They are not evidence of Db2 behaviour.

## Your run log (fill in before submitting)
- Db2 version/image and date:
- `python scripts/init_db.py` output:
- `pytest tests` summary on your machine:
- CrewAI run: provider/model, run id, report status:
