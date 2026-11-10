# AnnaSetu Test Report

## Scope and evidence dates

This report separates the packaging checks run on 2026-11-10 from the most recent live Db2/browser verification already recorded for the unchanged application on 2026-11-09. Package source is a filtered copy of that application; no app logic was changed for submission packaging. The live database workflow results below are historical execution evidence, not a claim that a new browser session or production database audit was run during packaging.

## Checks run during packaging (2026-11-10)

| Check | Result | Evidence |
|---|---|---|
| Official repository submission validator | **Passed** | `python scripts/validate_submission.py submissions/annasetu` reported all checks passed (run with UTF-8 console output on Windows). |
| Backend default suite on packaged source | **21 passed, 0 failed, 7 skipped** | `python -m pytest api\tests -q -rs -p no:cacheprovider`; all seven skips explicitly say live Db2 test is opt-in. One Starlette/AnyIO `BlockingPortal` deprecation warning. |
| React/Vite production build | **Passed** | Vite 7.3.7 transformed 26 modules and emitted index HTML, CSS and JS bundles. Eight packaged frontend source/manifest files matched the source tree by SHA-256. |
| `git diff --cached --check` | **Passed** | All 41 staged AnnaSetu files; no whitespace errors. |

The first validator invocation encountered a Python Windows console `cp1252` encoding exception while emitting the validator's checkmark. It did not reveal a validation error. Rerunning with `PYTHONIOENCODING=utf-8` completed successfully.

The package-only `npm ci --offline` probe could not install because one public npm tarball was not present in the local offline cache. The production build was run with the installed project's Vite dependencies against the packaged, SHA-256-matched frontend source. This offline cache limitation is not presented as a successful fresh dependency installation.

## Prior live Db2 and browser verification (2026-11-09)

The unchanged local project report records a live run against IBM Db2 Community Edition 12.1.5.0. It reports the `annasetu-db2` container healthy, direct FastAPI connectivity to `ANNATEST` for QA and `ANNASETU` for operations, and successful LangChain `DB2VS` retrieval. The run was performed against the isolated QA database for synthetic test writes; operational records were preserved.

- **Live backend and Db2 integration suite:** 28 passed, 0 failed, 0 skipped. The suite used `ANNATEST` and tested actual Db2 insert/select/update/rollback, batch/passport creation, missing-evidence `HOLD`, verification, feasibility, partial multi-NGO allocation, capacity bounds/release, assigned volunteer and OTP stage permissions, pickup/delivery/distribution, actual distributed kilograms, audit-chain integrity and vector retrieval with citations.
- **Browser and authentication:** the report records Edge rendering, all four reserved role logins on the relevant databases, rejection of incorrect/unknown credentials, and a 403 for donor access to an admin-only route.
- **Operational dashboard:** the report records direct-SQL agreement for donated 395 kg, collected 264 kg, delivered 264 kg, distributed 228 kg, and one HOLD batch.
- **Vector retrieval:** the production API returned three cited Db2 vector sources and the operational audit chain verified.

These are the results captured in the project's prior live test report. They were not rerun against a live Db2 instance as part of this packaging validation.

## Skipped tests

The seven integration test cases are gated by `ANNASETU_INTEGRATION=1` so ordinary unit tests do not make network/database writes. They are environment-dependent and require IBM Db2, schema initialization, credentials, and `DB2_NAME=ANNATEST`. They are **skipped**, not passed, in the default packaging run. Run them only with an isolated QA database using the guard and instructions in [DB2_SETUP.md](DB2_SETUP.md); the test fixture refuses an operational `ANNASETU` target.

## Known warning and limitations

- Starlette reports a deprecation warning for its AnyIO `BlockingPortal` alias; tests pass, and it is not an application runtime failure.
- ETA is an estimate, not live route/traffic data. Safety screening is not official certification. OTP relay is manual. Policy answers use cited retrieval with no generative model configured.
- An npm offline-cache miss prevented a fresh offline dependency installation during packaging. A production build did succeed against the packaged source.

## Reproduction commands

From `submissions\annasetu\src` in PowerShell, after installing dependencies and configuring local `.env`:

```powershell
.\.venv\Scripts\python.exe -m pytest api\tests -q -rs
npm --prefix frontend run build
```

For a live integration run, use `ANNATEST` only and follow [DB2_SETUP.md](DB2_SETUP.md).
