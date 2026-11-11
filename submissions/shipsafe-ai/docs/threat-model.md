# ShipSafe AI: Threat Model

| Threat | Risk | Mitigation in the code |
|---|---|---|
| Unauthenticated access to the API or UI | High | Bearer tokens (256-bit random) required on every route except health and readiness. Tokens are stored only as SHA-256 hashes in `API_TOKENS`. |
| Privilege escalation between users | High | Roles (`viewer` < `operator` < `admin`) enforced server-side on every route. Admins cannot revoke the token they are signed in with. |
| Scanning arbitrary paths through the API | High | `resolve_target()` resolves symlinks and `..`, then requires the result to sit inside `SHIPSAFE_ALLOWED_ROOTS`. Rejections are audited. |
| Abuse or denial of service through scans | Medium | Per-token scan rate limit, bounded worker pool, per-tool timeouts and output caps. |
| Malicious content in a scanned repository | High | Files are read as text and never modified (read-only mount in Docker). The only code executed is the project's own test suite, and only in the `pre-pr` and `deep` profiles. |
| Command injection through scanner invocation | High | Fixed argument lists with `shell=False`. Tools are run as `python -m <tool>` with the current interpreter. |
| SQL injection in ShipSafe itself | High | All values bound with `?` markers. The schema identifier is validated and row limits are cast to `int`. |
| Secret leakage through storage, logs or reports | High | Evidence is redacted before reaching Db2, reports or clients. The log filter redacts `PWD=`, bearer tokens and `ss_` tokens. Tool JSON is parsed first and redacted per field. |
| Db2 credential exposure | High | Credentials come only from the environment. `DB2_SECURITY=SSL` is supported. A least-privilege runtime role is available (`docs/db2-least-privilege.sql`). |
| Tampering with the audit trail | Medium | `AUDIT_LOG` is append-only for the application role (`INSERT` and `SELECT` grants only). |
| Browser-side attacks on the UI | Medium | Strict CSP (`script-src 'self'`, `frame-ancestors 'none'`), `nosniff`, `no-referrer` and `no-store` on API responses. Same-origin only, with CORS off by default. The token lives in `sessionStorage` for one tab. |
| Prompt injection through policy documents | Low | No LLM acts on retrieved text. Retrieval cannot create findings or change the gate. |
| False confidence from skipped checks | Medium | Skipped or unavailable checks are recorded as `skipped` and prevent a clean `PASS`. |
| Partial writes when Db2 fails mid-save | Medium | The assessment bundle is written in a single transaction and rolled back on any error; the UI reports "not saved". |

## Known gaps
- Scan jobs are held in the API process's memory (results are in Db2). Restarting the API loses the progress of in-flight scans.
- The test-runner check executes the target project's tests. Run ShipSafe in a container or CI sandbox when assessing untrusted repositories.
- There is no SSO yet. Tokens are the only authentication method.
