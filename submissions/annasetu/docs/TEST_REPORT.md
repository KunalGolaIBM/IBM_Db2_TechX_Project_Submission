# AnnaSetu Final MVP Verification Report

Run date: 2026-11-11. All live QA writes in this report were confined to IBM Db2 `ANNATEST`. No test targeted operational database `ANNASETU`; existing records were preserved.

## Runtime and database evidence

| Component | Verified result |
|---|---|
| Docker / Db2 | Existing `annasetu-db2` container is healthy. Engine reports IBM Db2 `12.1.5.0`, fix pack 0. |
| Direct Db2 connection | Python `ibm_db_dbi` connection reports `CURRENT SERVER=ANNATEST`, `CURRENT SCHEMA=DB2INST1`; the eight checked operational tables are present. |
| FastAPI | Running at `127.0.0.1:8010`. `/api/health` returned HTTP 200, `database=IBM Db2`, `database_name=ANNATEST`, and LangChain Db2 vector `ready=true`. |
| React / Vite | Running at `127.0.0.1:5175`. The page, React entry module, and SVG favicon returned HTTP 200; the page includes the React root. |
| CORS | An OPTIONS preflight from `http://127.0.0.1:5175` returned 200 and the exact allowed origin. |

The API was restarted with the latest recovery code, `DB2_NAME=ANNATEST`, development mode, seeding disabled, and CORS limited to the local 5175 frontend. The frontend process was already serving 5175 and remained running.

## Automated test results

| Run | Passed | Failed | Skipped | Result |
|---|---:|---:|---:|---|
| Default backend suite: `python -m pytest -q api/tests` | 58 | 0 | 8 | Passed; the eight live Db2 cases are opt-in and were skipped in this run. |
| Live Db2 integration: `ANNASETU_INTEGRATION=1`, `DB2_NAME=ANNATEST` | 8 | 0 | 0 | Passed against the running IBM Db2 QA database; synthetic QA records remain labelled in `ANNATEST`. |
| Frontend production build: `npm run build` from `frontend/` | — | 0 | — | Passed with Vite 7.3.7; 26 modules transformed and production assets generated. |
| Live API role/auth checks | Passed | 0 | 0 | Health, generic role list, four role logins, invalid credentials, role denial, and non-enumerating reset response all passed. |
| Local HTTP/CORS checks | 4 checks | 0 | 0 | Passed: CORS preflight, Vite page/root, React entry module, and favicon. |

The default suite reported one Starlette/AnyIO `BlockingPortal` deprecation warning. Skipped tests are not counted as passed; all eight were separately executed in the live Db2 suite.

## Authentication and recovery

- The four reserved demo logins in `ANNATEST` accepted the private local QA `DEMO_PASSWORD`; each `/api/me` response returned the matching `admin`, `donor`, `ngo`, or `volunteer` role. Passwords and internal demo emails are not printed here.
- The public role selector returned only generic role labels. Wrong password and unknown email both returned HTTP 401. Donor, NGO, and volunteer tokens received HTTP 403 for the admin-only audit route.
- Live Db2 integration verified signup for donor, NGO, and volunteer QA users, duplicate rejection, password policy and confirmation, role/profile persistence, PBKDF2-SHA256 hashes, and subsequent login. These generated QA users are labelled and reside only in `ANNATEST`.
- Public recovery returned the same generic response for known and unknown accounts and did not reveal or issue a code. In the live Db2 integration test, a non-admin issuance attempt was rejected; an authenticated Admin issued a five-minute, single-use code after identity review. Db2 stored a keyed HMAC digest, and the test verified expiry, invalidation of an older code, single use, password hash update, and successful login with the new password.
- Recovery is an explicitly local development flow. It uses no SMTP, email, SMS, or external provider. A signed-in administrator must verify the requester and hand the code to them directly. Local recovery is disabled outside development; an administrator locked out of the only admin account needs an operator-assisted recovery procedure.

## Db2 workflows and retrieval

The eight live integration tests exercised Db2 schema readiness, reserved demo-account seeding, SQL insert/select/update/rollback, authenticated signup and reset, NGO verification authorization, missing-evidence safety HOLD, human verification, feasibility and expiry rejection, partial capacity allocation, reservation release after failed rescue, audit/evidence mutation rejection, dashboard aggregates, and LangChain `DB2VS` policy retrieval with citations. Audit-chain integrity and the vector index were verified through the application against `ANNATEST`.

The direct read-only Db2 probe reported `CURRENT SERVER=ANNATEST`, `CURRENT SCHEMA=DB2INST1`, Db2 service level `DB2 v12.1.5.0`, and all eight queried core tables. API health independently reported the same active database and vector readiness.

## Browser verification and limitations

Interactive browser verification could not be completed in this run: the Computer Use system reported that it had been stopped by a physical Escape key and instructed this session not to issue further computer-control calls. Therefore this report does **not** claim a fresh browser sign-in, dashboard interaction, or browser-console check against the latest recovery UI. Loopback HTTP checks confirmed that Vite and its React entry module are served, and live API tests verified the corresponding authentication and Db2 operations.

Other MVP limitations: ETA is a straight-line logistics estimate, not live routing or traffic; safety decisions are evidence-based screening, not official certification; handoff and local recovery codes are relayed manually; the policy copilot retrieves and cites Db2 passages but has no generative model configured.

## Reproduction commands (PowerShell)

From `C:\Users\mr.rajat\Desktop\AnnaSetu`:

```powershell
python -m pytest -q api\tests
Set-Location frontend
npm run build
Set-Location ..
```

Run the live suite only against `ANNATEST`, with the private QA `DEMO_PASSWORD` loaded from ignored `.env.qa`, and set `ANNASETU_INTEGRATION=1`. The test module refuses a database name other than `ANNATEST`.
