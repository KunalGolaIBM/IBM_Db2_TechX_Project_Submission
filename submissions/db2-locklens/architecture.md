# System Architecture

## Overview
Db2 LockLens is a read-mostly investigation tool. A Streamlit dashboard (and a small CLI) call a
shared runtime that holds one Db2 connection. The runtime collects a monitoring snapshot from
Db2's native table functions, a LangChain pipeline turns it into structured, explainable findings,
and an incident store keeps important findings in Db2. The core path needs no external service.

## Architecture Diagram
```
 Streamlit UI (src/app.py, ui/)          CLI (python -m locklens.cli)
        |                                        |
        +------------------+---------------------+
                           v
                 LockLensRuntime (services/runtime.py)
          one Db2 connection · lock · refresh cache · record/resolve
        +------------------+--------------------------+
        v                  v                          v
 MonitoringClient     LangChain pipeline          IncidentStore
 (db/monitoring.py)   (pipeline/)                 (services/incident_service.py)
        |                  |                          |
        |   Snapshot       |  DiagnosisResult         |  Findings
        |  ------------>   |  ------------------>     |  ------------>
        v                                             v
  Db2 MON_GET_LOCKS                              Db2 LOCKLENS.LOCK_INCIDENTS
  MON_GET_APPL_LOCKWAIT                          (identity PK, unique OPEN_KEY index)
  MON_GET_CONNECTION
  MON_FORMAT_LOCK_NAME

 Inside the pipeline:
 Snapshot -> prepare_input -> apply_rules -> narrative -> finalize -> DiagnosisResult
             (lock_monitor)   (diagnostic_    (deterministic
                               engine)         or optional Ollama via
                                               prompt | llm | parser,
                                               with_fallbacks -> deterministic)
```

## Component Breakdown
| Component | Responsibility |
|---|---|
| `config.py` | Reads and validates environment settings; password excluded from `repr` and the redacted view |
| `logging_setup.py` | Logging with a filter that masks `PWD=` fragments and registered secrets |
| `db/connection.py` | `ibm_db` wrapper: parameterized statements, autocommit ON (LockLens holds no locks), statement cleanup, SQLCODE parsing, error classification |
| `db/monitoring.py` | Discovers available columns, builds explicit-column queries, collects locks/waits/sessions/lock-name details into a `Snapshot`, adds `Note`s for anything unavailable |
| `services/lock_monitor.py` | Builds wait edges with provenance, finds root blockers, chain depth and wait-for cycles |
| `services/diagnostic_engine.py` | Deterministic rules producing `Finding`s (severity, evidence, explanation, advice) |
| `pipeline/diagnostic_chain.py`, `prompts.py` | LangChain composition of the stages; optional local-model narrative with fallback |
| `services/incident_service.py` | Schema creation, de-duplicated recording, auto-resolution, filtered reads |
| `services/runtime.py` | Orchestration, thread safety, reconnect, refresh caching |
| `services/graph_layout.py`, `ui/graph_view.py` | Pure graph layout, Plotly rendering |
| `ui/dashboard.py`, `ui/components.py` | Overview, Live Lock Monitor, Blocking Relationships, Diagnostics, Incident History, Settings |
| `cli.py`, `locklens_cli.py` | `test-connection [--wait N]`, `init-db`, `snapshot`; the launcher needs no `PYTHONPATH` |

## Data Flow
1. **Refresh** (button or timer) calls `runtime.refresh()`. A recent result is reused for a short
   time so page navigation does not query Db2.
2. **Collect**: for each monitoring function, discover the columns this server returns (once per
   connection; `MON_GET_APPL_LOCKWAIT` tries its 2- and then 3-argument call form), then run `SELECT <known columns> FROM TABLE(fn(NULL,-2))`. Waits are enriched with
   application details, and the lock names involved are decoded (capped at 25 per refresh).
   Each failure becomes a user-visible note; successful parts still render.
3. **Analyse**: each wait becomes an edge. The holder comes from Db2 when reported; otherwise it is
   inferred only if exactly one *other* application holds a granted lock with the same name;
   otherwise it stays `ambiguous` or `unknown`. Handle `0` is `holder_gone`.
4. **Diagnose**: rules run over the analysis and thresholds and emit findings.
5. **Narrate**: deterministic text by default; on request, a local model summarises the findings.
6. **Record**: findings at or above the configured severity are upserted by key; open incidents
   whose key is no longer present in a *complete* snapshot are resolved.
7. **Render**: tables hide columns Db2 did not return; the graph shows unknown holders explicitly.

## IBM Db2 Schema & Storage Design
`LOCKLENS.LOCK_INCIDENTS` (see `src/locklens/db/schema.sql`, mirrored by `scripts/init_db.sql`):

| Column group | Columns |
|---|---|
| Identity | `INCIDENT_ID` (identity PK), `INCIDENT_KEY`, `OPEN_KEY` |
| Lifecycle | `STATUS` (OPEN/RESOLVED), `DETECTED_AT`, `LAST_SEEN_AT`, `RESOLVED_AT`, `OBSERVATIONS`, `RESOLUTION_NOTE` |
| Classification | `SEVERITY`, `CATEGORY`, `FINDING_TYPE`, `TITLE` |
| Relationship | `BLOCKER_HANDLE`, `BLOCKER_INFO`, `WAITER_HANDLES`, `WAITER_INFO`, `LOCK_DETAILS`, `MAX_WAIT_SECONDS` |
| Narrative | `EXPLANATION`, `RECOMMENDATION`, `EVIDENCE` (CLOB, JSON list) |

**De-duplication.** A finding's key is `finding_type|subject_key` (for example
`BLOCKING_SESSION|blocker:7`). While an incident is open, `OPEN_KEY` equals that key and a unique
index (`EXCLUDE NULL KEYS`) allows only one open row per key, so concurrent LockLens instances cannot
create duplicates (a duplicate-key error falls back to an update). On resolution `OPEN_KEY` becomes
NULL, so a later recurrence opens a new row. Severity only escalates; the longest wait is kept.

Large text uses CLOBs to stay within the default 4 KB page row limit.

## Security & Secrets Management
- Credentials come from the environment or an uncommitted `.env`; no defaults for the password.
  `.env`, `.env.db2` are git-ignored; `.env.example` and `db2.env.example` hold placeholders.
- The UI never displays or accepts the password. Logs and error messages are scrubbed of `PWD=`
  fragments and the registered password.
- Connection-string values are validated, and quoted when they contain `; = { }`.
- Every value reaches Db2 as a bound parameter. The schema name is the only interpolated identifier
  and must match `^[A-Z][A-Z0-9_]{0,29}$`. Incident filters are validated against fixed sets.
- LockLens' own connection is autocommit, so it takes no locks that could add to contention.
- LockLens executes no `FORCE APPLICATION`, `ROLLBACK` of others, or configuration changes; such
  steps appear only as advice for a DBA.
- LLM use is opt-in, local (Ollama), receives only computed findings, and never credentials.

## Design Decisions
- **Provenance over completeness.** Every relationship states how it is known; unknowns are shown as
  unknown.
- **Deadlock vs. lock wait.** Only a deadlock event monitor can confirm a deadlock, so snapshot
  cycles are named "circular wait observed".
- **Rules are the diagnosis; the model only narrates.** The optional LLM cannot change findings, and
  its output is labelled with its source.
- **Pure stages, thin LangChain layer.** Stage functions are plain and unit-tested; LangChain composes
  them, so the chain can be tested separately and the app can say plainly if LangChain is missing.
- **Runtime column discovery** instead of hard-coding one Db2 version's columns.
- **Server-side wait durations** avoid client/server clock skew.
- **Single shared connection** guarded by a lock: no connection per UI refresh.
- **Dedicated `src/locklens` package** (not `src/langchain`) so a local folder can never shadow the
  real `langchain` package.
