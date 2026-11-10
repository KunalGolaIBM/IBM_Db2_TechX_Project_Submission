# Evidence index

Recorded output of real runs, not summaries. Nothing here is hand-edited except that absolute local paths are replaced by `<submission>` / `<venv>` / `<repo>` / `<scratch>` and ANSI colour codes are stripped. Secret values never appear: the scans print only file names and kinds of match, and tokens are read from the environment by the tests and never logged.

Files marked **02** were re-generated or added in Phase 02 on the final code; the full audit that uses them is [`../PHASE_02_RELEASE_REPORT.md`](../PHASE_02_RELEASE_REPORT.md).

| File | Phase | What it is |
|---|---|---|
| `db2_smoke_test_result.json`, `pytest_live_db2.txt` | 00 | Db2 smoke test and the first live-Db2 test run |
| `api_workflow_transcript.txt`, `pytest_phase01a_live_db2.txt` | 01A | HTTP transcript of the investigation workflow and the live-Db2 run after Phase 01A |
| `pytest_phase01b_live_db2.txt` | 01B | The whole backend suite against live IBM Db2 as it stood after Phase 01B: 138 passed, 1 skipped (kept as history) |
| `pytest_phase02_live_db2.txt` | **02** | The whole backend suite against **live IBM Db2** (`CIVICLENS_DB2_TESTS=1`) on the final code: **149 passed, 1 skipped** (the opt-in real-LLM test) |
| `coverage_backend.txt` | **02** | Line coverage of `src/backend/civiclens` from that same live-Db2 run (97 %; `pytest-cov` is installed in the verification environment only, not a project dependency) |
| `backend_static_and_unit.txt` | **02** | `ruff check`, `ruff format --check` and the 111 backend unit tests in a clean environment (no DB, no tokens, no LLM settings) |
| `frontend_checks.txt` | **02** | `tsc --noEmit`, ESLint and the Vitest component / API-integration suite (245 tests, verbose) |
| `contract_live_test.txt` | **02** | The real TypeScript API client + zod schemas against the running FastAPI + Db2 (no mocks): 8 passed |
| `e2e_functional_results.txt` | **02** | The Playwright run against the production build, the real backend and IBM Db2 (list reporter): 63 passed |
| `bundle_scan.txt` | **02** | `npm run verify:bundle`: no literal secret value, no database identifier, CSP present in the built bundle |
| `secrets_scan.txt` | **02** | `check_secrets.py --literal-from-env` over the repository (literal values of the real secrets are searched for) |
| `submission_validator.txt` | **02** | Output of the official `scripts/validate_submission.py` |
| `fresh_clone_run.txt` | **02** | Dry run of the documented submission procedure from a new clone of the official `main` (branch, only the project folder, CI as the workflow runs it, scope isolation), then a from-scratch install, lint, tests, build and bundle scan |
| `dependency_audit.txt` | **02** | `pip-audit` on the three requirement files and `npm audit` (shipped dependencies and everything) |
| `endpoint_auth_matrix.txt` | **02** | The measured authorization matrix of all 20 API operations (no token, bad token, each role, and a database-down process proving authorization runs before any database connection) |
| `llm_verification.txt` | **02** | Why real-LLM verification is **BLOCKED** (checked by variable names only), the no-network `llm_preflight.py` output, and how to unblock it |
| `palette_validation.txt` | 01B | The dataviz skill's palette validator on the dashboard's colours (includes the status-colour run that fails, with the reason) |

Screenshots are in [`../screenshots/`](../screenshots/README.md) with their own manifest; the recording is [`../demo/civiclens-demo.mp4`](../demo/civiclens-demo.mp4).
