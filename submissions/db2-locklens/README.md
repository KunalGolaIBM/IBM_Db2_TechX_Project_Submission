# Db2 LockLens – Explainable Database Lock & Deadlock Investigator

An IBM Db2 observability and troubleshooting dashboard. LockLens reads Db2's native lock
monitoring, shows which applications are waiting and which are blocking them, explains the
situation with evidence, recommends next steps, and keeps an incident history in Db2.

> **Advisory only.** LockLens never terminates sessions, rolls back transactions, changes Db2
> configuration or runs destructive SQL. It reads monitoring data and writes only to its own
> incident table.
>
> **What "AI" means here.** The diagnosis comes from deterministic, explainable rules over live Db2
> data. LangChain composes the pipeline stages. A language model is optional, local, used only to
> *summarise* findings that were already computed, and always labelled. LockLens is not an
> autonomous agent.

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [Key Features](#key-features)
- [IBM Db2 Integration](#ibm-db2-integration)
- [LangChain and the Optional Local Model](#langchain-and-the-optional-local-model)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Demonstration: two-session lock wait](#demonstration-two-session-lock-wait)
- [Testing & Verification](#testing--verification)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

More documents in this folder: [WINDOWS_QUICKSTART.md](WINDOWS_QUICKSTART.md) ·
[DEMO_SCRIPT.md](DEMO_SCRIPT.md) · [architecture.md](architecture.md) ·
[FINAL_TEST_REPORT.md](FINAL_TEST_REPORT.md) · [FINAL_SUBMISSION_CHECKLIST.md](FINAL_SUBMISSION_CHECKLIST.md)

## Problem Statement
When one transaction holds a lock, others touching the same resource must wait. A transaction
left open (a missing `COMMIT`, a paused client, a crashed process) can stall many applications.
Finding the culprit normally means piecing together monitoring views, application handles and
logs by hand, and it gets harder as more sessions join the chain.

## Solution Overview
LockLens connects directly to Db2, reads the lock and lock-wait monitoring functions, builds the
blocking relationships between applications, and presents them in a Streamlit dashboard with a
graph, plain-language diagnostics and a stored incident history. It is useful on its own: no
external AI service, API key or model download is needed.

## Key Features
- **Live lock monitor** from `MON_GET_LOCKS` and `MON_GET_APPL_LOCKWAIT`; columns Db2 does not
  return on your version are hidden, never invented.
- **Blocking identification with provenance**: each relationship says whether Db2 reported the
  holder, it was inferred from `MON_GET_LOCKS`, it is ambiguous, or it is unknown. Unknown stays
  unknown.
- **Blocking graph** (Plotly): holder → locked resource → waiting application, including chains.
- **Explainable diagnostics**: severity, finding type, evidence, affected applications,
  explanation and recommended next steps. Covers long waits, blocking sessions, idle-in-
  transaction holders (from the state Db2 reports), chains, unknown or vanished holders and
  circular waits.
- **Honest deadlock handling**: a lock wait is not a deadlock, and a circular wait seen in one
  snapshot is reported as an *observation*, never a confirmed deadlock.
- **Incident history in Db2** with de-duplication (application check plus a database unique
  index), automatic resolution when a situation is no longer observed, and filters by severity,
  category, status and date.
- **Graceful degradation**: missing privileges, missing functions, timeouts and wrong credentials
  produce clear messages instead of crashes or fake data.
- **Optional local-model summary** through LangChain and Ollama, with automatic fallback.

## IBM Db2 Integration
| Purpose | Db2 feature |
|---|---|
| Locks currently held / requested | `MON_GET_LOCKS(NULL, -2)` |
| Who waits for whom, since when | `MON_GET_APPL_LOCKWAIT(NULL, -2)` (3-argument form tried if needed) |
| Application name, user, state (`UOWWAIT` = idle in a transaction) | `MON_GET_CONNECTION(NULL, -2)` |
| Which table or row a lock name refers to | `MON_FORMAT_LOCK_NAME` |
| Incident history | `LOCKLENS.LOCK_INCIDENTS` table, identity column, unique index `EXCLUDE NULL KEYS` |

Result columns are named explicitly (IBM advises against `SELECT *` on monitoring routines). A
`WHERE 1=0` probe discovers which documented columns your server returns, so differences between
Db2 versions degrade gracefully. All values are bound as parameters; the only interpolated
identifier is the schema name, validated against a strict pattern. Wait durations are computed on
the Db2 server to avoid clock-skew errors. Details: [architecture.md](architecture.md).

## LangChain and the Optional Local Model
LangChain (`langchain-core`) is used in `src/locklens/pipeline/diagnostic_chain.py`:

```
Snapshot -> prepare_input -> apply_rules -> narrative -> finalize -> DiagnosisResult
            RunnableLambda   RunnablePassthrough.assign(...)          RunnableLambda
```

- `RunnableLambda` wraps each plain, separately unit-tested stage function.
- `RunnablePassthrough.assign` adds `findings` and then `narrative` to the running state.
- The optional narrative step is `ChatPromptTemplate | local model | StrOutputParser`, wrapped with
  `with_fallbacks` so any failure yields the deterministic summary instead.

Three things stay distinct, and the UI labels each one:
1. **Rule-based findings** – deterministic code over Db2 data. This *is* the diagnosis.
2. **LangChain pipeline** – composes the stages. The default run uses no model at all.
3. **Optional LLM summary** – only when `LOCKLENS_LLM_ENABLED=true`, only on button press, only a
   local Ollama model. It receives the already-computed findings, is instructed to add no new
   facts, and cannot change them. If Ollama is missing or fails, a deterministic summary is shown
   and labelled `deterministic-fallback`.

If `langchain-core` is not installed the app still runs the same stages directly and says so
(`pipeline: direct (langchain not installed)`).

## Architecture
```
Streamlit UI / CLI -> LockLensRuntime (one Db2 connection)
        -> MonitoringClient --(MON_GET_* table functions)--> Db2
        -> LangChain pipeline (rules -> findings -> narrative)
        -> IncidentStore ------------------------------------> Db2 LOCKLENS.LOCK_INCIDENTS
```
Full diagram, data flow, schema and design decisions: [architecture.md](architecture.md).

## Tech Stack
Python · IBM Db2 Community Edition · `ibm_db` · Streamlit · Plotly · LangChain (`langchain-core`)
· pandas · pytest · Docker Compose. Optional: Ollama via `langchain-ollama`.

## Prerequisites
- Docker Desktop (for a local Db2), or any reachable Db2 LUW 10.1+ database.
- Python 3.11 or 3.12 recommended (`ibm_db` needs a prebuilt wheel or a C toolchain; if `pip` tries
  to compile it, use a supported Python version).
- A Db2 user that may run the monitoring functions (see [Configuration](#configuration)).
- No GPU, API key or paid service is required. 16 GB RAM is plenty; give Docker Desktop ≥ 4 GB.

## Setup & Installation
Short version for Windows PowerShell (full version with troubleshooting:
[WINDOWS_QUICKSTART.md](WINDOWS_QUICKSTART.md)). Run from `submissions\db2-locklens`.

```powershell
# 1. One shared password for Db2 and LockLens (creates .env.db2 and .env; both git-ignored)
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1

# 2. Start Db2 (first start takes several minutes)
docker compose up -d

# 3. Python environment. Keep the venv OUTSIDE this folder: the repository validator rejects
#    files such as certifi's .pem that every venv contains.
python -m venv ..\..\.venv
..\..\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 4. Wait for Db2, then create the incident tables
python locklens_cli.py test-connection --wait 900
python locklens_cli.py init-db
```
Linux/macOS: `python3 -m venv ../../.venv && source ../../.venv/bin/activate`, `cp .env.example .env`,
`cp db2.env.example .env.db2` (use the same password in both).

Docker Desktop being installed does **not** mean Db2 exists: `docker compose up` starts IBM's
Db2 Community Edition image (`privileged: true` is required by that image; starting it means
accepting its license, `LICENSE=accept`).

## Configuration
All settings come from environment variables or `.env` (see [.env.example](.env.example); placeholders
only). The password is never shown in the UI and is redacted from logs. `db2.env.example` configures
the Db2 container; its `DBNAME` and instance name match `DB2_DATABASE` and `DB2_USER`.

| Variable | Default | Meaning |
|---|---|---|
| `DB2_HOST` / `DB2_PORT` / `DB2_DATABASE` | localhost / 50000 / testdb | target database |
| `DB2_USER` / `DB2_PASSWORD` | db2inst1 / *(none)* | credentials; password is required |
| `DB2_SECURITY` | false | `true` adds `SECURITY=SSL` |
| `LOCKLENS_POLL_SECONDS` | 5 | auto-refresh interval (2–300) |
| `LOCKLENS_AUTO_REFRESH` | false | start with auto-refresh on |
| `LOCKLENS_WAIT_WARN_SECONDS` / `..._CRITICAL_SECONDS` | 10 / 60 | severity thresholds |
| `LOCKLENS_AUTO_RECORD` / `LOCKLENS_RECORD_MIN_SEVERITY` | true / WARNING | store incidents in Db2 |
| `LOCKLENS_SCHEMA` | LOCKLENS | schema for the incident table |
| `LOCKLENS_CONNECT_TIMEOUT` | 15 | connection timeout in seconds (passed to the driver) |
| `LOCKLENS_LLM_ENABLED`, `LOCKLENS_OLLAMA_URL`, `LOCKLENS_OLLAMA_MODEL`, `LOCKLENS_LLM_TIMEOUT` | false, … | optional local model |

**Db2 privileges.** The connecting user needs `EXECUTE` on `MON_GET_LOCKS`, `MON_GET_APPL_LOCKWAIT`,
`MON_GET_CONNECTION` and `MON_FORMAT_LOCK_NAME` (or an authority such as DBADM, SQLADM, DATAACCESS
or SYSMON; check IBM's documentation for your version). To store incidents it also needs `CREATETAB`
and `IMPLICIT_SCHEMA` (or create the table with `scripts/init_db.sql` as an administrator). The
container's `db2inst1` user is sufficient. Missing privileges are reported on the dashboard.

## Running the Project
```powershell
streamlit run src/app.py                      # dashboard at http://localhost:8501
```
Command-line alternative (no `PYTHONPATH` needed):
```powershell
python locklens_cli.py test-connection --wait 900   # retry while Db2 starts
python locklens_cli.py init-db                      # idempotent
python locklens_cli.py snapshot                     # one snapshot + diagnosis (records incidents)
python locklens_cli.py snapshot --json --no-record
```
Turn on *Auto-refresh* in the sidebar (or `LOCKLENS_AUTO_REFRESH=true`) to poll. One Db2 connection
is reused across refreshes.

Optional local model: install [Ollama](https://ollama.com), pull a small model that fits 6 GB of
VRAM (for example `ollama pull llama3.2:3b`), `pip install langchain-ollama`, set
`LOCKLENS_LLM_ENABLED=true`. Everything else works without it.

## Demonstration: two-session lock wait
Uses a dedicated demo schema (`LOCKLENS_DEMO`); nothing else is touched. Needs the container
(`db2server`) running and `python locklens_cli.py init-db` done. A narrated version for recording:
[DEMO_SCRIPT.md](DEMO_SCRIPT.md).

```powershell
# One time: copy the scripts into the container and create the demo table
docker exec db2server rm -rf /tmp/locklens
docker cp scripts db2server:/tmp/locklens
docker exec -it db2server su - db2inst1 -c "db2 connect to testdb && db2 -tvf /tmp/locklens/demo_setup.sql"
```
**1. Terminal A – the blocker** (keep it open; it holds a transaction):
```powershell
docker exec -it db2server su - db2inst1
db2 connect to testdb
db2 +c -tvf /tmp/locklens/demo_session_a.sql     # updates row 1, autocommit OFF, no COMMIT
```
**2. Terminal B – the waiter** (a separate connection):
```powershell
docker exec -it db2server su - db2inst1
db2 connect to testdb
db2 -tvf /tmp/locklens/demo_session_b.sql        # blocks, waiting for A
```
**3. LockLens** (`streamlit run src/app.py`, press *Refresh now*):
- *Live Lock Monitor*: one waiting application, its blocker, a `ROW` lock (table `LOCKLENS_DEMO.ACCOUNTS`
  when `MON_FORMAT_LOCK_NAME` can decode it) and the wait time.
- *Blocking Relationships*: A → locked row → B.
- *Diagnostics*: after 10 s the wait is a WARNING; A is reported as idle inside its transaction when
  Db2 reports it in `UOWWAIT`. No deadlock is claimed.
- *Incident History*: one OPEN incident per condition, updated rather than duplicated on each refresh.

**4. Resolve:** in Terminal A run `db2 rollback` (or `db2 commit`). Terminal B's update completes, the wait
disappears on the next refresh and the incidents become RESOLVED. Clean up with
`db2 -tvf /tmp/locklens/demo_cleanup.sql`.

The waiter must be an `UPDATE`: under Db2's default currently-committed behaviour a plain `SELECT`
may read the last committed value instead of waiting.

## Testing & Verification
```powershell
pytest -v                                       # unit tests: mocked Db2, no database needed
$env:LOCKLENS_RUN_INTEGRATION = "1"; pytest tests/integration -v -s   # REAL Db2 (see below)
python ..\..\scripts\validate_submission.py submissions/db2-locklens   # run from the repo root instead
```
- **Unit tests (mocked)** cover diagnostic rules, blocking/wait classification, incident creation,
  de-duplication and resolution, input validation, error handling, SQL safety, graph layout, CLI
  behaviour and the LangChain pipeline. Db2 responses in these tests are mocks.
- **LangChain and dashboard tests** skip automatically if `langchain-core` / `streamlit` are missing.
- **Real Db2 integration test** (skipped unless `LOCKLENS_RUN_INTEGRATION=1`) opens two real sessions,
  makes one block the other and asserts LockLens sees it. It needs Db2, the demo table
  (`demo_setup.sql`), `ibm_db` and the `DB2_*` variables.

### Honest verification status
The authoring environment had no Docker, no Db2 and no network access. See
[FINAL_TEST_REPORT.md](FINAL_TEST_REPORT.md) for exact commands and results.

| Item | Status |
|---|---|
| Official `validate_submission.py` | Executed – passed |
| Unit tests | 93 passed with a minimal stand-in test runner (real pytest could not be installed offline); **please run real `pytest`** |
| LangChain pipeline tests | Not run against real LangChain; the 5 LangChain-specific tests plus the pipeline stages were run against a stub of the documented API (a simulation of my wiring, not of LangChain itself) |
| Streamlit dashboard / Plotly graph | Page code executed against stub modules (simulation); **not run in a browser**, not run with real Streamlit/Plotly |
| CLI | Executed as a real process: config errors, missing driver, and a full run against a fake `ibm_db` module |
| Real Db2 (monitoring SQL, incident SQL, lock-name decoding, demo, integration test) | **Not executed.** SQL follows IBM's documentation but is unproven against a live server |
| Docker Compose | YAML parsed and checked; `docker compose` itself was not run |
| Optional Ollama path | Not executed |

## Screenshots & Demo
Add your own screenshots to `docs/screenshots/` after running the demo (see
[FINAL_SUBMISSION_CHECKLIST.md](FINAL_SUBMISSION_CHECKLIST.md)).
- Live demo URL: not deployed (runs locally)
- Demo video: see `submission.json` → `project.video_url` once recorded
- Repository / Pull Request: see `submission.json` → `project.repo_url` once published

## Known Limitations & Future Roadmap
- **No confirmed deadlock detection.** That needs a deadlock event monitor, which is not implemented.
  LockLens reports circular waits seen in a snapshot as observations.
- **Snapshots, not history.** Waits shorter than the refresh interval can be missed.
- **No SQL statement text** for blocker or waiter is shown (it would need package-cache or activity
  monitoring); the blocker's *state* is shown when `MON_GET_CONNECTION` allows it.
- **Lock names are decoded best-effort.** `MON_FORMAT_LOCK_NAME` needs its own privilege; two call
  forms are tried, and if both fail the object shows as "not resolved" with a note.
- **Db2 LUW only**, not yet verified against a live server; column availability varies by version and
  is discovered at runtime. Db2 on z/OS and cloud variants are untested.
- **Auto-refresh** uses `st.fragment(run_every=...)` (Streamlit 1.37+). *Refresh now* always works.
- `LOCKLENS_CONNECT_TIMEOUT` is passed to the driver as `CONNECTTIMEOUT`; whether your driver version
  honours it is unverified. There is no per-query timeout.
- Single-user tool: one shared connection, no login screen. Run it on a trusted network.
- Roadmap: deadlock event monitor, statement text, lock-escalation analysis, trend charts.

## Team Members & Credits
Individual participant: see `submission.json` (`team.members`).
Built on IBM Db2, `ibm_db`, Streamlit, Plotly and LangChain.
