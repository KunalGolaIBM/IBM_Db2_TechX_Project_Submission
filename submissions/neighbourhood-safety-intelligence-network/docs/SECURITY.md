# Security & Privacy

NSIN handles the most sensitive data a neighbourhood has: where people are, who is alone, who is in danger. This document lists every security control, **where it is implemented**, and **the test that proves it**.

## 1. Threat model (what we defend against)

| Threat | Example | Control | Proof |
|---|---|---|---|
| Privilege escalation | A user registers with `"role": "admin"` | Registration accepts only `resident`, `guardian` and `responder`; responders stay unverified until an admin approves them | `tests/test_security.py::test_admin_role_cannot_be_self_registered`, `test_self_registered_responder_needs_admin_verification` |
| Credential stuffing / brute force | Repeated password guesses | Sliding-window throttle per IP + email → `429` with `Retry-After` | `test_login_is_throttled_after_repeated_failures` |
| User enumeration | Probing which emails exist | Identical response and constant-time bcrypt check for unknown emails | `test_unknown_email_and_wrong_password_look_identical` |
| Token forgery | Edited or replayed JWT | HS256 signature + expiry verification; missing / malformed / tampered tokens get `401` | `test_tampered_or_missing_token_is_rejected` |
| IDOR (reading others' data) | Resident opens another resident's private incident by id | Private incidents are visible to the reporter and verified staff only; others get `404` (ids can't be probed) | `test_private_incidents_are_invisible_to_other_residents` |
| Privacy leak | Public alert reveals who reported it and where | Reporter name and coordinates are masked for other residents; responder GPS is hidden from residents | `test_public_alerts_hide_reporter_identity_and_coordinates`, `test_roster_hides_responder_locations_from_residents` |
| Unauthorised writes | Resident resolves someone else's incident; attaches AI analysis to it | Ownership and role checks on every write | `test_residents_cannot_act_on_others_incidents`, `test_ai_triage_cannot_be_attached_to_someone_elses_incident` |
| SQL injection | Malicious text in a report | All SQL is parameterised (ORM, `ibm_db.prepare`, bound `text()` parameters, IBM packages' bound parameters). No user input is interpolated into SQL | Bandit scan (below): 0 issues |
| Oversized / malformed input | 300-character title crashing a Db2 `VARCHAR(255)` | Pydantic schemas with enums, coordinate ranges and lengths sized to the Db2 columns → `422`, never `500` | `test_input_limits_match_db2_column_sizes`, `test_registration_validates_input` |
| Illegal state changes | Re-opening a resolved incident | Explicit state machine; illegal transitions → `409` | `test_incident_state_machine_rejects_illegal_transitions` |
| Audit tampering | Deleting evidence of an action | Audit rows are written in the same transaction as the change; the app's Db2 role cannot `UPDATE`/`DELETE` `audit_events` | `test_least_privilege_login_is_denied_ddl_and_audit_tampering` |
| Database takeover via the app | SQL injection used to `DROP` tables | App runs as a data-only Db2 role: no `CREATE`, `ALTER`, `DROP` | same test (5 statements, all rejected with `SQL0551N`) |
| Error-message leakage | Stack traces revealing SQL | Generic `500` handler; details logged server-side only | `src/backend/app/main.py` (`unhandled_exception_handler`) |
| Prompt injection / data exfiltration through AI | A report that tries to steer the model | The rule-based priority is authoritative; the LLM only explains. Answers must cite a retrieved protocol (`grounded`). The model runs locally, so no resident text is sent to a third party | `tests/test_crew.py`, `tests/test_triage.py` |

## 2. Least privilege in IBM Db2

[`db/least_privilege.sql`](../db/least_privilege.sql) creates role **`NSIN_APP`**:
- `SELECT, INSERT, UPDATE, DELETE` on the application tables only;
- **no DDL**;
- `audit_events` is **insert/read only**.

[`scripts/db2_least_privilege.sh`](../scripts/db2_least_privilege.sh) provisions the login `nsinapp` with that role. The app connects with `DB2_USER=nsinapp DB2_SCHEMA=DB2INST1`. It checks the Db2 catalog (`SYSCAT.TABLES` in `CURRENT SCHEMA`) before any DDL, so the restricted login never attempts it.

The whole test suite runs as this login (`NSIN_KEEP_DB=1 DB2_USER=nsinapp …`), and `test_least_privilege_login_is_denied_ddl_and_audit_tampering` proves that `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`, `UPDATE audit_events` and `DELETE FROM audit_events` are all rejected by Db2.

## 3. Secrets & configuration
- No secret is committed. `.env` is gitignored; `.env.example` holds placeholders only.
- `APP_ENV=production` **refuses to start** with the development JWT secret, with a secret shorter than 32 characters, or with wildcard CORS (`core/config.py::_validate`, tested by `test_production_refuses_development_secrets`).
- Db2 credentials go into the connection URL through `URL.create`, so special characters are escaped (`test_sqlalchemy_url_escapes_credentials_and_adds_options`).
- `/health` hides host, port and database name in production.

## 4. Privacy by design
- **AI runs locally.** IBM Granite models are served by Ollama on the same machine, and embeddings are computed locally too. Resident reports never reach a third-party AI service.
- **Telemetry off.** Haystack and CrewAI usage telemetry are disabled in code and in the container (`HAYSTACK_TELEMETRY_ENABLED=False`, `CREWAI_DISABLE_TELEMETRY=true`, `OTEL_SDK_DISABLED=true`).
- **Data minimisation in responses.** Masked identities and coordinates for non-owners; responders' live location is never shown to residents.
- **Android:** cleartext HTTP is allowed in **debug builds only**, and backups are disabled because the app stores a session token.

## 5. Platform hardening
- Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` and `Cache-Control: no-store` (`test_security_headers_present`).
- CORS: an explicit allow-list of origins and methods.
- Passwords: bcrypt with cost 12; passwords are limited to bcrypt's 72-byte maximum instead of being silently truncated.
- The backend container runs as a non-root user (`uid 10001`).

## 6. Automated scans (reproducible)

| Scan | Command | Result |
|---|---|---|
| Python static analysis (Bandit) | `bandit -r src/backend/app` | **0 issues** (High 0 · Medium 0 · Low 0). Two false positives are annotated with the reason: a token-type label, and a dev secret that production refuses |
| Python dependencies (pip-audit) | `pip-audit` on the exact installed versions | Fixed: `python-jose` was replaced by PyJWT (removing the unfixed `ecdsa`), and `filelock` is pinned to `>=4.2.1`. **Remaining (accepted):** `chromadb` 1.5.9, an indirect dependency of CrewAI used only by CrewAI's optional memory feature. NSIN does not enable crew memory (vectors live in Db2), so the code is never called; no fixed version is published yet |
| Web dependencies (npm audit) | `npm --prefix src/web-app audit` | **0 vulnerabilities** |
| Lint (ruff) | `ruff check src/backend tests --select F,E9,B` | clean |
| Landing site dependencies | `npm --prefix site audit --omit=dev` (deployment repo) | **0 vulnerabilities** |

Last full run: **12 Nov 2026**. Bandit scanned 3,057 lines of backend code.

## 6a. The hosted live demo
The public site lets anyone try the real app. That opens new risks, so here is what we did about each one. Details: [LIVE_DEMO.md](LIVE_DEMO.md).

| Risk | What we did |
|---|---|
| Exposing a home machine to the internet | Only the API port (8000) is tunnelled, over an outbound-only Cloudflare quick tunnel with TLS. No inbound port is opened on the router; Db2 (50000) and Ollama (11434) are never exposed. |
| Cross-site calls to the API | `CORS_ORIGINS` lists the exact Vercel origin and localhost. Wildcards are refused when `APP_ENV=production`. |
| Secrets leaking through the site | `live.json` holds only the public tunnel URL. No keys, tokens or passwords are in the static site; the JWT secret and Db2 password live only in the backend's environment. |
| Demo accounts | Seeded test residents only, with no real people's data. Every action still goes through the same JWT auth, role checks and Db2 audit trail as production. |
| A stale URL breaking the demo | `live.json` is served with `Cache-Control: no-store`, so a new tunnel URL takes effect right away, with no rebuild. |
| Clickjacking of the landing page | `X-Content-Type-Options: nosniff` and a strict `Referrer-Policy` on every page. The app frame is same-origin (`/app/`), so no third-party framing is needed. |

## 7. Reporting a vulnerability
Please open a private security advisory on the repository, or contact the author listed in `submission.json`. Do not include real resident data in reports.
