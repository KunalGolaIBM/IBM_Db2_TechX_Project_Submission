# Testing

## Principles
- **Real infrastructure only.** Every test talks to a real IBM Db2 12.1 database and, for AI features, a real local Ollama server running IBM Granite. There are **no mocks** and **no SQLite**.
- **Repeatable.** At the start of a run, `tests/conftest.py` drops and recreates the application's tables, then the app seeds a deterministic 30-day history. Use a dedicated database.
- **Failures are real failures.** Degradation tests break things for real: for example, they point the app at an Ollama port where nothing is listening. They don't patch functions.

## Running

```bash
# Defaults: localhost:50000, database TESTDB, user db2inst1
DB2_PASSWORD=<password> pytest tests/ --cov=src/backend/app --cov-report=term-missing

# As the least-privilege login (keeps the tables created by the admin run)
NSIN_KEEP_DB=1 DB2_USER=nsinapp DB2_PASSWORD=<password> DB2_SCHEMA=DB2INST1 pytest tests/
```

Prerequisites: a Db2 instance (for example, created with the IBM Db2 VS Code extension) and Ollama with `granite3.3:2b` and `granite-embedding:278m`.

## What each file proves

| File | What it proves |
|---|---|
| `test_api.py` | End-to-end workflows: health, login, trusted contacts, the incident lifecycle across resident and responder, SOS, triage persistence |
| `test_security.py` | No admin self-signup, responder verification, login throttling, constant-time unknown emails, token tampering, private-incident isolation, privacy masking, Db2-sized input limits, state machine, reference codes, SOS atomicity + audit, overdue journeys, AI-analysis ownership |
| `test_db2_adapter.py` | Native `ibm_db`: prepared `SELECT`, transactional `INSERT`/`DELETE`, rollback on constraint violation, wrong-password handling, credential escaping, VS Code variable aliases, production-secret guard |
| `test_db2_features.py` | Db2 analytics: exact median and p90, hotspots, SLA breaches. The Db2 catalog including the `VECTOR` columns. Semantic retrieval and off-topic rejection, duplicate-report linking. DDL and audit tampering denied to the restricted login |
| `test_retrieval.py` | Haystack hybrid search: category and audience metadata filters, passage citations, stop-word queries, API validation, hybrid status |
| `test_triage.py` | CrewAI Flow: 10 wording traps, escalation vs standard branch, cited protocol per category |
| `test_crew.py` | IBM's `DB2VectorSearchTool` on Granite embeddings, the Granite crew briefing end to end, degradation when Ollama is unreachable, disabling the LLM |
| `test_care.py` | Elder check-ins and assistance requests, child journeys, profiles, trusted contacts, hazards |

## Results

| Run | Result |
|---|---|
| IBM Db2 `TESTDB` (fresh schema) + Ollama Granite | see the README's Testing section for the latest numbers (last full run: **78 passed, 0 failed, 96% line coverage**) |
| IBM Db2 as least-privilege login `nsinapp` | full suite, plus 5 DDL and audit-tampering denial tests |
| Android `testDebugUnitTest` | 4 passed; `assembleDebug` builds |
| Web `npm run build` | passes (strict TypeScript) |

## Bugs these tests caught (that SQLite would have hidden)

| Bug | How the Db2 test run caught it |
|---|---|
| Duplicate index on primary-key and unique columns | Db2 rejects it with `SQL0605W`; the backend could not start on Db2 |
| `.is_(True)` renders `IS 1` | Db2 rejects it with `SQL0104N`; SOS and the roster failed |
| `ibm_db_sa` table-existence check looks in the login's own schema | The least-privilege login tried `CREATE TABLE` |
| `GETVARIABLE` needs `EXECUTE` | The health probe failed for the restricted login |
| `timestamp` is reserved | Raw SQL must quote the lowercase column |
| `langchain-db2` connection left a transaction open | Db2's infinite lock timeout hung other connections; fixed with autocommit |
