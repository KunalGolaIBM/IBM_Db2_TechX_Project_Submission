# CivicLens AI: Phase 01B Report

| | |
|---|---|
| Date | 9 November 2026 |
| Branch | `feat/civiclens-phase01b`, created from `feat/civiclens-phase01a` |
| Scope | `submissions/civiclens-ai/` only. No file outside it was modified (checked with `git status`) |
| Not done, by instruction | Final submission PR, public deployment, paid hosting, external forms |

---

## 0. Headline: what is and is not proven

| Claim | Status |
|---|---|
| A working React/TypeScript intelligence dashboard on top of the existing FastAPI + IBM Db2 backend (overview, map, complaints, investigation workspace, human review, agent transparency) | ✅ **Built, and driven end to end in a real browser** (production build, real backend, real IBM Db2 12.1.5) |
| Every dashboard number comes from the backend | ✅ **Verified** in the browser: each KPI tile and chart value is compared with `GET /api/overview` and with Db2-backed lists |
| Complaint browsing, investigation creation, evidence attach/view, running the investigator, recommendation review, audit history | ✅ **Verified** by Playwright against the real backend and Db2 (see §3) |
| Review error states 401 / 403 / 409 / 422 / 503 are shown clearly | ✅ **Verified** against real server responses (two 503s against deliberately misconfigured real API processes) |
| Deterministic output is never described as an AI result | ✅ **Verified**: one wording function (`describeGenerator`), unit tests, and browser assertions on every generator label |
| Security requirements of the brief (no tokens in source, protected complaint creation, minimal health endpoints, no DB credentials in the browser, configurable API URL and CORS, no auth shortcuts) | ✅ **Done and tested**, with remaining gaps stated in §6 |
| Genuine screenshots from the running application | ✅ **28 captures**, with a manifest (see §4) |
| **A real LLM produced a recommendation** | ❌ **BLOCKED.** No provider, model or credential is configured for the application, so no real LLM investigation was run and no paid API call was made (§5) |
| Public deployment | ➖ Not attempted (instructed). The app is **not safe to expose publicly yet** (§6) |

Every recommendation visible in the dashboard is either `DETERMINISTIC_FALLBACK` (shown as **"Rule-based · no LLM"**) or `MANUAL` (shown as **"Manual · analyst-written"**). The *Agent transparency* page states that none of them was written by a language model.

---

## 1. What was built

**Dashboard** (`src/frontend`, React 19 + TypeScript + Vite + Tailwind v4; dark charcoal surfaces with copper-orange accents):

| View | Screenshot | Notes |
|---|---|---|
| Sign-in | [01](screenshots/01-sign-in.png) | Token in a password field; kept in `sessionStorage` for the tab only; verified with `GET /api/me` before it is accepted |
| Intelligence overview | [02](screenshots/02-intelligence-overview.png) | KPI tiles, complaints by category / severity / day, who wrote the recommendations, top hotspots, operational status read from the live system, recent audited tool activity; a "View as table" twin for every chart |
| Geographic intelligence | [03](screenshots/03-geographic-intelligence.png), [04](screenshots/04-geographic-hotspot-selected.png) | Leaflet + OpenStreetMap; one marker per complaint (dashed ring = SYNTHETIC); hotspot cells drawn on the same grid Db2 aggregates; category, record-type, window and cluster filters |
| Complaints | [05](screenshots/05-complaints.png), [06](screenshots/06-complaint-detail.png) | Search, filters, sort, pagination, record detail, "Show on map"; analysts can report a complaint (SYNTHETIC by default) and see Db2's duplicate candidates |
| Investigation workspace | [07](screenshots/07-investigations.png), [08](screenshots/08-investigation-results.png), [09](screenshots/09-investigation-run-options.png), [18](screenshots/18-new-investigation.png), [19](screenshots/19-attach-evidence.png), [20](screenshots/20-investigation-run-result.png) | Create, attach evidence (picker or by ID), run (Auto / LLM only / Rule-based only), status tracker, evidence, audited tool activity with "who issued these calls", recommendations, manual proposals |
| Human review | [10](screenshots/10-human-review-queue.png), [11](screenshots/11-human-review-decided.png), [12](screenshots/12-human-review-analyst-readonly.png), [21](screenshots/21-review-confirm.png), [22](screenshots/22-review-approved.png) | Queue, explanation, generator, cited evidence, approve / reject with a confirmation that names the acting reviewer; analysts get no decision controls |
| Agent transparency | [13](screenshots/13-agent-transparency.png) | LLM status, per-generator counts, guard rails, each recommendation's stored author, audited tool activity |
| Error states | [23](screenshots/23-error-409-already-decided.png) 409 · [24](screenshots/24-error-403-forbidden.png) 403 · [25](screenshots/25-error-422-validation.png) 422 · [26](screenshots/26-error-401-signed-out.png) 401 · [27](screenshots/27-error-503-database-unavailable.png), [28](screenshots/28-error-503-auth-not-configured.png) 503 | Each is a real server response |
| Phone layout (390 px) | [14](screenshots/14-phone-overview.png), [15](screenshots/15-phone-map.png), [16](screenshots/16-phone-investigation.png), [17](screenshots/17-phone-review.png) | |

**Backend changes** (all inside the submission folder; behaviour changes are deliberate and tested):

* `GET /api/me` (identity + capabilities) and `GET /api/overview` (every dashboard aggregate computed in Db2 per request; hotspot `total` is the true count, not the number listed); `GET /api/recommendations` (review queue across investigations, with each item's stored generator).
* **Complaint creation is now analyst-only** (it was public); the audit actor is the authenticated user.
* **Health endpoints reveal nothing:** `/api/health` and `/api/health/db` return `{"status":"ok"}`; Db2 product/version appears only in the authenticated overview.
* Authentication is evaluated before the database dependency (an unauthenticated caller cannot probe Db2); database failures return a **generic** `503 DB_UNAVAILABLE` and the reason goes to the server log only.
* `CORS_ORIGINS` accepts only explicit `scheme://host[:port]` origins (wildcards and paths are rejected at start-up); `/api/*` responses carry `nosniff`, `no-referrer` and `no-store`; `/docs`, `/redoc` and `/openapi.json` are not served when `APP_ENV=production`.
* Scripts: `seed_demo_workflow.py` builds a believable demo state **through the real API** (nothing inserted into Db2 directly); `cleanup_test_data.py` removes test-marker rows (and, with `--workflow`, resets workflow state; it refuses to run if any complaint is not synthetic).

---

## 2. Test and check results (all actually run on 9 November 2026)

| Check | Result | Evidence |
|---|---|---|
| Backend unit tests, clean environment (no DB, no tokens, no LLM settings) | **103 passed** | [`evidence/backend_static_and_unit.txt`](evidence/backend_static_and_unit.txt) |
| Backend suite against **live IBM Db2** (`CIVICLENS_DB2_TESTS=1`) | **138 passed, 1 skipped** (the opt-in real-LLM test, see §5) in 43 s | [`evidence/pytest_phase01b_live_db2.txt`](evidence/pytest_phase01b_live_db2.txt) |
| `ruff check` / `ruff format --check` | clean | [`evidence/backend_static_and_unit.txt`](evidence/backend_static_and_unit.txt) |
| Frontend `tsc --noEmit`, ESLint | clean | [`evidence/frontend_checks.txt`](evidence/frontend_checks.txt) |
| Frontend component + API-integration tests (Vitest, React Testing Library, MSW) | **245 passed** in 16 files | [`evidence/frontend_checks.txt`](evidence/frontend_checks.txt) |
| **Live API contract test**: the real TypeScript client + zod schemas against the running FastAPI + Db2 | **8 passed** | [`evidence/contract_live_test.txt`](evidence/contract_live_test.txt) |
| **Playwright** against the production build, the real backend and IBM Db2 | **63 passed** | [`evidence/e2e_functional_results.txt`](evidence/e2e_functional_results.txt) |
| Evidence screenshots (separate Playwright project) | **20 capture tests passed, 28 images** | [`screenshots/manifest.json`](screenshots/manifest.json) |
| Production bundle scan (no literal secret value, no DB identifier, CSP present) | **0 findings** (5 bundle files; the 4 literal secret values of the environment were checked) | [`evidence/bundle_scan.txt`](evidence/bundle_scan.txt) |
| Repository secret scan (`check_secrets.py --literal-from-env`) | **0 findings** (218 files; the 4 literal secret values of the environment were checked) | [`evidence/secrets_scan.txt`](evidence/secrets_scan.txt) |
| Palette validation (dataviz skill's validator) | categorical series and severity ramp **pass**; the status-colour run **fails and is reported as such** | [`evidence/palette_validation.txt`](evidence/palette_validation.txt) |
| Official `scripts/validate_submission.py submissions/civiclens-ai` (script not modified) | **PASSED all validation checks** | [`evidence/submission_validator.txt`](evidence/submission_validator.txt) |

## 3. Real browser-test results

The Playwright suite drives the **production build** (so the Content-Security-Policy is really enforced) through the real API into real IBM Db2. It does **not** record traces, videos or automatic screenshots (they would capture the bearer header and the token field), and every test fails on any unexpected browser console error or CSP violation.

| Spec | Tests | Result | What it proves |
|---|---:|---|---|
| `a11y.spec.ts` | 11 | 11 passed | axe-core WCAG A/AA on every view, dialogs, chart table views; keyboard order |
| `auth.spec.ts` | 8 | 8 passed | real 401; masked field; token only in this tab's sessionStorage; sent only to the API; deep link; sign-out; role-based controls |
| `complaints.spec.ts` | 5 | 5 passed | search/filter/detail agree with the API; pagination; intake and Db2 duplicate detection; validation first |
| `errors.spec.ts` | 3 | 3 passed | real 503 (database down; authentication not configured) and unreachable API, each with recovery |
| `map.spec.ts` | 8 | 8 passed | one marker per complaint; hotspot cells equal Db2's aggregates; filters; deep link; basemap failure; keyboard access |
| `overview.spec.ts` | 7 | 7 passed | every KPI and chart value equals what the API reports; tooltips; Refresh re-reads Db2 |
| `responsive.spec.ts` | 5 | 5 passed | 390 px and 820 px: no horizontal scroll, no sideways-scrolling container, map first, dialogs fit |
| `review.spec.ts` | 8 | 8 passed | approve/reject with Db2 recording; 409 race with two reviewers; 403; 401; 422; analyst read-only |
| `workflow.spec.ts` | 8 | 8 passed | create, attach evidence (422 on unknown ids), LLM-only 409, Auto and Rule-based runs, audit history, manual proposal |
| **Total** | **63** | **63 passed, 0 skipped, 0 failed** | wall time 5.6 min, one worker |

How each required verification is covered:

| Required verification | Where |
|---|---|
| Complaint browsing | `complaints.spec.ts` (search, filters and record detail agree with the API/Db2; pagination; intake with Db2's duplicate detection), `map.spec.ts` (one marker per complaint, filters) |
| Investigation creation | `workflow.spec.ts` (validated in the browser first, then Db2 stores it; it appears in the list and on the overview) |
| Evidence viewing / attaching | `workflow.spec.ts` (picker and by-ID attach; an unknown ID is refused by the server with a 422 and nothing is saved), `review.spec.ts` (the evidence behind a recommendation matches the API) |
| Executing the workflow | `workflow.spec.ts` (**Auto mode**, the form's default, falls back to the labelled rule-based run and says why, and Db2 stores `DETERMINISTIC_FALLBACK`; "Rule-based only" is labelled as such; "LLM only" is refused with a 409 and consumes nothing; recommendations are grounded in attached evidence) |
| Recommendation review | `review.spec.ts` (approve with confirmation; reject needs a comment; Db2 records reviewer, decision and the audit entry atomically; a decided recommendation cannot be decided again) |
| Audit history | `workflow.spec.ts` (every tool call and who issued it matches the database), `review.spec.ts` (the decision appears in the audit log), overview/transparency pages |
| 401 / 403 / 409 / 422 / 503 | `review.spec.ts` (401, 403, 409 with two real reviewers racing, 422), `errors.spec.ts` (503 database down and 503 authentication not configured, each against a real misconfigured API process; unreachable API with retry) |
| Accessibility | `a11y.spec.ts` (axe-core WCAG A/AA on every view, dialogs and the chart table views, plus keyboard order) |
| Responsive layout | `responsive.spec.ts` (390 px and 820 px: no horizontal page scroll, **no container scrolls sideways**, map on the first screen with collapsible filters, dialogs fit) |
| Security in the browser | `auth.spec.ts` (token masked; only in this tab's `sessionStorage`; never in URL, DOM, `localStorage` or cookies; sent only to the API as a bearer header; 401 ends the session) |

## 4. Screenshots (genuine)

[`screenshots/README.md`](screenshots/README.md) indexes all 28 images. They were produced by `src/frontend/e2e/screenshots.spec.ts` from the running app: production build, real FastAPI, real Db2 rows (synthetic and labelled), real OpenStreetMap tiles (with the attribution visible), deviceScaleFactor 2. `manifest.json` records the file, what it shows, who was signed in, viewport, pixel size, SHA-256 and capture time. Each capture asserts that what its caption promises is on screen (for example that the 409 notice is inside the viewport), so it fails instead of quietly missing its subject. Nothing is mocked, composited or edited, and bearer tokens never appear (the sign-in box is a password field; tokens are not rendered anywhere).

The state shown comes from the real application: the demo workflow was created by `seed_demo_workflow.py` through the real API; the workflow, approval and error screenshots are driven through the UI; the 403/401/422 cases alter the request on the wire (the server's answer is real); the 409 uses two real reviewer sessions; the two 503 cases target real API processes (one with a wrong `DB2_PORT`, one with no tokens configured). After capture the workflow state was reset and re-seeded.

## 5. Real LLM verification: BLOCKED

[`evidence/llm_verification.txt`](evidence/llm_verification.txt) records the checks (variable **names** only; no value was ever printed or stored):

* No `LLM_PROVIDER`, `LLM_MODEL` or provider API key is set for the application (not in the environment, not in the application's settings file, not in the running API process); the API itself reports `{"configured": false, "provider": "none"}`.
* The opt-in test `tests/integration/test_llm_provider_live.py` is **skipped** with its reason.
* The only provider-like variable in the sandbox, `ANTHROPIC_BASE_URL`, belongs to the sandbox's own gateway for the coding assistant, not to the application; there is no application key, and it was **not** repurposed. A billable call needs the operator's authorization.

Consequences: **no real LLM investigation was executed**, so no provider, model, evidence set or LLM result can be reported. The dashboard therefore labels everything it shows as rule-based or manual, and the Agent transparency page says "No language model is configured" and "None of the 5 recommendations … were written by a language model". The agent loop itself (allow-list, step limit, timeout, grounding, fallback with a stated reason) remains verified only with a scripted test double, which the UI would label "Test double · not a real model".

To unblock (needs authorization): install `requirements-llm.txt`, set `LLM_PROVIDER`, `LLM_MODEL` and the provider key, run `CIVICLENS_DB2_TESTS=1 CIVICLENS_LLM_TESTS=1 pytest -m llm`, then run one investigation in Auto or LLM-only mode from the dashboard. The result, the recommendation cards and the transparency page will show `provider:model`.

## 6. Security review against the brief

| Requirement | What was done | Evidence |
|---|---|---|
| Do not expose bearer tokens in committed source | No token anywhere in the repository; the sign-in screen asks for one; tests read tokens from the environment and never print them; traces/videos are off | secret scan, bundle scan, `auth.spec.ts` |
| Protect complaint creation before any public deployment | `POST /api/complaints` requires the **analyst** role (401 without a token, 403 for a reviewer); the audit actor is the authenticated user | `test_api_no_db.py`, live tests, contract test, `complaints.spec.ts` |
| Reduce information exposed by health endpoints | Both health endpoints return only `{"status":"ok"}`; Db2 product/version only in the authenticated overview; DB errors are generic 503s | unit + live tests, `errors.spec.ts` |
| Do not send database credentials to the browser | The frontend has no database setting at all; `verify:bundle` scans `dist/` for the literal values of every secret in the environment and for DB identifiers; no `VITE_*` secret | [`evidence/bundle_scan.txt`](evidence/bundle_scan.txt) |
| Configurable API base URL and CORS origins | `VITE_API_BASE_URL` (public, build-time; empty = same origin through the dev/preview proxy); `CORS_ORIGINS` validated to explicit origins | `config.py`, `tests/unit/test_api_dashboard.py` (CORS cases), frontend README |
| No authentication shortcut that would make a public deployment unsafe | No default user, no bypass flag, no "remember me", fail-closed 503 when no tokens are configured, token only in `sessionStorage` | `auth.spec.ts`, `errors.spec.ts` |
| Browser hardening | Production CSP (no `unsafe-eval`, scripts from `'self'`, `connect-src` limited to the API origin), `credentials: 'omit'`, no HTML-injection sinks (map tooltips use `textContent`) | `security.test.ts`, every e2e test fails on a CSP violation |

**Remaining gaps (not fixed, stated plainly; do not expose publicly until closed):**

1. `GET /api/complaints`, `/api/complaints/{id}` and `/api/hotspots` are still **public** (Phase 00 design). The data is synthetic, but real data would need protection.
2. Tokens are **static** and there is **no rate limiting or lockout**; a public deployment needs real identity (OIDC, e.g. IBM App ID), per-user revocation and rate limits.
3. A token in `sessionStorage` is readable by any script that runs in the page. The CSP and the absence of injection sinks reduce that risk; they do not remove it. `style-src` still needs `'unsafe-inline'` (Leaflet sets inline styles). `frame-ancestors` and the other security headers must be set by the host that serves the static bundle.
4. The authenticated *Operational status* panel shows the Db2 product/version, database and schema names. They are not secrets, but a public deployment may prefer to hide them.
5. The public OpenStreetMap tile server is fine for a demo, not for production traffic.
6. Browser coverage is Chromium only (Playwright); Firefox and Safari were not exercised.

## 7. Findings: problems found by looking at the real app, and fixed

Looking at genuine screenshots found problems that the DOM-level tests had not. All are fixed; every behavioural fix has a test:

| Finding | Fix |
|---|---|
| **After a decision the result notice was off screen**: the buttons are at the bottom of a long panel, the notice at the top, so a reviewer who clicked "Confirm" saw nothing happen (found because the 409/403/422/approved screenshots did not show their notices) | The outcome region scrolls into view and takes focus; unit tests assert it; every screenshot now asserts its notice is on screen |
| Raw enum text in the evidence list ("cited by DETERMINISTIC_FALLBACK") | Worded in plain language through the same provenance module ("Cited by the rule-based run (no LLM)") |
| A 22-row evidence table pushed the recommendations ~2000 px down | The list collapses to 8 rows with "Show all 22" |
| Phone: the map filters filled the first screen, the map was below the fold | Filters collapse behind a button (with an active-filter count); the result count stays visible |
| Phone: several tables scrolled sideways and hid the hotspot "Show" link | Secondary columns are dropped on narrow screens (and the evidence table uses container queries); an e2e check now fails if any container scrolls sideways at 390 px or 820 px |
| "Showing 1 complaints and 1 hotspots" (and other singular cases) | Proper singular/plural wording; tests |
| Review queue gave no decision status outside the "Awaiting review" filter | Status badge on items in other filters |
| 422 text read "request: Value error, A comment of …" | Plain message without the pydantic prefix or a pseudo-field name |
| `--color-serious` status colour was defined but unused and failed the palette validator | Removed; the validator output (including the failing status run) is kept as evidence with an explanation |
| `npm run e2e` would also have run the screenshot project (mutating data, overwriting images) | The `e2e` script runs only the functional project |

Earlier in this phase (also covered by tests): initial map fit collapsed hotspot cells when a far-away record existed (now hotspot-first); `sr-only` text inside tables widened the page on phones; a numeric search matched titles containing the digit; the token store kept a hidden in-memory copy after storage was cleared; and four existing backend tests (three unit, one live integration) were changed **deliberately** because the security requirements changed the behaviour they asserted (health endpoints are minimal, the database error body is generic, anonymous complaint intake is now 401); the diff is in `tests/unit/test_api_no_db.py` and `tests/integration/test_db2_live.py`.

**Environment incident (disclosed):** the sandbox worker restarted during final verification and took down Docker, the Db2 container, the API processes and the preview server. Db2's data volume survived; I restarted everything and re-ran, after the restart, the backend suite against live Db2 (138 passed), the live contract test, the whole browser suite and the screenshot capture. The test-result evidence files in this folder and the screenshots come from those post-restart runs. A first pytest attempt made while Db2 was down failed with connection errors and was discarded, not committed.

## 8. Files changed

165 files (`M` = modified, `A` = new); nothing outside `submissions/civiclens-ai/` is touched. Build and test artefacts (`node_modules/`, `dist/`, `test-results/`) and every `.env` are git-ignored.

* **Project files**: 4 (0 new, 4 modified)
  * `.env.example` (M)
  * `README.md` (M)
  * `architecture.md` (M)
  * `submission.json` (M)
* **Backend: application code**: 12 (3 new, 9 modified)
  * `src/backend/civiclens/agent/llm.py` (M)
  * `src/backend/civiclens/agent/tools.py` (M)
  * `src/backend/civiclens/api/deps.py` (M)
  * `src/backend/civiclens/api/investigations.py` (M)
  * `src/backend/civiclens/api/main.py` (M)
  * `src/backend/civiclens/auth.py` (M)
  * `src/backend/civiclens/config.py` (M)
  * `src/backend/civiclens/db/investigation_repo.py` (M)
  * `src/backend/civiclens/domain/investigation_models.py` (M)
  * `src/backend/civiclens/api/dashboard.py` (A)
  * `src/backend/civiclens/db/overview_repo.py` (A)
  * `src/backend/civiclens/domain/overview_models.py` (A)
* **Backend: scripts**: 2 (2 new, 0 modified)
  * `src/backend/scripts/cleanup_test_data.py` (A)
  * `src/backend/scripts/seed_demo_workflow.py` (A)
* **Backend: tests**: 5 (2 new, 3 modified)
  * `tests/integration/test_db2_live.py` (M)
  * `tests/unit/test_agent_tools.py` (M)
  * `tests/unit/test_api_no_db.py` (M)
  * `tests/integration/test_dashboard_live.py` (A)
  * `tests/unit/test_api_dashboard.py` (A)
* **Frontend: configuration, lockfile, scripts, README**: 14 (13 new, 1 modified)
  * `src/frontend/README.md` (M)
  * `src/frontend/.env.example` (A)
  * `src/frontend/.gitignore` (A)
  * `src/frontend/eslint.config.js` (A)
  * `src/frontend/index.html` (A)
  * `src/frontend/package-lock.json` (A)
  * `src/frontend/package.json` (A)
  * `src/frontend/playwright.config.ts` (A)
  * `src/frontend/public/favicon.svg` (A)
  * `src/frontend/scripts/verify-bundle.mjs` (A)
  * `src/frontend/tsconfig.json` (A)
  * `src/frontend/vite.config.ts` (A)
  * `src/frontend/vitest.config.ts` (A)
  * `src/frontend/vitest.live.config.ts` (A)
* **Frontend: application source**: 54 (54 new, 0 modified)
* **Frontend: Vitest suites, MSW handlers, live contract test**: 21 (21 new, 0 modified)
* **Frontend: Playwright specs**: 11 (11 new, 0 modified)
* **Docs: reports**: 1 (1 new, 0 modified)
  * `docs/PHASE_01B_REPORT.md` (A)
* **Docs: evidence**: 11 (11 new, 0 modified)
  * `docs/evidence/README.md` (A)
  * `docs/evidence/backend_static_and_unit.txt` (A)
  * `docs/evidence/bundle_scan.txt` (A)
  * `docs/evidence/contract_live_test.txt` (A)
  * `docs/evidence/e2e_functional_results.txt` (A)
  * `docs/evidence/frontend_checks.txt` (A)
  * `docs/evidence/llm_verification.txt` (A)
  * `docs/evidence/palette_validation.txt` (A)
  * `docs/evidence/pytest_phase01b_live_db2.txt` (A)
  * `docs/evidence/secrets_scan.txt` (A)
  * `docs/evidence/submission_validator.txt` (A)
* **Docs: screenshots (+ manifest and index)**: 30 (30 new, 0 modified)

## 9. Remaining submission requirements (not done, by instruction or because they need the team)

* **Team details:** `submission.json` still has `TODO: full name` (and no e-mail), and the README team table says "to be completed by the team". The official rubric penalises unfilled placeholders.
* **Deadline:** the repository README says the hard deadline is **29 October 2026, 7:00 PM IST**; the brief for this phase says **10 November 2026, 5:00 PM IST**. Please confirm which applies.
* **Submission mechanics (official CONTRIBUTING rules):** a branch named `submission/civiclens-ai` created from `upstream/main`; one PR containing only `submissions/civiclens-ai/` (no root files); PR title `[Submission] civiclens-ai: <Short Project Title>`; conventional commits scoped `feat(civiclens-ai): …`; then the PR URL must be submitted in the official Google Form (the repository still shows `[GOOGLE_FORM_LINK_TO_BE_ADDED]`). Update `project.repo_url` in `submission.json` to the final branch.
* **Demo URL and video:** not deployed, not recorded (`demo_url` and `video_url` are empty). Hosting needs approval, a hosted Db2 and the hardening in §6.
* **Real-LLM run:** BLOCKED on credentials and authorization (§5).
* **Licence:** the dashboard's third-party licences are declared in the README; a licence for the project's own code should be chosen by the team.

## 10. How to reproduce

```bash
# backend (Db2 running, .env or exported variables, CIVICLENS_AUTH_TOKENS with one analyst and two reviewers)
CIVICLENS_DB2_TESTS=1 pytest
cd src/backend && uvicorn civiclens.api.main:app --port 8000 &        # then: python scripts/seed_demo_workflow.py

# frontend
cd src/frontend && npm ci && npm run typecheck && npm run lint && npm test
CIVICLENS_LIVE_API=http://127.0.0.1:8000 npm run test:live
npm run build && npm run verify:bundle && (npm run preview &)
npm run e2e                  # E2E_DB_DOWN_API / E2E_NO_AUTH_API enable the two real 503 tests
npm run screenshots          # regenerates docs/screenshots

# afterwards
python src/backend/scripts/cleanup_test_data.py --workflow --yes
```
