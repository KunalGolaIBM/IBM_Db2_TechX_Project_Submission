# CivicLens AI: Phase 01A Report

| | |
|---|---|
| Date | 9 November 2026 |
| Branch | `feat/civiclens-phase01a`, created from `feat/civiclens-phase00` (`f70c5ee`) |
| Scope | `submissions/civiclens-ai/` only. No file outside it was modified (checked with `git status`) |
| Not done, by instruction | React dashboard, final submission PR, deployment, paid resources, external forms |

---

## 0. Headline: what is and is not proven

| Claim | Status |
|---|---|
| Investigation, evidence, recommendation, review and audit workflow persisted in IBM Db2 | ✅ **Verified** against a live Db2 12.1.5 (live tests + real HTTP run) |
| Fabricated or foreign evidence ids are rejected | ✅ **Verified**, by the application and independently by Db2 constraints |
| Atomic review, no double or conflicting decisions, self-review blocked | ✅ **Verified**, including a two-connection concurrency test and a forced mid-transaction failure |
| Bounded LangChain agent (allow-list, step limit, timeout, validation, audit) | ✅ **Loop logic verified**, using a scripted test double instead of a model |
| **A real LLM produced recommendations** | ❌ **NOT verified.** No LLM credentials exist in this environment, so no hosted model was called |
| Deterministic fallback, clearly labelled and never called "LLM" | ✅ **Verified** on Db2 and over HTTP |

Every recommendation that exists in the Db2 database right now was produced by the **rule-based fallback** (`generator_type = DETERMINISTIC_FALLBACK`), or by a test, in which case it was cleaned up afterwards.

---

## 1. Implemented features

### Task 1: Investigation API (all persisted in Db2)
| Endpoint | Auth |
|---|---|
| `POST /api/investigations` | analyst |
| `GET /api/investigations`, `GET /api/investigations/{id}` | any user |
| `GET /api/investigations/{id}/evidence` | any user |
| `POST /api/investigations/{id}/evidence` (attach existing complaints) | analyst |
| `GET /api/investigations/{id}/audit` | any user |
| `GET /api/investigations/{id}/recommendations`, `GET /api/recommendations/{id}` | any user |
| `POST /api/investigations/{id}/recommendations` (manual proposal) | analyst |
| `POST /api/investigations/{id}/run` (`mode`: `auto`, `llm` or `fallback`) | analyst |
| `POST /api/recommendations/{id}/decision` | reviewer |

Errors use a stable shape: `{"detail": {"code": "...", "message": "...", ...}}`.

### Task 2: Evidence-grounded recommendations
Each recommendation has a summary, an explanation (`rationale`), an explicit `priority` (1 = most urgent, 5 = least urgent), a confidence value, and its evidence ids. It always starts as `PROPOSED`: the status is a SQL **literal** in the `INSERT`, so no caller and no model output can choose another status.

Evidence is checked in four layers:
1. **Agent grounding:** a cited id must have been *returned by a tool in the current run*.
2. **Application check:** the id must exist in `COMPLAINTS` and be attached to the same investigation (`UNKNOWN_COMPLAINT_IDS` or `EVIDENCE_NOT_ATTACHED`, HTTP 422).
3. **Db2 foreign key:** a composite FK `RECOMMENDATION_EVIDENCE(INVESTIGATION_ID, COMPLAINT_ID) → INVESTIGATION_EVIDENCE` refuses anything else, even if application code is bypassed (tested with raw SQL, `SQL0530N`).
4. **Strict types:** evidence ids are strict positive integers, so `true` and `"5"` are refused. This was a real gap found by a test, see §6.

### Task 3: Human review
- `decide()` runs in **one Db2 transaction**: compare-and-set status flip, `REVIEW_DECISIONS` insert, audit row, and closing the investigation when nothing is left to review. Any failure rolls back all of it.
- Authorization: reviewer role only. The **reviewer identity comes from the token**, and a `reviewer` field in the body is rejected with 422.
- Blocked: a second decision (`ALREADY_DECIDED`, 409), a conflicting decision by another reviewer (409), and review by the investigation's creator (`SELF_REVIEW_FORBIDDEN`, 403, with a `REVIEW_DENIED` audit row). Rejection requires a comment.
- Db2 backstop: unique index `UX_DECISIONS_REC`.
- Supported decisions are `APPROVED` and `REJECTED`. The schema also allows `NEEDS_INFO`, but the API does not expose it yet.

### Task 4: LangChain agent
- **Bounded loop** (`agent/runner.py`) over the existing audited tools, with a tool allow-list, argument validation, a maximum number of steps, a wall-clock deadline, size-capped tool messages, strict JSON output validation, and evidence grounding. Unknown output keys, such as a model-supplied `status`, are dropped.
- **Providers** (`agent/llm.py`): `openai`, `anthropic` and `watsonx`, all optional. Credentials, model name and timeouts come from the environment only. watsonx is **not required**.
- **Rule-based fallback** (`agent/fallback.py`): fixed, documented rules over Db2 hotspot data, using the same audited tools. It does not read the investigation's free-text question. Its output is labelled `[RULE-BASED, NO LLM]` in the rationale and `DETERMINISTIC_FALLBACK` in the database and API.
- **Mode semantics:** `mode=llm` with no provider returns `409 LLM_NOT_CONFIGURED` and never silently falls back. `mode=auto` uses the LLM if available, otherwise the fallback, and the response states why (`fallback_reason`). If an LLM run fails in `auto` mode, the fallback runs and the reason is returned and audited.

### Task 5: Security improvements
See §5.

---

## 2. Files changed (39 files including this report; +3262 / −38 for the other 38, against Phase 00)

**New backend:** `civiclens/auth.py`, `domain/errors.py`, `domain/investigation_models.py`, `db/investigation_repo.py`, `agent/{runner,fallback,llm,investigate}.py`, `api/investigations.py`, `requirements-llm.txt`.

**Modified backend:** `config.py` (LLM, agent and auth settings; `CIVICLENS_ENV_FILE`), `db/schema.sql`, `db/migrate.py` (column upgrades), `db/connection.py` (re-entrant transactions, lock timeout), `db/repository.py` (`geo_cell` filter), `agent/tools.py` (`geo_cell` argument), `api/main.py` (router, error handler, `Authorization` header allowed by CORS).

**New scripts:** `check_secrets.py`, `api_workflow_demo.py`.

**Config and docs:** `docker-compose.db2.yml`, `.env.example`, `README.md`, `architecture.md`, `submission.json`, `pyproject.toml`, and the evidence files in `docs/evidence/`.

**Tests added:** `tests/unit/{test_auth, test_investigation_models, test_agent_runner, test_fallback_and_llm, test_secrets_scan}.py`, `tests/unit/conftest.py`, `tests/scripted_llm.py`, `tests/integration/{test_investigations_live, test_llm_provider_live}.py`.

**One Phase 00 regression test was edited, deliberately:** `test_migrate_parser.py` asserted that the schema has exactly six tables. Phase 01A adds a seventh (`RECOMMENDATION_EVIDENCE`), so the expected set was updated and two new assertions were added. No other Phase 00 test was changed, and all of them still pass.

---

## 3. Actual database operations (IBM Db2 12.1.5, `DB2/LINUXX8664 12.01.0500`)

All of these ran against the real server, in the live tests and in the HTTP run recorded in [`evidence/api_workflow_transcript.txt`](evidence/api_workflow_transcript.txt).

| Area | Operation |
|---|---|
| Schema | Created 7 tables and 7 indexes on a **fresh** database: new `RECOMMENDATION_EVIDENCE` with a composite foreign key and multi-path `ON DELETE CASCADE` (Db2 accepted this design), `GENERATOR_TYPE` with a CHECK list, `UX_DECISIONS_REC` (unique), `IX_REC_INV_STATUS` |
| Migration upgrade | `ALTER TABLE … ADD COLUMN` on a Phase 00 style table in a scratch schema (`apply_column_upgrades`), then a second run was a no-op |
| Create and read | `INSERT … FINAL TABLE` for investigations, recommendations and audit rows; joins for evidence and recommendations (with the decision `LEFT JOIN`) |
| State machine | Compare-and-set `UPDATE … WHERE STATUS IN (…)` for `OPEN → RUNNING → PENDING_REVIEW → CLOSED` and `FAILED → OPEN` |
| Evidence | `INSERT … SELECT … WHERE NOT EXISTS` (idempotent attach); existence checks with bounded `IN (?, …)` lists |
| Review | One transaction: lookup, guarded `UPDATE`, `INSERT` of the decision, audit `INSERT`, pending count, optional closing `UPDATE` |
| Integrity checks | Raw-SQL attempts that Db2 itself refused: foreign key (`SQL0530N`), CHECK constraint (`SQL0545N`), unique index (`SQL0803N`) |
| Concurrency | Two threads, two Db2 connections, one recommendation: exactly one decision won, the other got a 409, and exactly one `REVIEW_DECISIONS` row exists |
| Rollback | A failure injected after the status `UPDATE` and decision `INSERT`; a second, separate connection saw `PROPOSED` and zero decision rows |
| Session | `SET CURRENT LOCK TIMEOUT 10` on every connection |
| Audit | Every tool call, agent step outcome, review decision and denial written to `AUDIT_LOG` and read back in order through the API |

---

## 4. Real LLM versus fallback results

### Real LLM: not verified
No LLM credentials (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `WATSONX_*`) exist in this environment, and none were requested or used. Therefore **no hosted model was called, and no result in this report is evidence of LLM reasoning quality.**

What was verified instead:
| What | Evidence | Limit of that evidence |
|---|---|---|
| Loop mechanics: allow-list, argument rejection, step limit, timeout, output parsing, grounding, truncation | 14 unit test cases, and 5 live-Db2 tests, with `ScriptedChatModel` | A scripted double, not a model. It proves the guard rails, not that a real model will use the tools sensibly |
| Records created through the double are labelled `test-double:scripted` | Live tests | They were deleted after each test |
| `openai` and `anthropic` clients build from settings with a dummy key (`langchain-openai 1.7.4`, `langchain-anthropic 1.7.10`) | 2 unit tests | Construction only; **no network request was made** |
| `watsonx` configuration errors are raised when credentials are missing | Unit tests | The `ChatWatsonx` client was **never constructed or called**; its constructor and call path are unverified |

**To close this gap:** set `LLM_PROVIDER`, `LLM_MODEL` and the provider key, then run `CIVICLENS_DB2_TESTS=1 CIVICLENS_LLM_TESTS=1 pytest -m llm`. That test (`test_real_llm_produces_grounded_proposals`) already exists and is the only one skipped in the suite. It makes billable calls.

### Fallback: verified
In the HTTP run (`LLM_PROVIDER=none`, synthetic data, `mode=auto`):
- `mode=llm` returned **409 `LLM_NOT_CONFIGURED`** (no silent fallback).
- `mode=auto` returned `generator: DETERMINISTIC_FALLBACK`, `llm_configured: false`, a notice saying "NO LLM WAS USED", and a `fallback_reason`.
- It produced 2 recommendations from Db2 hotspot aggregates, each citing real complaint ids, with explicit priorities and status `PROPOSED`.
- The audit trail showed three tool calls (`hotspot_summary`, then `search_complaints` per hotspot) before `RECOMMENDATION_PROPOSED`.

Limitation: the fallback applies thresholds to counts and severities. Its `confidence` is a data-volume heuristic (`count / (count + 4)`), not a probability, and the rationale says so.

---

## 5. Security checks

| Check | Result | How verified |
|---|---|---|
| Db2 port exposed only on localhost | ✅ Compose publishes `127.0.0.1:50000` | `docker ps` showed `127.0.0.1:50000->50000/tcp`. Not tested from a second host |
| Db2 image pinned | ✅ By digest `sha256:2de8151713c2…` (Db2 Community 12.1.5), the build used for all results | Fresh container created **from the compose file** and used for every test |
| No model-generated SQL | ✅ No SQL tool exists; each tool maps to one fixed parameterized query | A test has the model call a `run_sql` tool: it is refused, audited as `TOOL_REFUSED`, and the data is untouched |
| Parameterized queries | ✅ Values are bound; only constants, a validated schema name, and the count of already-bounded lists are formatted into SQL | Code review plus injection-string tests on Db2 (Phase 00 and 01A); ruff rule `S608` is suppressed only for these reviewed sites |
| Authentication | ✅ Bearer tokens, constant-time compare, fail closed (503) if unconfigured, 401 if wrong | Unit tests, live API tests, HTTP run |
| Authorization | ✅ analyst and reviewer roles; analysts cannot decide; reviewers cannot create | Unit tests, live API tests, HTTP run |
| Unauthorized approval blocked | ✅ 401 (no token), 403 (wrong role), 403 (self-review), 409 (already decided) | Live API tests and HTTP run |
| Reviewer identity unforgeable | ✅ Taken from the token; a body `reviewer` field returns 422 | Unit test |
| Weak or duplicate tokens | ✅ Rejected at configuration time (<24 chars, duplicates, bad roles or ids) | Unit tests |
| Secrets never committed | ✅ `.env` is gitignored; the scanner found **0 findings** across 69 tracked and untracked files, including a search for the 4 real secret values (Db2 password and 3 tokens) | `scripts/check_secrets.py --literal-from-env`, plus a test that the scanner catches planted fakes |
| Credentials not in logs or errors | ✅ Connection errors are redacted and `SecretStr` is used | Phase 00 unit tests; the audit stores tool inputs but not credentials |
| Prompt-injection blast radius | ⚠️ Mitigated by design, **not red-teamed** | The model has no write tool, outputs are only `PROPOSED`, evidence is grounded, and a human approves. I did not test an adversarial complaint text against a real model |

**Known gaps (not fixed in this phase):**
- Phase 00 complaint ingestion (`POST /api/complaints`) and the read endpoints are still **public**, so anyone could add complaints. I kept them open to preserve Phase 00 behaviour and regression tests.
- Tokens are static and there is no rate limiting, revocation or OIDC.
- `GET /api/health/db` is public and reveals the Db2 version.
- The Db2 container needs `privileged: true`, which is IBM's documented requirement and a risk on shared hosts.
- The agent's deadline is cooperative (checked between calls). A single hung provider call is bounded only by the provider request timeout (`LLM_TIMEOUT_S`).

---

## 6. Test results (all actually run, 9 November 2026)

| Run | Result |
|---|---|
| `pytest` with a **clean environment** (no DB credentials, no `.env`) | **85 passed, 29 skipped** (the skipped tests are the 28 live-Db2 tests and the 1 real-LLM test) |
| `CIVICLENS_DB2_TESTS=1 pytest -v` against live Db2 | **113 passed, 0 failed, 1 skipped** (the real-LLM test). Output: [`evidence/pytest_phase01a_live_db2.txt`](evidence/pytest_phase01a_live_db2.txt) |
| Of those 113 | 85 unit, 9 Phase 00 live-Db2 (unchanged), 19 new live-Db2 |
| Phase 00 regression | All 36 Phase 00 tests (27 unit + 9 live) still pass; one assertion was updated, see §2 |
| FastAPI end to end | 2 live API tests (`TestClient`) **and** a run over real HTTP with uvicorn: [`evidence/api_workflow_transcript.txt`](evidence/api_workflow_transcript.txt) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 55 files already formatted |
| `compileall` | OK |
| `db2_smoke_test.py` (Phase 00) | PASS on the new pinned container |
| `scripts/check_secrets.py --literal-from-env` | 0 findings |
| Official `scripts/validate_submission.py` | **PASSED**, both for `submissions/civiclens-ai` and the CI-style all-submissions run |

### Problems found and fixed during verification
1. **Validator versus a local `.env`:** the official validator fails if *any* file named `.env` exists in the submission folder, even an untracked, gitignored one. I moved my local secrets file outside the folder and added a `CIVICLENS_ENV_FILE` setting. The validator itself was not modified.
2. **Boolean evidence ids:** `[true]` was accepted as evidence id 1, because pydantic coerces booleans before my validator runs. Fixed with strict integer types; it is covered by a test.
3. **Secret scanner false positives:** the first version flagged ordinary code (`api_key=_need(...)`). Rules were split by file type, and test fixtures are exempt from the assignment rule only (credential shapes and literal values still apply to them).
4. **Two test mistakes, not product bugs:** a priority expectation for `7 × 3.57 = 24.99` (below the threshold of 25), and a fixture that cached settings before the test's token override.

### Implemented but not directly tested
- The `EVIDENCE_MISSING` check at review time.
- The "too many tool calls in one step" cap.
- The lock timeout actually firing.
- Which guard (compare-and-set or the unique index) stops the loser in the concurrency test. The test checks only the outcome: exactly one winner and one decision row.
- The `watsonx` client construction and calls, and any hosted-provider call.

---

## 7. Remaining blockers and open questions
1. **LLM credentials.** The real-LLM path needs a provider key and model name. Please supply them through environment variables, never Git. watsonx is not required.
2. **Deadline conflict (carried over).** The repository README says the Db2Hack deadline was 29 October 2026, 7:00 PM IST; this task says 10 November 2026, 5:00 PM IST. Please confirm.
3. **Team metadata:** the team member name in `submission.json` is still a `TODO`.
4. **Hosted Db2 and backend:** still not provisioned. Hosting the Python backend with the 137 MB `ibm_db` driver on Vercel remains risky and unverified.
5. **Db2 is temporary.** The Db2 container in this cloud session is ephemeral. I **recreated it** from the new compose file, so Phase 00 data is gone; the demo data was re-seeded (52 synthetic rows). It also holds a few demo investigations created by the HTTP run.
6. **Final PR branch name:** repository rules require `submission/civiclens-ai`.

---

## 8. Recommended Phase 01B
1. **Real-LLM verification first** (about 30 minutes once a key is available): run the opt-in test, then `mode=llm` on the synthetic data, and record the result. If the model fails or misbehaves, the fallback keeps the demo working.
2. **React + TypeScript + Vite + Tailwind dashboard:** investigation list and detail page, evidence table, recommendation cards that show the generator label (`LLM` or `RULE-BASED`), approve and reject with a comment, an audit timeline, and a Leaflet map of hotspots.
3. **Run the agent as a background job:** `POST …/run` is currently synchronous and an LLM run can take tens of seconds. Add a status endpoint and let the UI poll.
4. **Close the security gaps:** protect or remove the public `health/db` detail, decide whether complaint ingestion should be authenticated, and add basic rate limiting.
5. **Add the missing tests listed in §6**, including a deliberately malicious complaint text sent to a real model.
6. **Playwright smoke test** of the full review flow, then real screenshots and a short demo video from the running system.
7. **Optional:** `NEEDS_INFO` review decisions, an evaluation script for duplicate detection (precision and recall on a labelled synthetic set), and Db2 views for dashboard KPIs.
