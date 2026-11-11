# Tests

Tests live next to the code they cover:

- `src/backend/tests/` — pytest (database integrity, Db2 recursive genealogy acceptance, impact analysis, risk, agents incl. CrewAI kickoff, verification, API, approval workflow, ibm_db driver handling). Run: `cd src/backend && pytest -q`
- `src/frontend/src/test/` — Vitest + Testing Library (dashboard, incident creation, batch tracing, recall approval, error/loading states). Run: `cd src/frontend && npm test`

Executed results: `docs/TEST_RESULTS.md`.
