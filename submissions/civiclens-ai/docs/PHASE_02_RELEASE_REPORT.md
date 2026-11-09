# CivicLens AI: Phase 02 release report (submission readiness)

Prepared on 9 November 2026 (UTC), on branch `feat/civiclens-final` (cut from `feat/civiclens-phase01b`), against the **official repository's current `main`**: `KunalGolaIBM/IBM_Db2_TechX_Project_Submission` at `4d685c2` (last commit 29 October 2026; it has a single branch, `main`).

**Nothing was submitted.** No pull request was opened, no form was filled, nothing was deployed, and no paid API call was made. Every number below comes from a command that was run on the final code; the raw output is in [`evidence/`](evidence/README.md).

## 0. Verdict

| Question | Answer |
|---|---|
| Is the folder ready to become the pull request? | **Yes, technically.** The official validator passes (alone, and exactly as CI runs it for all four submissions with ours added). The change touches nothing outside `submissions/civiclens-ai/`. Secret scans report 0 findings. |
| What stops you submitting right now? | Only things that need **you**: choose a licence, agree to the Code of Conduct, confirm your name and the team name, get the Google Form link, confirm the deadline, and give the go-ahead to open the PR (section 3). |
| Was a real language model used? | **No. Real-LLM verification is BLOCKED**: no application credentials exist, the coding assistant's own gateway credentials were deliberately not reused, and no call was attempted (section 5). Every recommendation is labelled rule-based or manual. |
| Defects found | 1 medium and 2 low, **all fixed and proven by tests or a re-run**; 2 medium and 1 low remain open and are documented, 1 low is accepted (dev-only); 3 informational. **None critical or high** (section 4). |
| Safe to put on the public internet? | **No** (public read endpoints, static tokens, no rate limiting). It is submitted as a local, reproducible project; the README and the PR text say so. |

## 1. Confirmed completed requirements

Official sources: `CONTRIBUTING.md`, `submissions/README.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/validate-submission.yml` and `scripts/validate_submission.py`, read from the official `main`. The full matrix, with the evidence for each row, is in [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md).

| Requirement | Status | How it was checked |
|---|---|---|
| Folder `submissions/civiclens-ai/`, slug `^[a-z0-9]+(-[a-z0-9]+)*$`, equal to `submission.json → project.slug` | Met | the official validator |
| Required files `README.md`, `architecture.md`, `submission.json`, `.env.example` (each at least 20 bytes), plus `src/` | Met | validator; the README and `architecture.md` were also compared section by section with `_template` (nothing missing) |
| `submission.json` has title, slug, team name, at least one member, `ibm_db2.edition`, `ibm_db2.connector` | Met | validator |
| No `.env`, `.pem`, `.key`, `.pfx`, `.p12`, `id_rsa` or `id_ed25519` anywhere in the folder | Met | validator (it walks the whole folder, including any virtualenv or `node_modules` left inside it) |
| No secrets or credentials committed; `.env.example` has placeholders only | Met | [`secrets_scan.txt`](evidence/secrets_scan.txt) (literal values of the real secrets are searched for, 0 findings), [`bundle_scan.txt`](evidence/bundle_scan.txt) (the built frontend, 0 findings) |
| Scope isolation: the PR changes only `submissions/civiclens-ai/` | Met | `git diff --name-only` against the official `main` lists 0 paths elsewhere ([`fresh_clone_run.txt`](evidence/fresh_clone_run.txt), step 4) |
| CI as it will run on the PR | Met | the workflow's command (`python scripts/validate_submission.py`, no arguments) passes on the official `main` with our folder added ([`fresh_clone_run.txt`](evidence/fresh_clone_run.txt), step 3) |
| Setup instructions work from a fresh environment | Met | new clone of the official `main`, new virtualenv, new `node_modules`: lint, 108 unit tests pass (3 optional-provider tests skip), 245 frontend tests, production build, bundle scan |
| Screenshots in the project folder | Met | 28 genuine captures from the running app with a manifest ([`screenshots/README.md`](screenshots/README.md)) |
| IBM Db2 used for real work, and shown | Met | 149 backend tests against live Db2 with no database mocks; smoke-test result JSON; 63 browser tests through Db2 |
| PR description follows the official template | Met | [`PR_DESCRIPTION.md`](PR_DESCRIPTION.md) mirrors all ten sections of `.github/PULL_REQUEST_TEMPLATE.md` |
| Branch and title conventions | Met (by the commands in section 7) | branch `submission/civiclens-ai` cut from `upstream/main`; title `[Submission] civiclens-ai: CivicLens AI, Db2-backed urban infrastructure investigations`; commits use the `feat(civiclens-ai): …` scope |
| The PR targets the official repository's `main` | Confirmed | `git ls-remote` of the official repository: its `HEAD` is `refs/heads/main`, the only branch |

**Placeholders.** Every placeholder in the folder was found and handled; the list is in [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) section 2. Fixed: the `TODO: full name` in `submission.json` and the `_To be completed by the team_` row in the README, both now `Tej Sagar`, the public display name of the GitHub account `tej-1916` (read through GitHub; not guessed). Left empty on purpose: the member e-mail, `demo_url` and `video_url` (no verified value exists). Required by the rules: the `change_me_…` values in `.env.example`.

## 2. Test and check results

All run on 9 November 2026 against the final code. Raw output for each row is in `docs/evidence/`.

| Check | Result | Evidence |
|---|---|---|
| Backend lint and format (`ruff check`, `ruff format --check`) | pass, 71 files | [`backend_static_and_unit.txt`](evidence/backend_static_and_unit.txt) |
| Backend unit tests in a clean environment (no database, no tokens, no LLM settings) | **111 passed** | same file |
| Whole backend suite against **live IBM Db2 12.1.5**, no mocks | **149 passed, 1 skipped** (the opt-in real-LLM test), 47 s | [`pytest_phase02_live_db2.txt`](evidence/pytest_phase02_live_db2.txt) |
| Backend line coverage of the application code, live Db2 run | **97 %** of 1,533 statements (lowest file 91 %) | [`coverage_backend.txt`](evidence/coverage_backend.txt) |
| Frontend type check, ESLint | pass | [`frontend_checks.txt`](evidence/frontend_checks.txt) |
| Frontend component and API-integration tests (Vitest) | **245 passed** (16 files) | same file |
| Real TypeScript API client and schemas against the running FastAPI and Db2 | **8 passed** | [`contract_live_test.txt`](evidence/contract_live_test.txt) |
| **Browser tests** (Playwright, Chromium) on the production build, real backend and Db2 | **63 passed** in 6.1 min (accessibility 11, authentication 8, complaints 5, errors 3, map 8, overview 7, responsive 5, review 8, workflow 8) | [`e2e_functional_results.txt`](evidence/e2e_functional_results.txt) |
| Built bundle scan (literal secrets, database identifiers, CSP present) | 0 findings | [`bundle_scan.txt`](evidence/bundle_scan.txt) |
| Repository secret scan (literal values of 4 real secrets plus patterns) | 0 findings | [`secrets_scan.txt`](evidence/secrets_scan.txt) |
| Official submission validator | passed | [`submission_validator.txt`](evidence/submission_validator.txt) |
| Dry run of the whole submission procedure from a fresh clone | passed | [`fresh_clone_run.txt`](evidence/fresh_clone_run.txt) |
| Dependency audit | `pip-audit`: 0 known vulnerabilities in all three requirement files; `npm audit --omit=dev`: 0; `npm audit` (everything): 10 moderate, dev-only (see S7) | [`dependency_audit.txt`](evidence/dependency_audit.txt) |
| Endpoint authorization matrix measured on the running API | 20 operations: 15 need a token, 5 are public reads; a bad token is 401 everywhere; analyst-only and reviewer-only operations answer 403 to the other role; **no database connection is made before authorization** | [`endpoint_auth_matrix.txt`](evidence/endpoint_auth_matrix.txt) |

**How the areas you named are covered** (live Db2 unless stated):

| Area | Tests |
|---|---|
| Authenticated review actions | `test_creator_cannot_review_their_own_investigation`, `test_second_or_conflicting_decision_is_refused`, `test_concurrent_decisions_exactly_one_wins`, `test_api_full_workflow`, `test_api_manual_proposal_validation_and_self_review_denial`; in the browser `review.spec.ts` (approve and reject recorded by Db2, real 401, 403, 409, 422) |
| Evidence integrity | `test_fabricated_and_unattached_evidence_is_rejected` (the application's check), `test_db2_itself_rejects_evidence_bypassing_the_application` (the composite foreign key, hit directly), `test_llm_fabricated_evidence_is_rejected_in_llm_mode` |
| Db2 transactions | `test_approval_is_atomic_audited_and_closes_the_investigation`, `test_failure_mid_decision_rolls_everything_back`, **new in this phase** `test_the_unique_index_is_a_database_backstop_and_rolls_back_the_status_flip` |
| Safe database connectivity | `test_authentication_happens_before_any_database_connection`, `test_health_endpoints_reveal_nothing_about_the_server`; generic 503 bodies (unit tests, and real outages in `errors.spec.ts`); bound parameters only (`ibm_db.prepare`/`execute`); the Db2 container is bound to `127.0.0.1` |
| Secret handling | the two scanners above; `auth.spec.ts` (the token lives only in the tab's `sessionStorage`, never in the URL, the DOM, `localStorage` or a cookie, and is sent only to the API as a bearer header); `.env.example` placeholders |

**What these numbers do not cover** (stated so nobody reads more into them): a real language-model provider; TLS to a hosted Db2 (the code path exists, `DB2_SECURITY=SSL`, but only the local container was used); any browser other than Chromium; performance, load or accuracy (none was measured, so none is claimed).

## 3. Remaining blockers and items that need you

| # | Item | Why it is not done | What to do |
|---|---|---|---|
| 1 | **Licence for your own code** | the PR checkbox "License Declared" asks for one; nobody else can choose it for you | pick MIT, Apache-2.0 or other terms; ready-to-paste MIT text and the README line are in [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) section 3 |
| 2 | **Code of Conduct** | each member must agree | read `CODE_OF_CONDUCT.md`, then tick the box yourself |
| 3 | **Name, team name, other members, e-mail** | only `Tej Sagar` could be verified (GitHub profile name of `tej-1916`); the team name `CivicLens` was derived from the project name; the e-mail was left empty so no contact detail is published without your say-so | confirm or change `team.name` in `submission.json`; add other members to `submission.json`, the README table and the PR; add an e-mail only if you want it public |
| 4 | **Deadline** | the official README still says 29 Oct 2026, 7:00 PM IST; your brief says **10 Nov 2026, 5:00 PM IST** (11:30 UTC). The repository shows no update | confirm the later date in the official community channel |
| 5 | **Google Form link** | the official `CONTRIBUTING.md` still reads `[GOOGLE_FORM_LINK_TO_BE_ADDED]` | get the link from the organisers; opening the PR is only step 1 |
| 6 | **Go-ahead to open the PR and submit the form** | by instruction neither was done | say so and I will do the branch step (section 7) and, if this session's tools can reach the official repository, tell you what the PR needs; or run sections 7 and 9 yourself. The Google Form entry is yours in either case (I cannot fill an external form) |
| 7 | Demo video link (optional) | the file is in the repository; no hosted copy exists | upload it if you want a URL, then fill `project.video_url` and the PR line; or record your own voice-over from [`DEMO.md`](DEMO.md) |
| 8 | Real-LLM run (optional) | BLOCKED, see section 5 | needs your credentials and your authorization, because the call is billable |
| 9 | Hosting (not required) | not safe yet, see S4 and S5 | do not fill `demo_url` |

## 4. Security and quality findings

Method: a read of every authentication, role, evidence, transaction and provider path against the behaviour the README and the demo claim; a measured authorization matrix; secret, bundle and dependency scans; a from-scratch run of the documented procedure; and tests that were shown to **fail without** each fix. No critical or high finding was proven, so no large change was made.

| ID | Severity | Finding | Status |
|---|---|---|---|
| S1 | Medium | **A failing language-model call escaped the agent loop as an unhandled exception** (wrong key, unknown model, rate limit, network). In *Auto* mode that skipped the promised labelled fallback and ended in a generic 500, exactly the case the fallback exists for. | **Fixed.** The loop now raises a structured `LLM_PROVIDER_ERROR` carrying only the exception class (provider exception text can contain request details). *Auto* degrades to the labelled rule-based run and states the reason; *LLM only* returns a retryable 502; a client that cannot be constructed is reported by class only; nothing from a failed call is ever stored as LLM output. 6 tests fail on the previous code and pass now. |
| S2 | Low | The 503 `AUTH_MISCONFIGURED` body repeated the configuration parser's reason to anonymous callers; that reason can name a configured user id. | **Fixed.** The body is generic; the reason is logged server-side. Unit test added. |
| S3 | Low | The README told readers to create `.venv` inside the submission folder. The virtualenv's certificate bundles (`cacert.pem`) then made the **official validator fail** with three "potential secret" errors. Found by the from-scratch run. | **Fixed.** The README uses an environment outside the folder and explains why; the run now passes. |
| S4 | Medium | The Phase 00 read endpoints `GET /api/complaints`, `GET /api/complaints/{id}` and `GET /api/hotspots` are public (synthetic data), and `GET /api/health/db` is unauthenticated and opens one Db2 connection per call. There is no rate limiting, so an anonymous caller can generate database load. Their bodies reveal nothing about the server, and they are read-only. | **Open, documented.** Changing a public contract is not a small change; protect or throttle them before any public deployment. |
| S5 | Medium | Static bearer tokens from the environment: no expiry, revocation, rotation or real identity provider, and no rate limiting or lockout on guessing (a 24-character minimum and a constant-time comparison mitigate guessing). | **Open, documented.** Suitable for a local demo; use OIDC (for example IBM App ID or an enterprise provider) and a rate limiter before exposure. |
| S6 | Low | `GET /api/overview` (any signed-in role) reports the Db2 product, version, database name and schema to the dashboard's status panel. | **Open, documented.** Authenticated only; restrict it to a role or drop it before public use. |
| S7 | Low | 10 moderate npm advisories (`minimatch`, GHSA-g3hv-75wg-m249, regular-expression denial of service) in the ESLint toolchain. | **Accepted.** Dev-only, not in the built bundle; `npm audit --omit=dev` and `pip-audit` report 0. |
| S8 | Info | The four-eyes rule is vacuous today (analyst and reviewer are disjoint roles) but is also enforced inside the review transaction and tested. | Defence in depth, kept. |
| S9 | Info | TLS to a hosted Db2 is coded but untested; one connection is opened per request (no pool). | Documented; fine at this scale. |
| S10 | Info | The Content-Security-Policy is a `<meta>` tag, so `frame-ancestors` must be set as an HTTP header by whatever hosts the build; `style-src 'unsafe-inline'` is needed by Leaflet; the token is in `sessionStorage`, so a script-injection bug would expose it (mitigated by `script-src 'self'`, no third-party scripts and React's escaping). | Documented. |

## 5. Real-LLM verification: BLOCKED

| Step | Result |
|---|---|
| Is a provider, model and key configured **for the application**? | No. `LLM_PROVIDER` is `none`; no application key variable exists (checked by variable **names** only, in the shell, in the application's settings file and in the running API's environment). |
| Anything else that could be borrowed? | The sandbox sets `ANTHROPIC_BASE_URL` (and a host-management flag) for the coding assistant. Those are the assistant's own gateway settings, not the application's, so per your instruction they were **not reused**. |
| No-network readiness check (new `src/backend/scripts/llm_preflight.py`) | prints `BLOCKED`, exit code 2, in both the plain shell and with the application's settings loaded |
| The opt-in real-LLM test (`tests/integration/test_llm_provider_live.py`) | skipped, as designed, without `CIVICLENS_LLM_TESTS=1` |
| Paid or network model call attempted | **None** |
| What is verified instead | the agent loop with a scripted test double that the UI labels "Test double · not a real model": allow-listed tools only, step limit, timeout, JSON validation, every cited complaint must have been returned by a tool in the same run, no SQL tool and no write tool, provider-failure handling (S1) |
| What stays unverified | an actual model's output, and the IBM watsonx.ai client, which authenticates when it is created and so cannot even be constructed without credentials (reviewed statically only) |

Consequently **nothing in the demo, the screenshots, the PR text or the LinkedIn draft says or implies that a language model produced anything**; the dashboard labels each recommendation with its stored author, and the *Agent transparency* page shows 0 from a language model. Evidence: [`llm_verification.txt`](evidence/llm_verification.txt). To unblock, follow its last section; it needs your credentials and your authorization, and it is a single bounded run.

## 6. Demo status

| Item | Status |
|---|---|
| Demonstration script, seven topics in the order you asked for (problem, Db2 architecture, hotspot detection, investigation and evidence, recommendation and provenance, human review and audit, real LLM versus fallback), with a spoken-text column, likely questions and a slide outline | Done: [`DEMO.md`](DEMO.md) |
| Genuine screenshots | 28 captures from the running app plus a manifest, none edited or composited: [`screenshots/`](screenshots/README.md) |
| Recording | **Done, captured safely**: [`demo/civiclens-demo.mp4`](demo/civiclens-demo.mp4), 1280×720, 3 min 46 s, 4.4 MB, silent with text captions. The browser was signed in off camera (the sign-in screen never appears, nothing is typed or pasted) and the app never renders a token, so no credential is on screen; sampled frames were checked. It is the real production build, backend and Db2, recorded live by `npm run demo` (not composited). |
| What the recording shows | a new investigation is created, six pieces of evidence are attached, the rule-based investigator runs ("NO LLM WAS USED" and why), a second person approves the recommendation, the audit trail is read back from Db2, and the transparency page counts 0 from a language model |
| What it deliberately does not show | any language-model output, a live deployment, or a voice-over |

## 7. Exact commands: create the final submission branch

The required branch name is `submission/civiclens-ai` (from `CONTRIBUTING.md`), cut from the official `main`. Run these in **your clone of your fork** (`origin` = `https://github.com/tej-1916/IBM_Db2_TechX_Project_Submission`). They produce **one clean commit authored by you** that contains only `submissions/civiclens-ai/`. The work branch `feat/civiclens-final` is pushed to `origin` for this purpose.

```bash
# 0. check where you are, and that your commit identity is yours
git remote -v
git config user.name && git config user.email

# 1. add the official repo as "upstream" (skip if it already exists), then fetch
git remote add upstream https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission.git
git fetch upstream main
git fetch origin feat/civiclens-final

# 2. the submission branch, cut from the OFFICIAL main
git checkout -b submission/civiclens-ai upstream/main

# 3. bring in ONLY the project folder from the finished work
git checkout origin/feat/civiclens-final -- submissions/civiclens-ai

# 4. scope and validator checks (the first command must print only the OK line; CI runs the validator without arguments)
git status --short | grep -v " submissions/civiclens-ai/" || echo "OK: only submissions/civiclens-ai/ changed"
python scripts/validate_submission.py
git ls-files -o --exclude-standard | head          # must be empty (no stray untracked files)

# 5. (optional) apply your licence here (SUBMISSION_CHECKLIST.md section 3), then commit once
git add submissions/civiclens-ai
git commit -m "feat(civiclens-ai): add CivicLens AI hackathon submission"
git push -u origin submission/civiclens-ai
```

Do not create a virtualenv or `node_modules` inside `submissions/civiclens-ai/` on that branch before running step 4 (the README explains the setup with an environment outside the folder), because the validator walks every file in the folder.

## 8. Final PR checklist

The official template's section 6, with what is verified and what is yours to tick.

- [x] **Folder Structure:** one new directory, `submissions/civiclens-ai/`.
- [x] **Naming Conventions:** slug `civiclens-ai`, branch `submission/civiclens-ai`, title `[Submission] civiclens-ai: …`.
- [x] **Complete Documentation:** `README.md` and `architecture.md` complete, no unfilled markers.
- [x] **Metadata File:** `submission.json` valid, validator passes.
- [x] **No Secrets or Credentials:** scans clean; `.env.example` placeholders only.
- [x] **Tested Setup Instructions:** run from a fresh clone and against live Db2.
- [ ] **License Declared:** yours (item 1 of section 3).
- [ ] **Code of Conduct:** yours (item 2).
- [x] **Scope Isolation:** only `submissions/civiclens-ai/` (re-checked by step 4 above).
- [ ] **Google Form Submission:** yours, after the PR exists.

## 9. GitHub and Google Form submission steps (none performed)

1. Settle items 1 to 5 of section 3. Decide whether to include a licence file (step 5 of section 7 is the place).
2. Run the commands of section 7. The branch `submission/civiclens-ai` is now on your fork.
3. Open the pull request **from** `tej-1916/IBM_Db2_TechX_Project_Submission` branch `submission/civiclens-ai` **to** `KunalGolaIBM/IBM_Db2_TechX_Project_Submission` branch **`main`**.
   * Title: `[Submission] civiclens-ai: CivicLens AI, Db2-backed urban infrastructure investigations`
   * Body: paste [`PR_DESCRIPTION.md`](PR_DESCRIPTION.md); tick only the boxes that are true for you (section 8).
   * Or: `gh pr create --repo KunalGolaIBM/IBM_Db2_TechX_Project_Submission --base main --head tej-1916:submission/civiclens-ai --title "[Submission] civiclens-ai: CivicLens AI, Db2-backed urban infrastructure investigations" --body-file submissions/civiclens-ai/docs/PR_DESCRIPTION.md`
4. Watch the **Validate Project Submission** action turn green. If it fails, open its log; the usual causes are files outside the slug, a missing file, invalid `submission.json`, or a committed `.env`/key file.
5. Copy the PR URL (`https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/pull/<number>`).
6. **Submit that URL in the official Google Form** (link from the organisers). A PR alone does not complete the submission.
7. You may keep pushing to `submission/civiclens-ai` until the deadline; the PR updates itself. Do not close and reopen it.
8. Optionally publish the post from [`LINKEDIN_SUMMARY.md`](LINKEDIN_SUMMARY.md) (it makes no claim beyond what was verified, and says plainly that no real LLM was run).

## 10. What changed in Phase 02

All inside `submissions/civiclens-ai/`. Application changes were limited to proven defects (S1, S2) and one small tool.

| Area | Files |
|---|---|
| Application code (modified) | `src/backend/civiclens/agent/runner.py`, `agent/investigate.py`, `agent/llm.py`, `auth.py` |
| New tool | `src/backend/scripts/llm_preflight.py` (no-network LLM readiness check) |
| Tests | `tests/unit/test_agent_runner.py`, `tests/unit/test_fallback_and_llm.py`, `tests/unit/test_auth.py`, `tests/integration/test_investigations_live.py` (provider failures, construction failures, preflight, generic 503, unique-index backstop) |
| Demo | `src/frontend/e2e/demo.spec.ts` (new), `src/frontend/playwright.config.ts`, `src/frontend/package.json` (the `demo` project and script), `docs/demo/civiclens-demo.mp4` |
| Submission documents (new) | `docs/DEMO.md`, `docs/SUBMISSION_CHECKLIST.md`, `docs/PR_DESCRIPTION.md`, `docs/LINKEDIN_SUMMARY.md`, this report |
| Metadata and README | `submission.json` (member name, repository URL), `README.md` (demo, preflight, venv location, counts) |
| Evidence | refreshed: `backend_static_and_unit`, `bundle_scan`, `contract_live_test`, `e2e_functional_results`, `frontend_checks`, `llm_verification`, `secrets_scan`, `submission_validator`, index `README`; new: `coverage_backend`, `dependency_audit`, `endpoint_auth_matrix`, `fresh_clone_run`, `pytest_phase02_live_db2` |

Not changed: the validator, any root file, any other submission, the database schema.

## 11. How to reproduce

```bash
cd submissions/civiclens-ai && cp .env.example .env            # set DB2_PASSWORD and CIVICLENS_AUTH_TOKENS
docker compose -f docker-compose.db2.yml up -d                  # first start takes a few minutes
python3 -m venv ~/.venvs/civiclens && . ~/.venvs/civiclens/bin/activate   # outside the folder (see S3)
pip install -r src/backend/requirements-dev.txt
python src/backend/scripts/db2_migrate.py && python src/backend/scripts/seed_synthetic.py
CIVICLENS_DB2_TESTS=1 pytest                                    # 149 passed, 1 skipped
python src/backend/scripts/llm_preflight.py                     # BLOCKED unless you configure a provider
cd src/frontend && npm ci && npm run typecheck && npm run lint && npm test   # 245 tests
npm run build && npm run verify:bundle
# browser tests (`npm run e2e`) need the API, Db2 and `npm run preview` running: see the README, "Testing & Verification"
```

## 12. Time

The deadline in your brief is **10 November 2026, 5:00 PM IST (11:30 UTC)**. This report was finished at about 18:10 UTC on 9 November, so roughly 17 hours remain. Sections 7 to 9 take about 15 minutes once items 1 to 5 of section 3 are settled.
