# Tests

The tests live next to the code they exercise, so that `make test` and `npm test` work without extra configuration:

| Where | What | Needs |
|---|---|---|
| [`../src/backend/tests/`](../src/backend/tests/) | pytest: metric semantics against the oracle, planner policy, pipeline and status precedence, API contract, Meta provider with a **mock** transport (50 tests), presentation, live Db2 integration | `make test`: nothing. `make test-db2`: running Db2 |
| [`../src/frontend/tests/unit/`](../src/frontend/tests/unit/) | Vitest: components, formatters, SQL highlighter, loading state, client; fixtures are real recorded API responses | `npm test` |
| [`../src/frontend/tests/e2e/`](../src/frontend/tests/e2e/) | Playwright: real backend + Db2 (3 specs use real Meta inference), mobile, and mocked HTTP states | API on :8000 and Db2 running; `npm run test:e2e` |
| [`../src/backend/metricguard/evaluation.py`](../src/backend/metricguard/evaluation.py) | 25-case benchmark plus 12 unseen prompts (`make eval`, `make eval-llm`) | Db2; the LLM variant needs `MODEL_API_KEY` and costs credits |
| [`../src/backend/metricguard/verification.py`](../src/backend/metricguard/verification.py) | `make db-verify`: Db2 verification suite and evidence report | Db2 |

```bash
cd submissions/metricguard/src
make test                    # unit tests, no database
make test-db2                # + live Db2 tests (MG_RUN_DB2_TESTS=1)
make db-verify               # writes evidence/DB2_VERIFICATION.md
cd frontend && npm ci && npm run typecheck && npm run lint && npm test
```

Recorded results and their limits: [`../docs/FINAL_QA_REPORT.md`](../docs/FINAL_QA_REPORT.md) and [`../src/evaluation/benchmark-results.md`](../src/evaluation/benchmark-results.md). The 37-case Meta benchmark is a smoke test, not an accuracy rate.
