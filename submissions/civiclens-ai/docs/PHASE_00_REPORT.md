# CivicLens AI: Phase 00 Report

| | |
|---|---|
| Date | 9 November 2026 |
| Branch | `feat/civiclens-phase00` (from `main` at `4d685c2`) |
| Scope | `submissions/civiclens-ai/` only; no repository-wide files modified |
| Target deadline | 10 November 2026, 5:00 PM IST (as given by the team; see *Blockers*) |

---

## 1. Summary
The Phase 00 foundation is in place and **has been verified against a real IBM Db2 server**, IBM Db2 Community Edition 12.1.5 (`DB2/LINUXX8664 12.01.0500`), running in Docker inside the cloud development container. The schema, migrations, parameterized data access, duplicate detection, hotspot aggregation, transactions, audit logging, LangChain tools and FastAPI endpoints all executed real SQL against that server. The official submission validator passes.

No LLM is called yet, no frontend exists yet, and nothing has been deployed.

---

## 2. Official submission requirements (inspected)
Sources: `README.md`, `CONTRIBUTING.md`, `docs/submission-guide.md`, `docs/judging-criteria.md`, `docs/faq.md`, `docs/db2-setup-guide.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/validate-submission.yml`, `scripts/validate_submission.py`, `submissions/_template/`.

| Requirement | How it is met |
|---|---|
| Single folder `submissions/<slug>/`, kebab-case slug | `submissions/civiclens-ai/` |
| Required `README.md`, `architecture.md`, `submission.json`, `.env.example` (each ≥ 20 bytes) | Present and filled in |
| `submission.json`: title/slug/team/members/`ibm_db2.edition`/`ibm_db2.connector` | Filled. **Team member name is still `TODO`** (see blockers) |
| No `.env`, `*.pem`, `*.key`, etc. | None committed; repository-wide `.gitignore` already excludes `.env*` |
| Meaningful, functional Db2 usage (30% of score) | Native `ibm_db`, constraints, identity + `FINAL TABLE`, in-SQL haversine, `GROUP BY/HAVING`, transactions, catalog-driven migrations |
| Do not modify root files or other submissions | Verified with `git status`: only new files under `submissions/civiclens-ai/` |
| Branch convention `submission/<slug>` | This work uses `feat/civiclens-phase00` as instructed. **The final PR should come from `submission/civiclens-ai`** (see next steps) |
| PR title `[Submission] civiclens-ai: …` plus Google Form | Not done, by instruction (no final PR, no forms) |

---

## 3. Cloud development tools (checked)
| Tool | Result |
|---|---|
| Python | 3.13.18 ✅ |
| Node.js / npm | v22.23.4 / 10.9.9 ✅ (not used yet) |
| Docker | Client present. The daemon was not running and **was started manually** (`dockerd`). The image pull from `icr.io` succeeded ✅ |
| Db2 container | `icr.io/db2_community/db2:latest` (12.1.5), `--privileged`, ready in about 3 minutes ✅ |
| `ibm_db` wheel | 3.3.0 installed from PyPI with bundled clidriver (~137 MB on disk) ✅ |
| Java | Present (not needed) |
| PyPI / npm registries | Reachable ✅ |
| Fresh-venv reproducibility | `pip install -r src/backend/requirements-dev.txt` in a new venv, then unit tests pass ✅ |

---

## 4. IBM Db2 feasibility and database strategy

### Options evaluated
| Option | Cost | Verified here? | Notes |
|---|---|---|---|
| **A. Db2 Community Edition in Docker** | Free | ✅ **Yes**: all operations in §6 | Matches the repository's own `docs/db2-setup-guide.md`. Requires a privileged container and about 4 GB of RAM. Best fit for reviewers reproducing the project. |
| **B. IBM Db2 on Cloud (free/Lite tier, if offered)** | Free tier possibly available | ❌ Not verified | Needs the team's IBM Cloud account. Free-tier availability, quotas and expiry rules must be checked in the IBM Cloud catalog. The code already supports TLS (`DB2_SECURITY=SSL`). |
| C. watsonx.data Db2 engine | Usually paid | ❌ Not evaluated further | Out of budget and scope for the deadline |
| D. Any non-Db2 store | n/a | Rejected | Violates the core rule that Db2 is the primary store |

### Recommendation
1. **Primary, demo-safe path: option A.** Develop, test, and record the demo video against Db2 Community Edition in Docker. This is the path verified today, and judges can reproduce it.
2. **Hosted demo: option B, only if the team can provision it quickly.** Run the same migration and seed scripts against it, then run `db2_smoke_test.py` with `DB2_SECURITY=SSL` as the acceptance test. If it is not ready before the deadline, submit with the local Docker path plus a recorded video. Do not block the submission on hosting.

### Hosting feasibility notes (not verified, no deployment done)
- **Frontend on Vercel:** feasible for a static Vite build (planned).
- **Backend on Vercel serverless Python:** **risky.** The `ibm_db` driver with clidriver is about 137 MB uncompressed, which leaves little room under serverless bundle limits. It also needs native shared libraries, and each cold start would open a new Db2 connection. A container host is recommended instead (for example IBM Cloud Code Engine, or any free-tier container platform the team already uses), with outbound TLS to Db2 on Cloud. This needs verification, and needs approval before any public deployment.
- **Db2 Community in a hosted container:** requires privileged mode and about 4 GB of RAM, which most free container hosts do not provide. It is not recommended for hosting.

---

## 5. Architecture
See [`../architecture.md`](../architecture.md) for diagrams, the schema and the tool security model. In short:

```
React dashboard (planned) ──HTTP──► FastAPI ──► Pydantic validation ──► Repository (static, parameterized SQL)
                                       │                                         │ ibm_db prepare/execute
                                       └► LangChain agent (Phase 01) ─► CivicLensToolkit (allow-listed,
                                                                         bounded, audited) ──► IBM Db2 (CIVICLENS)
```

**Schema (6 tables, 5 secondary indexes):** `COMPLAINTS`, `INVESTIGATIONS`, `INVESTIGATION_EVIDENCE`, `RECOMMENDATIONS`, `REVIEW_DECISIONS`, `AUDIT_LOG`.

**Secure LangChain tools:** `search_complaints`, `get_complaint`, `find_duplicate_candidates` and `hotspot_summary` are all read-only, Pydantic-bounded and audited. No SQL-generating tool exists. The planned `propose_recommendation` tool can only insert rows with status `PROPOSED`, and approval stays a human API action.

---

## 6. Actual test and verification results
All runs were performed on 9 November 2026 in the cloud container against the local Db2 12.1.5 container.

### 6.1 Live Db2 smoke test (`src/backend/scripts/db2_smoke_test.py`)
Result: **PASS**. The output is recorded in [`evidence/db2_smoke_test_result.json`](evidence/db2_smoke_test_result.json).
1. Connected with `ibm_db`; server reported `DB2/LINUXX8664 12.01.0500`, database `CIVICDB`.
2. First run created the schema, 6 tables and 5 indexes. Later runs created nothing and skipped all 11 objects, so the migration is idempotent.
3. Inserted a synthetic complaint, read it back, and confirmed the fields matched.
4. Inserted an identical twin. The Db2 haversine query found the original at a distance of 0.0 m with score 1.0.
5. Hotspot aggregation returned the cell with count 2.
6. Wrote an `AUDIT_LOG` row.
7. Deleted the smoke rows inside an explicit transaction (2 rows).

### 6.2 Pytest
| Run | Result |
|---|---|
| Unit only (`pytest`, no DB) | **27 passed, 9 skipped** (the skipped tests are the live-Db2 tests) |
| Unit + live Db2 (`CIVICLENS_DB2_TESTS=1 pytest -v`) | **36 passed, 0 failed** in about 10.6 s. Output: [`evidence/pytest_live_db2.txt`](evidence/pytest_live_db2.txt) |
| Fresh venv from pinned requirements (unit) | **27 passed, 9 skipped** |

The live Db2 tests (no mocks) cover:
- idempotent migration
- an insert/read round trip
- SQL-injection strings stored literally, with the table still present
- **Db2 CHECK constraint enforcement (`SQL0545N`)**
- duplicate detection with a Db2-computed distance of 5–30 m for a ~14 m neighbour, while a far-away record is excluded
- **transaction rollback**
- LangChain tools executing against Db2 and writing `AUDIT_LOG` rows in order
- the API end to end through FastAPI (`/api/health/db`, create, duplicate on resubmission, get, 404, list)
- hotspot ordering over seeded synthetic data

The unit tests for the agent tools use an in-memory fake repository on purpose. They check argument bounds, audit behaviour and error masking only, and they are **not** counted as Db2 evidence.

### 6.3 Live HTTP check (uvicorn on :8000, real Db2)
- `GET /api/health` returned `{"status":"ok","version":"0.1.0"}`.
- `GET /api/health/db` returned `dbms_name DB2/LINUXX8664`, `dbms_ver 12.01.0500`, plus the Db2 server time.
- `GET /api/hotspots?days=30&min_count=3` returned the 3 planted synthetic clusters (POTHOLE 7, WATER_LEAK 7, GARBAGE 6).
- `POST /api/complaints` with an invalid category returned `422`.

### 6.4 Static checks and official validator
- `ruff check .`: **All checks passed** (rules E, F, W, I, B, UP, S).
- `ruff format --check .`: clean.
- `python -m compileall src tests`: OK.
- `python scripts/validate_submission.py submissions/civiclens-ai`: **PASSED**. A CI-style run across all submissions also passed (exit 0).
- A secret scan of the submission tree for the local Db2 password found no match.

### 6.5 Bug found and fixed during verification
The live HTTP check showed that the synthetic seeder could produce **future `REPORTED_AT` timestamps**: same day, later hour. This was fixed with `reported_time()`, which never returns a time later than now, and a regression unit test was added. The data was reseeded and checked in Db2: 52 rows, 0 in the future, all `IS_SYNTHETIC = 1`.

---

## 7. Completed files
```
submissions/civiclens-ai/
├── README.md                     # template-based overview, setup, run, test
├── architecture.md               # diagrams, schema, data flow, tool security model
├── submission.json               # metadata (team member name still TODO)
├── .env.example                  # placeholders only
├── docker-compose.db2.yml        # local Db2 Community Edition
├── pyproject.toml                # pytest + ruff config
├── data/synthetic/complaints_demo.json   # 52 SYNTHETIC records (seed 2026)
├── docs/
│   ├── PHASE_00_REPORT.md
│   ├── evidence/db2_smoke_test_result.json
│   ├── evidence/pytest_live_db2.txt
│   └── screenshots/.gitkeep      # no screenshots yet (none fabricated)
├── src/
│   ├── backend/
│   │   ├── requirements.txt / requirements-dev.txt   # pinned, verified versions
│   │   ├── civiclens/config.py
│   │   ├── civiclens/db/{connection.py, migrate.py, repository.py, schema.sql}
│   │   ├── civiclens/domain/{models.py, geo.py, text.py}
│   │   ├── civiclens/agent/tools.py
│   │   ├── civiclens/api/{main.py, deps.py}
│   │   └── scripts/{db2_migrate.py, db2_smoke_test.py, generate_synthetic.py, seed_synthetic.py, _bootstrap.py}
│   └── frontend/README.md        # placeholder: planned stack only
└── tests/
    ├── conftest.py
    ├── unit/{test_config, test_domain, test_migrate_parser, test_agent_tools, test_api_no_db, test_seed_time}.py
    └── integration/test_db2_live.py
```

---

## 8. Known technical limitations
- **The Db2 instance is ephemeral.** It lives inside this cloud session's container and disappears when the session ends. Each session (and each reviewer) must start Db2 with `docker-compose.db2.yml`, which needs privileged Docker and about 4 GB of RAM.
- **No LLM integration yet.** The tools exist and are tested, but no agent loop or model provider has been wired up, so there are no AI recommendations yet.
- **No authentication or authorization.** This is acceptable for local development only. Reviewer identity is needed before the human-review API ships.
- **Duplicate text similarity is lexical** (token Jaccard). It will miss paraphrases. Embeddings in Db2 `VECTOR` columns are a possible Phase 02 upgrade, once feature availability on the target edition is confirmed.
- **Geo-cells are a fixed 0.005° grid,** so a cluster that straddles a cell boundary is split. Neighbour-cell merging could be added later.
- **Connection per request.** There is no pooling yet. That is fine for the demo, but should be revisited for a hosted backend.
- **Timestamps are naive UTC.** The Db2 `TIMESTAMP` type has no zone, so the UI must convert to IST for display.
- **Only `ibm_db` 3.3.0 on Python 3.13/linux-x86_64 has been verified.** Other platforms rely on IBM's published wheels.

## 9. Remaining blockers and open questions
1. **Deadline conflict.** The repository README lists the Db2Hack deadline as **29 October 2026, 7:00 PM IST**, while this task gives **10 November 2026, 5:00 PM IST**. Please confirm the 10 November deadline with the organizers.
2. **Team metadata.** `submission.json` and the README need real member names, and optionally emails. These were not invented.
3. **Hosted Db2.** A Db2 on Cloud instance requires the team's IBM Cloud account. It cannot be provisioned from here, and it was not attempted (no paid infrastructure).
4. **LLM provider credentials.** watsonx.ai (or another provider) API key and project id are needed for Phase 01. These should be supplied through the environment, never through Git.
5. **Branch naming for the final PR.** Repository rules require `submission/civiclens-ai` and PR title `[Submission] civiclens-ai: CivicLens AI`. This Phase 00 work is on `feat/civiclens-phase00`.
6. **Public deployment** needs explicit approval. None has been done.
7. The **Google Form link** in the official docs is still a placeholder (`[GOOGLE_FORM_LINK_TO_BE_ADDED]`).

## 10. Proposed next phase (Phase 01: agent, review loop, dashboard MVP)
Ordered by value to the judges, given less than about 30 hours remaining:

1. **Investigation and review API (Db2-backed):** `POST /api/investigations`, `GET /api/investigations/{id}` (with audit trail), `POST /api/recommendations/{id}/decision`. Decisions and status changes must commit in **one Db2 transaction**.
2. **`propose_recommendation` tool:** status forced to `PROPOSED`, evidence ids validated against `INVESTIGATION_EVIDENCE`, and a confidence score stored.
3. **LangChain agent loop:** a tool-calling agent with watsonx.ai Granite (or a configured fallback provider), a step limit, a timeout, and full audit logging. Add a deterministic **"no-LLM" fallback** investigator so the demo works without API keys.
4. **Dashboard MVP:** React + Vite + Tailwind with a complaint list, a Leaflet map of complaints and hotspots, an investigation timeline (from `AUDIT_LOG`), and approve/reject buttons.
5. **Playwright smoke test** of the dashboard against the local API and Db2.
6. **Demo assets:** real screenshots and a short video recorded from the running system, plus the final `submission/civiclens-ai` branch and the PR, opened by the team.

Stretch goals: Db2 views for dashboard KPIs, a recurring-failure detector (complaints reappearing in a cell after `RESOLVED`), and an evaluation script reporting duplicate-detection precision and recall on a labelled synthetic set.
