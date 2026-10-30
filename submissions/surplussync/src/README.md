# SurplusSync · Team HyperX

SurplusSync is a React/Vite + FastAPI + SQLite food-rescue coordination demo. Its specific contribution is an explainable feasibility engine that checks recipient availability, food category, remaining configured capacity after active rescue reservations, simulated travel-time estimates, pickup deadline, and required human-entered safety checks. It ranks eligible recipients and gives explicit rejection reasons. This is a focused project contribution, not a claim of global uniqueness.

## Architecture and data flow

```text
React + Vite browser
  └─ credentialed JSON requests to /api
       └─ FastAPI + Pydantic validation + role authorization
            ├─ explainable deterministic feasibility rules
            └─ SQLite: accounts, profiles, sessions, listings, recipients,
                       plans, rescue reservations, events and audit history
```

The local SQLite database is `backend/surplussync.db`. Startup performs additive schema migrations and preserves existing listing/recipient data. An optional Turso HTTP adapter remains in the code from the earlier serverless deployment attempt; it is inactive unless both private database variables are configured and is not part of the current Railway plan. New accounts are stored with PBKDF2-SHA256 password hashes; the browser receives an opaque HttpOnly session cookie, while unsafe requests also require a session-bound CSRF token. Password reset uses expiring, single-use tokens. Email verification is intentionally not part of signup or login: accounts become usable immediately after signup. Password authentication remains required, and recipient organizations still require separate administrator profile approval.

The frontend uses `VITE_API_BASE_URL` when set and otherwise uses same-origin `/api`. During local development, Vite proxies `/api` to `http://127.0.0.1:8000`; in production, requests stay on the deployed origin. CORS includes the original production origin and local Vite origins by default. Override with comma-separated `SURPLUSSYNC_CORS_ORIGINS` values for the exact known frontend origins.

## Features

- Public landing, signup, login, logout, forgot-password and reset-password screens, with loading and API error feedback.
- DONOR, RECIPIENT, VOLUNTEER and ADMIN roles. Signup cannot request ADMIN. A completed profile opens donor and volunteer access; recipient organizations still need an admin review before receiving offers.
- A local-only presentation account setup creates fictional donor, recipient, volunteer and admin logins. The login help panel appears only in Vite development on localhost and never contains passwords.
- Role-specific onboarding for donor organizations, recipient organizations and volunteers. Recipient addresses are visible to the account and authorized review queue; donors see the separate public receiving area.
- Admin review queue with approve/reject, rejection reasons and security audit entries. Review is an administrative review only; no government or identity provider is connected.
- Donor-owned listings and plans, recipient-side offer acceptance/rejection, and assigned-volunteer collection/delivery updates, enforced on the server.
- One offer per listing at a time. Active offers/rescues reserve configured recipient capacity across listings until rejected, cancelled or delivered. Acceptance rechecks eligibility in a serialized SQLite write transaction.
- Persistent rescue timeline and dashboard metrics scoped to the signed-in role.
- Human food-safety checklist; missing checks block recommendation/acceptance. The software does not certify food safe.
- Fictional demo recipients and static simulated travel-time estimates, clearly labelled in the UI. There is no live routing, traffic, notification service, paid API or real-world delivery confirmation.

## Roles and permissions

| Role | Main permissions |
| --- | --- |
| DONOR | Manage own surplus listings and plans, propose a recipient, mark an accepted rescue ready for pickup, cancel own rescues, assign an approved volunteer. |
| RECIPIENT | Update availability only for the recipient profile they own; accept or reject offers addressed to that profile. |
| VOLUNTEER | View and update only rescues assigned to their account; record collection and delivery. |
| ADMIN | Review profiles, manage demo network data, inspect records, and perform administrative lifecycle actions. Admin accounts are bootstrapped locally, never self-registered. |

## Windows PowerShell setup

Run commands from the project root. Use Node.js/npm and Python 3.10+.
The checked-in frontend has its own `frontend/index.html`, Vite config,
package manifest and lockfile; it starts separately from FastAPI.

For a fresh checkout, create a venv with official Python 3.12 and install
dependencies from the project root when the trusted registries are reachable:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix frontend
```

This computer now has the official Python 3.12.10 user installation. Its
existing `.venv` was repaired in place to use that interpreter; the existing
backend dependencies were retained. In this PowerShell session, `python`
still points to the Windows Store alias until a new terminal refreshes PATH,
so use `& .\.venv\Scripts\python.exe` for backend commands below.

The frontend and backend can be started independently. From the project
root, start the frontend in its own PowerShell terminal:

```powershell
npm run dev --prefix frontend
```

The frontend uses `frontend/index.html` as its Vite entry point and can
render its public welcome/login interface without FastAPI. Authentication,
database-backed pages and rescue actions require the backend; if it is
unreachable, requests show an error and do not simulate successful writes.

In a separate PowerShell terminal, from the project root, start FastAPI:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

For the complete application, run the frontend command in one PowerShell
terminal and the backend command in a second terminal, then open
<http://localhost:5173>. The API is at <http://localhost:8000>;
interactive API documentation is at <http://localhost:8000/docs>.

## Railway preparation and database migration plan

No Railway deployment was made yet. The simplest compatible architecture is one Railway web service built from the existing root `Dockerfile`: it builds React/Vite, then runs FastAPI, which serves both the frontend and `/api/*` from one HTTPS origin. The frontend is built with `VITE_API_BASE_URL=/api`; Railway injects `PORT` and the container command already listens on it. Configure the service health check to `/api/health`.

The backend currently uses `sqlite3` directly. For a low-traffic, single-replica demo, the smallest change is to keep SQLite and attach a Railway Volume at `/var/data`. The container stores `surplussync.db` and private NGO certificate uploads under that mount. Keep one replica: SQLite is not a shared multi-instance database. I updated the Docker environment so uploaded certificates, like the database, use the persistent volume. Without the volume, both paths are ephemeral and the deployment is not data-durable.

After Railway/GitHub access and storage approval, create a Railway project from `rajatrajput2402/SurplusSync`, select branch `main`, and deploy the root Dockerfile. Attach a volume at `/var/data` before the first deployment, then set `SURPLUSSYNC_DB_PATH=/var/data/surplussync.db`, `SURPLUSSYNC_UPLOAD_DIR=/var/data/private_uploads`, and `SURPLUSSYNC_COOKIE_SECURE=true`. Generate a Railway HTTPS domain and configure `SURPLUSSYNC_CORS_ORIGINS` and `SURPLUSSYNC_FRONTEND_URL` to that exact origin. The app uses same-origin `/api`, so it does not need a separate frontend service. Leave `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` unset. Do not seed demo accounts in production; create the first real admin through the private bootstrap utility after the volume is attached. Password reset email is optional and requires the documented private SMTP variables; signup/login do not require email verification.

Railway GitHub autodeploy requires the Railway GitHub app to have contributor access to this repository and the service to be configured to deploy `main`. This workspace has no Railway CLI/token or GitHub CLI/token. A read-only check of the configured `origin` URL returned no remote refs (the local `origin/main` tracking ref may be stale), so no commit or push was attempted. The working tree contains user changes; review and commit them only after Railway access is authorized and any automatic Vercel deployment for this repository is ruled out.

Railway currently documents a $0 Free plan with $1 of included usage credit, a $5/month Hobby subscription with $5 usage included, and volume storage at $0.15/GB/month. Usage beyond the included amount can incur charges. Verify current pricing and approve any paid plan or expected usage in your Railway account before creating resources; none were created here. [Railway pricing](https://docs.railway.com/pricing).


PostgreSQL is not currently compatible with this backend without code changes: connections, schema setup, and migrations use SQLite-specific `sqlite3`/`PRAGMA` behavior. If PostgreSQL is chosen later, first make a protected backup of SQLite and the private certificate directory, implement and test a separate PostgreSQL data layer, import into a new empty staging database preserving IDs and foreign-key relationships, compare per-table counts and integrity, run auth/rescue/ownership tests, and keep the original SQLite copy untouched for rollback. No PostgreSQL service, credentials, migration, or production data upload is configured here. Object/file storage alone is not a relational database.

For a new checkout with an activated venv, `python` can be used in place of
the explicit `.venv` interpreter path. If PowerShell blocks venv activation,
run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate
again.

## Local presentation accounts and administrator setup

For a judge presentation, create the fictional role accounts from a trusted local terminal. The tool asks for one password using a hidden prompt; that password is shared by the local demo accounts and is never printed or embedded in the frontend:

```powershell
& .\.venv\Scripts\python.exe -m backend.seed_demo_accounts
```

The repeatable seed creates or refreshes only these reserved fictional identities: `demo-admin@surplussync.invalid`, `demo-donor@surplussync.invalid`, `demo-volunteer@surplussync.invalid`, and one `demo-recipient-N@surplussync.invalid` account for each fictional demo recipient. Choose a local-only password of at least 12 characters and use it for each role. On the localhost login page, expand **Local presentation accounts** to see the account names and setup instructions. The account names are shown only in Vite development on `localhost` or `127.0.0.1`; no password is included in frontend source or production build.

Running the seed again with the same password does not duplicate accounts or demo records. If a different password is entered, only the seeder-managed demo account password hashes are updated. The additive `user_accounts.is_demo` marker defaults existing/public accounts to non-demo. The seed refuses to adopt a reserved email created through public signup, refuses to take ownership of a record owned by another account, and does not delete listings, recipients, plans, rescue cases, users or audit history. The local demo admin is created only by this trusted local tool; public signup still rejects the ADMIN role.

The tool approves only its own fictional demo profiles, then links those accounts to the existing demo recipient/listing records. Email verification is not part of signup or login. The same normalized email can have separate Donor, Recipient and Volunteer profiles; if an email has multiple profiles, login asks which role to open. A repeat signup for the same email and role is rejected. It does not bypass normal API authorization. Run it only against the local presentation database; never seed demo accounts in a shared or deployed environment. Before sharing a database, disable or rotate the local demo accounts.

For a ready-to-present local donor → recipient → volunteer workflow, run this separate, repeatable local-only seed. It adds three fictional listings (40 Prepared meals, 30 Bakery, 25 Fresh produce), an approved fictional recipient profile in Mathura, and an available fictional volunteer. It stores plans using the actual rule engine. It does not delete existing records, and it refuses a configured remote or Vercel database:

```powershell
& .\.venv\Scripts\python.exe -m backend.seed_demo_workflows
```

The scenario's checklist fields are stored as unverified. The rule engine may show category/capacity/deadline matches for these explicitly fictional fixtures with `simulation_only=true`, while keeping `food_safety_passed=false`; the UI labels offers and lifecycle actions as simulated. This is not safety certification or operational clearance. Normal non-demo listings still cannot pass the mandatory human checks without actual recorded verification. Travel estimates, recipient availability and volunteer availability remain fictional/static.

For a separate non-demo installation that needs its first administrator, use the trusted local bootstrap command instead. It prompts for a password and does not expose admin creation through public signup:

```powershell
& .\.venv\Scripts\python.exe -m backend.create_admin admin@example.org
```

## Demo workflow

1. Run the local demo workflow seed above, then log in as the fictional donor, recipient, volunteer or admin. These reserved demo accounts are created by the trusted local seeder. The same password is the one chosen at the seed prompt.
2. Public signup immediately creates a password-authenticated account. Users can log in without opening an email. Donor and volunteer profiles open after completion; real recipient organizations appear in **Review queue** and remain unavailable until an admin reviews their submitted certificate. The seeded fictional demo recipient is visibly marked as a demo and is not represented as a legally verified organization.
3. As a donor, create a listing. A responsible person must verify each displayed food-handling, temperature, allergen, packaging and local-requirements item. The application does not certify safety.
4. Generate a plan and inspect candidate rankings, remaining-capacity effects, deadline margins and explicit rejection reasons.
5. Propose to an eligible recipient. Log in as that recipient to accept or reject. Rejection records its reason and offers the next eligible recommendation where available.
6. The donor can mark an accepted rescue ready and assign an approved volunteer. That volunteer records collection and delivery. Refresh to confirm the SQLite-backed timeline and dashboard totals.
7. Use the admin-only demo reset to restore the fictional recipient network and unverified sample listing. It preserves user and audit/test listings.

## API overview

All routes below are under `/api`; except health and the explicitly public authentication endpoints, they require a valid session. Unsafe requests require the `X-CSRF-Token` header issued by `GET /auth/csrf`.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/auth/signup`, `/auth/login`, `/auth/logout` | Account creation and session management |
| POST | `/auth/account/delete` | Password and email-confirmed permanent self-deletion |
| GET | `/auth/me`, `/auth/csrf` | Current account and session CSRF token |
| PUT | `/auth/profile` | Submit or revise a role profile; it returns to pending review |
| POST | `/auth/password/forgot`, `/auth/password/reset` | Generic reset request and expiring one-use reset |
| GET / PATCH | `/admin/verifications`, `/admin/verifications/{user_id}` | Admin review queue and decision |
| GET | `/health` | Liveness check |
| GET | `/recipients`; PATCH | `/recipients/{id}/availability` | Recipient network and owned availability |
| POST / GET | `/listings` | Create and list role-visible listings |
| PUT | `/listings/{id}` | Donor edits own unoffered listing; existing plan is recalculated from the saved values |
| DELETE | `/listings/{id}` | Donor deletes own listing and its dependent rescue history |
| POST / GET | `/listings/{id}/plan`, `/plans/{id}/recalculate` | Evaluate or recalculate recipient feasibility |
| POST | `/listings/{id}/rescue/propose` | Offer listing to an eligible recipient |
| POST | `/rescues/{id}/accept`, `/rescues/{id}/reject` | Recipient decision |
| PATCH | `/rescues/{id}/status` | Valid role-authorized lifecycle transition |
| GET / POST | `/volunteers`, `/rescues/{id}/volunteer` | List approved volunteers and assign to an eligible rescue |
| GET | `/rescues`, `/rescues/{id}`, `/dashboard/metrics` | Role-scoped tracking and database-derived counts |
| POST | `/demo/reset` | Admin-only safe reset of explicitly tagged fictional demo data |

## Environment configuration

- `VITE_API_BASE_URL`: optional frontend API base, including `/api`.
- `SURPLUSSYNC_DB_PATH`: optional SQLite database file path. Defaults to `backend/surplussync.db`; useful for an isolated local test/demo database without replacing the existing project database.
- `SURPLUSSYNC_COOKIE_SECURE`: set to `true` behind HTTPS; leave unset for local HTTP.
- `SURPLUSSYNC_CORS_ORIGINS`: optional comma-separated exact origins; configure the Railway HTTPS origin for a future deployment. Local Vite origins are allowed by default.
- `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`: optional legacy Turso adapter settings. They are not PostgreSQL credentials and are not needed for local SQLite or the planned Railway migration.
- SMTP settings in `.env.example` are optional and are used only to send password-reset emails. They are not needed for account signup, login, or profile review. The `.env` file is gitignored; do not commit credentials.
- Account deletion requires the signed-in session, CSRF token, current password, and exact account email. It deletes the account's profile, sessions, password-reset tokens, owned listings and owned recipient record; affected recipient rescues are cancelled, and other rescue history is anonymized. The last active admin is protected.
- `SURPLUSSYNC_FRONTEND_URL`: base URL used in password-reset links; defaults to `http://localhost:5173`.
- `SURPLUSSYNC_DEV_RESET_TOKEN`: local-only opt-in for returning a reset token when SMTP is not configured. Never enable on a public deployment.
- `SURPLUSSYNC_DEMO_PASSWORD`: optional temporary password input for synthetic local demo-account seeding; without it, the tool prompts securely.

No secret is committed or hardcoded by these configuration options. Use a secret manager in any deployment.

## Test and build

```powershell
$PYTHON = ".\.venv\Scripts\python.exe"
& $PYTHON -m py_compile backend\auth.py backend\database.py backend\models.py backend\main.py backend\feasibility.py backend\tests\test_api.py backend\tests\test_feasibility.py backend\tests\test_deployment_database.py
& $PYTHON -m pytest -q
npm run build --prefix frontend
```

The backend suite uses HTTPX's ASGI transport and per-test temporary SQLite databases. On restricted Windows environments, Python's Proactor event loop may require permission for a local socket pair before `asyncio.run` can initialize. This is an execution-environment restriction, not a reason to skip the tests.

### Previous verification recorded for this workspace

- Python compilation: passed for backend source and both test modules using the repaired project venv and official Python 3.12.10.
- Frontend production build: `npm run build --prefix frontend` passed with Vite 6.4.4.
- Browser workflow: an isolated SQLite instance with explicitly synthetic accounts/data was used to create a listing, generate a plan, see feasible and rejected recipients, propose/accept an offer, register and approve a test volunteer, assign the rescue, mark it ready/collected/delivered, refresh, and confirm the persisted timeline plus delivered dashboard totals. The synthetic safety-check values were test fixtures only, not claims about real food.
- Browser offline check: with FastAPI stopped, the frontend welcome/login screen still rendered; attempting login showed a backend-unavailable error and did not create a session.
- Browser testing found and fixed a missing rescue-assignment prop that crashed donor tracking, and pending-profile logout rendering with a null user. The plan loader also now avoids donor-only plan endpoints for recipient/volunteer sessions.
- Browser test services used `.pytest-browser-workflow-20261020/browser.db`, not the shared `backend/surplussync.db`. The isolated database and pytest artifacts were retained; no project data or existing files were cleaned up.
- Final Windows readiness check (2026-10-20): official Python 3.12.10 was installed through WinGet from the Python Software Foundation package, and the existing `.venv` was upgraded in place with its dependencies retained. The latest run compiled the backend and test modules, passed all 35 backend tests in that venv, and built the production frontend. FastAPI started and `/api/health` returned `ok`. Vite served the public page both with FastAPI running and stopped. The browser check was desktop 1280 × 720; mobile viewport emulation was not available, so responsive breakpoints were reviewed in CSS but not browser-tested at mobile size.
- Local demo-account setup was run against the existing `backend/surplussync.db`: 7 explicitly fictional role accounts were added and linked to the existing demo listing/recipients. The pre-existing `abc@gmail.com` account stayed non-demo and pending; counts remained 4 recipients, 10 listings, 8 plans and 10 rescue cases. No listing, recipient, plan, rescue record or existing account was deleted.
- Previous browser checks covered the dashboard and rescue workflows. The current no-email signup/login behavior is covered by isolated HTTPX API tests; it has not been separately clicked through in a browser.
- Production bundle check: the built JavaScript does not contain the local demo login email strings; the account-help panel is development-only and restricted to localhost.
- These checks do not represent independent organization identity verification, food-safety certification, real routing or a deployment security review.

## Known limitations and safety

- Fictional recipient organizations, areas, configured capacities and static travel-minute estimates are demonstration data; estimates are not actual routes, distances, traffic or dispatch commitments.
- Admin profile review is not identity, charity-status, food-safety or government verification.
- Food safety remains the responsibility of the responsible human. The application records self-reported checks and verifier name; it cannot inspect or certify food.
- Recipient access to the operational network needs the existing admin review; this is not government or charity verification. Donor and volunteer profiles can use their role after profile completion, but organization details are self-reported.
- There is no multifactor authentication or identity provider. Email verification is not used; optional password-reset delivery requires SMTP configuration.
- Local SQLite is the active database for development. PostgreSQL support, production persistence and migration have not been implemented or verified.
- Lifecycle milestones are entered by authenticated demo actors, not validated with proof of pickup/delivery.
- Local sessions use non-Secure cookies for HTTP; HTTPS deployments must set `SURPLUSSYNC_COOKIE_SECURE=true`, configure the exact CORS origin, and review secrets and persistent storage.
- Capacity reservations are local configured portion counts; there is no physical inventory, vehicle dispatch, real-time capacity feed or independently verified recipient capacity.


### Signup and login behavior

New and existing users sign in with their email and password immediately; no verification email, verification token, resend endpoint or SMTP setup is part of authentication. Password hashes, secure session cookies, CSRF validation, role checks and administrator-only recipient profile approval remain enforced. Existing SQLite account records and any legacy verification columns or token rows are preserved but ignored by current authentication. SMTP settings remain optional only for password-reset email.

### Current no-email-auth change (2026-10-21)

- Signup and login no longer call email verification; existing password hashes, sessions, role checks and recipient admin approval remain. Legacy SQLite verification timestamps and token rows are preserved but ignored. SMTP is retained only for optional password-reset delivery.
- Verification: complete backend suite **39 passed, 0 failed**; Python compilation passed; Vite production build passed. The tests use isolated temporary databases. Browser signup was not separately exercised.
- Previous Vercel-adapter verification (2026-10-22): backend tests covered fail-closed database selection and remote-driver configuration. The adapter and its tests are retained for now; the Vercel deployment entry point and build configuration were removed in this cleanup. No Railway deployment or database migration was made.

### Shared identity and presentation workflow (2026-10-24)

`user_accounts` now represents one case-insensitive email/password identity. `user_profiles` is keyed by `(user_id, role)` and stores separate DONOR, RECIPIENT, and VOLUNTEER profile JSON, review status, and a fictional-demo marker. Authentication creates one session with a server-side `active_role`; `/api/auth/role-profiles` can add an operational role and `/api/auth/active-role` switches only to a profile already owned by that identity. Each route still checks the active role and resource ownership. ADMIN remains a separate trusted account role and cannot be added through these endpoints.

The one-time SQLite migration preserves IDs and profile rows, adds role-specific profile keys and session role state, and enforces one normalized email per account. It refuses to guess how to merge databases that contain duplicate email identities with possibly different passwords. The local database migration was preceded by a verified SQLite backup; legacy profile rows, account IDs, listings, plans, rescue cases/events and audit rows were preserved. The existing `tournamentgaming07@gmail.com` account and password were not replaced. Its existing Recipient profile remains pending; no certificate, review, or approval was fabricated. Fictional Donor and Volunteer profiles were added as separate demo-marked profiles, and only explicitly tagged demo listings were associated with that identity.

Run `python -m backend.seed_presentation_demo` locally to create or refresh the three labeled scenario listings and persisted plans. Existing account passwords, personal profiles, active rescue histories, and non-demo rows are left alone. If the reserved account is absent, the tool prompts privately for a password; it never prints it. Demo checklist flags are synthetic software-test inputs and are explicitly identified as not human verification or food-safety certification. Recipient organizations still require the normal administrator certificate review before they can accept offers.

For a Render deployment, the Docker image includes the presentation seeder. Startup seeding is **disabled by default** with `SURPLUSSYNC_PRESENTATION_DEMO_ENABLED=false`. To enable repeatable setup for an isolated presentation deployment, configure that flag to `true`, set `SURPLUSSYNC_PRESENTATION_DEMO_EMAIL`, and store `SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD` as a private Render environment secret. A fresh/ephemeral database needs that password to recreate the reserved identity; an existing account's password is never overwritten, and a configured mismatch fails startup safely. Do not enable this flag on a real-user production database without reviewing the seed's ownership scope. No Render deployment was performed by this change.

Render's local SQLite file is durable only when the service has an attached persistent disk mounted at the configured `SURPLUSSYNC_DB_PATH` (`/var/data/surplussync.db`). Free instances without persistent storage may lose local SQLite data across restarts; this seed mechanism can recreate only fictional presentation records, not users' real records. The checked-in Render blueprint currently requests a paid Starter service and a 1 GB disk; verify current Render billing and actual service settings in the dashboard before applying it. No account plan or paid service was changed here.

New API routes: `POST /api/auth/role-profiles` (authenticated, CSRF-protected profile creation) and `POST /api/auth/active-role` (authenticated, CSRF-protected switch). `GET /api/auth/me` returns `available_roles` and role-specific statuses. The login endpoint requires a role choice only after correct password verification when the identity has multiple profiles. A role change does not grant organization approval or ADMIN access.

### Controlled presentation mode and donor listing edits (2026-10-24)

- Presentation mode is off by default. Set `SURPLUSSYNC_PRESENTATION_DEMO_ENABLED=true` only in a local or isolated demo environment. Only an already seeded role profile with the database `demo=1` marker receives the short organization form. It asks for a fictional organization name, receiving area, configured capacity and accepted categories; saving creates a clearly labeled `— DEMO` recipient fixture. No certificate or registration number is requested, and the API labels its state `demo_fixture` rather than official verification. Turning the flag off blocks that profile from operational recipient endpoints. Publicly registered/non-demo organizations continue to require their certificate and administrator review, even while presentation mode is enabled.
- The demo organization is not listed as legally registered, government verified, or food-safe. Its availability and capacity are configured fictional values. Do not enable the mode on a real-user deployment database.
- Donors can select **Edit listing** in Food Listings before an offer starts. Save uses authenticated, CSRF-protected `PUT /api/listings/{id}` with owner enforcement, validates deadline/preparation time and counts, preserves audit/rescue history, records a security audit event, and refreshes any saved plan against current recipient data. Listings lock as soon as their rescue leaves `listed`; the API rejects edits even if a client manually calls the endpoint. Editing never checks any human safety box automatically.
- Backend API tests cover the certificate-free fictional organization setup, rejection of the same shortcut for a real pending organization, role permissions, invalid/past edit dates, ownership, persisted listing edits, plan refresh, and preventing edits after delivery. All three seeded scenario listings use future deadlines and their persisted plans are calculated from current recipient records.
- Local startup seeding remains disabled unless the presentation flag is explicitly enabled. Configure the flag privately for an isolated demo; do not put credentials in `.env.example` or commit `.env`.

### Final verification for presentation changes (2026-10-24)

- Backend: **62 passed, 0 failed** using isolated temporary SQLite databases, including role-switching, certificate-free demo recipient setup, the donor-to-recipient offer/accept path, listing edit persistence, owner checks, past-deadline rejection, and the completed-rescue lock.
- Frontend: `npm run build --prefix frontend` passed with Vite 6.4.4. Python compilation and `git diff --check` passed.
- The existing local database was checked read-only: `integrity_check=ok`, zero foreign-key violations, one reserved account, and all three persisted demo scenarios had saved plans with four feasible candidates each. No personal profile was converted or approved. The reserved account's existing Recipient profile is still non-demo and pending administrator review.
- The certificate-free form was verified through FastAPI integration tests using an isolated newly seeded demo identity. Browser-based interaction was not run in this final pass. The existing reserved identity cannot use the shortcut for its preserved non-demo Recipient profile; to use the presentation-only flow, seed an unused demo identity by setting a new `SURPLUSSYNC_PRESENTATION_DEMO_EMAIL`, a private `SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD`, and `SURPLUSSYNC_PRESENTATION_DEMO_ENABLED=true` in an isolated local demo environment. Never put a password in this template or commit `.env`.

### Optional IBM Db2 + LangChain analysis

The Db2Hack integration keeps SQLite as the operational database. Authenticated, approved Donors can analyze their own listings; Admins can analyze listings for review. `GET /api/ai/db2/status` checks the Db2 connection, and `POST /api/ai/db2/analyze` snapshots the listing and its saved candidate evaluations to IBM Db2, reads that snapshot back, and produces an evidence-grounded explanation. Snapshot replacement is transactional: existing Db2 records remain if a write or read-back check fails. Db2 errors return a clear unavailable response; this workflow never falls back to SQLite while claiming it used Db2. Direct connection strings must use TLS (`SECURITY=SSL`).

Install the added packages from `requirements.txt`. Configure either `DB2_CONNECTION_STRING` or `DB2_DATABASE`, `DB2_HOSTNAME`, `DB2_PORT`, `DB2_UID`, and `DB2_PWD` in the ignored local `.env` or the deployment's private environment. `DB2_SECURITY` defaults to `SSL`; direct connection strings are also required to use TLS. The optional `WATSONX_API_KEY` (current IBM spelling; legacy `WATSONX_APIKEY` is accepted) and `WATSONX_PROJECT_ID` enable `ChatWatsonx`; `WATSONX_URL` and `WATSONX_MODEL_ID` have documented defaults in `.env.example`. Without watsonx credentials, the endpoint labels the answer `rules_only`; a failed model call is also labeled as a rules-only fallback. It does not claim a trained model or certify food safety. The integration sends only listing operational fields and evaluated recipient evidence to Db2/watsonx; it excludes account IDs, email, verifier names, and other account profile data.

Both routes require an authenticated, approved DONOR or ADMIN session. POST also requires the existing `X-CSRF-Token` header. In a signed-in same-origin browser session, retrieve `/api/auth/csrf`, then send the returned token with `POST /api/ai/db2/analyze` and JSON such as `{"listing_id": 12, "question": "Explain the capacity and deadline evidence."}`. `GET /api/ai/db2/status` reports connection/configuration state without returning driver details. No public or anonymous access is added.

Create the `SURPLUSSYNC_AI_RECORDS` table in the configured Db2 schema or grant the application user narrowly scoped table-creation rights for first use; it needs select/insert/update/delete on this one integration table to replace and verify each listing snapshot. Review IBM service data handling and credentials before enabling watsonx. No Db2 connection or LLM call is assumed to have succeeded until configured and tested.
