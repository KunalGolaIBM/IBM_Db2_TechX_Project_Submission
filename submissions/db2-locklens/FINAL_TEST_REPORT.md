# Final Test Report – Db2 LockLens

Date of the checks below: 10 November 2026. Environment: a Linux sandbox with Python 3.12, **no Docker,
no Db2, no network access, no pip installs possible**. `pytest`, `ibm_db`, `streamlit`, `plotly`,
`langchain-core` were not available. Only `pandas`, `PyYAML`, `python-dotenv` and `setuptools` were.

**Bottom line:** the logic, the CLI and the page code were exercised with mocks, a fake driver and stub
modules. **Nothing was verified against a real Db2, real Streamlit/Plotly, real LangChain or Docker.**
Items marked *simulated* are not substitutes for those.

## 1. Executed checks

| # | Command (run from `submissions/db2-locklens` unless noted) | Real or simulated | Result | Limitation |
|---|---|---|---|---|
| 1 | `python3 scripts/validate_submission.py submissions/db2-locklens` (repo root) | Real (official script) | **PASS** | Checks structure/metadata/secret filenames only |
| 2 | `python3 -W error -m compileall -q src tests locklens_cli.py` | Real | **PASS** | Syntax only |
| 3 | Custom AST script: unused imports / undefined names | Real, home-made (not a standard linter) | 1 unused import found and removed; 0 remaining | Approximate; `__file__` false positives ignored |
| 4 | `python3 /tmp/shim/run.py` – a ~25-line **stand-in test runner**, *not pytest* | Real execution of the real test code, but **not real pytest** | **93 passed, 0 failed, 7 skipped** | No fixtures/plugins; real pytest was unavailable |
| 5 | Same runner, tests in `test_pipeline.py`, with a stub `langchain_core` on `PYTHONPATH` | **Simulated** (stub implements documented semantics of `RunnableLambda`, `\|`, `assign`, `with_fallbacks`, prompt template) | 10 passed, 0 failed | Validates my chain wiring and data flow only; says nothing about real LangChain compatibility |
| 6 | Dashboard executed with stub `streamlit`/`plotly`, real `pandas`, fake `ibm_db`: 6 pages × (incident table absent/present) + auto-refresh path + unconfigured path | **Simulated** | 14/14 scenarios ran without exception | Catches typos/bad names/wrong shapes; cannot validate real Streamlit/Plotly API behaviour or rendering |
| 7 | `locklens_cli.py test-connection` with no `DB2_PASSWORD` | Real process | exit 2, lists the problem | – |
| 8 | `DB2_PASSWORD=pw locklens_cli.py test-connection --wait 30` (real sandbox: no `ibm_db`) | Real process | exit 1 immediately: "ibm_db driver is not installed" (no pointless retry) | – |
| 9 | `test-connection`, `init-db`, `snapshot`, `snapshot --json --no-record` against a **fake `ibm_db` module** | **Simulated** driver, real LockLens code | All exit 0; 3 incidents "created"; password absent from output | The fake answers canned rows; no SQL was executed by any database |
| 10 | PyYAML parse of `docker-compose.yml`; consistency check of `.env.example` vs `db2.env.example` vs variables read in `config.py` | Real (structural only) | Parses; database name, user and port consistent; every documented variable is read and vice versa | `docker compose config` / `up` **not run** |

### Unit-test inventory (check 4, by file)
`test_config` 7 · `test_connection` 8 · `test_monitoring` 13 · `test_lock_monitor` 12 ·
`test_diagnostics` 18 · `test_incidents` 16 · `test_graph_layout` 7 · `test_runtime` 3 · `test_cli` 4 ·
`test_pipeline` 5 run + 5 skipped (need `langchain_core`).
Skipped modules: `tests/integration/test_live_db2.py` (needs real Db2), `tests/test_dashboard_apptest.py`
(needs real Streamlit).

## 2. Failures found and fixed during this session
- `str.capitalize()` lowercased user/application names in finding titles (found by a test; fixed).
- Setting `LOCKLENS_QUERY_TIMEOUT` was documented but never applied; removed rather than left misleading.
- A single-hop idle-holder finding forced WARNING even for a 1-second wait; severity now follows the wait.
- `finalize` took an optional 2nd argument, which is risky for `RunnableLambda`; split into a one-argument function.
- Added a 3-argument fallback for `MON_GET_APPL_LOCKWAIT` and a second decode path for
  `MON_FORMAT_LOCK_NAME` (both covered by mocked tests).
- Documentation told users to create the venv inside the submission folder, which makes the official
  validator fail on certifi's `.pem`; instructions now place it outside.

## 3. NOT executed
| Item | Why | How to cover it |
|---|---|---|
| Real `pytest` run | Not installable offline | `pytest -v` |
| The 5 LangChain-specific tests with real `langchain-core` | Not installable | `pytest -v` (they un-skip automatically) |
| Real-Db2 integration test (`tests/integration`) | No Db2 | `$env:LOCKLENS_RUN_INTEGRATION="1"; pytest tests/integration -v -s` |
| Streamlit headless test (`tests/test_dashboard_apptest.py`) | No Streamlit | `pytest -v` after `pip install -r requirements-dev.txt` |
| Dashboard in a browser, Plotly rendering, `st.fragment` auto-refresh | No Streamlit/browser | `streamlit run src/app.py` |
| Every SQL statement against Db2 (monitoring functions, `HEX`, `CHAR`, `MIDNIGHT_SECONDS`, incident DDL incl. `EXCLUDE NULL KEYS`, CLOB binding) | No Db2 | Quickstart steps 4–8 |
| `MON_FORMAT_LOCK_NAME` input form; whether `CONNECTTIMEOUT` is honoured | Unverifiable offline | Quickstart step 8 |
| Docker image start, privileged mode, healthcheck, volume | No Docker | `docker compose up -d`, `docker ps` |
| `scripts/setup_windows.ps1` | No PowerShell | Run it; fallback is manual `copy` |
| Ollama / `langchain-ollama` path | Not installed | Optional |
| Fresh-machine install of `requirements.txt` (version compatibility) | No network | Step 3 of the quickstart. Versions are lower bounds only |

## 4. Real Db2 verification status
**None.** No claim in this repository states that a real Db2 test passed. The SQL and the demo are
written from IBM's documentation (monitoring table functions and their documented columns, the
`HLD_APPLICATION_HANDLE` semantics, `UOWWAIT`/`UOWEXEC` states) and are intended to be proven by the
steps in `WINDOWS_QUICKSTART.md`.

## 5. Run on your machine (fill in)
| Check | Command | Result (pass/fail, notes) |
|---|---|---|
| Unit tests | `pytest -v` | |
| Connection | `python locklens_cli.py test-connection --wait 900` | |
| Init tables | `python locklens_cli.py init-db` | |
| Integration test | `pytest tests/integration -v -s` | |
| Demo end to end | see `DEMO_SCRIPT.md` | |
| Validator | `python scripts/validate_submission.py submissions/db2-locklens` (repo root) | |

## 6. Known limitations
See README → "Known Limitations": no confirmed deadlock detection (needs a deadlock event monitor),
snapshot-only view, no SQL text, best-effort lock-name decoding, single-user tool, Db2 LUW only and
unverified on a live server.
