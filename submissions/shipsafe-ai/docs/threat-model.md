# ShipSafe: Threat Model

ShipSafe runs on a developer's machine, is launched by an AI IDE, reads code the assistant wants to
write, talks to a Db2 database and a local model server, and can also serve a team API. Each row lists
a threat, its risk, and the mitigation in the code.

## IDE add-on (MCP server, extension, CLI)

| Threat | Risk | Mitigation |
|---|---|---|
| A prompt-injected assistant asks a tool to read files outside the project | High | `resolve_in_workspace()` resolves symlinks and `..` and refuses any path outside the workspace root |
| Malicious code in a snippet executes during a check | High | Checks parse and pattern-match text only. Bandit analyses a temporary copy and never imports or runs it. |
| The model's "fix" weakens security or breaks behaviour | High | Fixes are re-checked with the same deterministic rules; unverified fixes are flagged and need explicit confirmation. Db2 API misuse is a blocking rule. |
| Invented policy references mislead the developer | Medium | Cited ids are checked against the ids Db2 returned; unknown ids are marked `(unverified)` |
| SQL validation modifies data | High | Statements are only PREPAREd (never executed) and the transaction is rolled back |
| Command injection through tool invocation | High | Fixed argument lists, `shell=False`, timeouts, empty stdin, output caps |
| Code or telemetry leaves the machine | High | Local Granite via Ollama; CrewAI, LiteLLM and Haystack telemetry disabled at import |
| A hung dependency freezes the IDE | Medium | Db2 connect timeout, subprocess timeouts, native modules loaded before the stdio transport |
| Oversized inputs exhaust memory | Low | 400 KB per inline check, 50 files per call, 4,000 characters per memory |
| Memory poisoning: wrong "decisions" saved and recalled later | Medium | Memories record their author (IDE name) and time, are scoped per project, and can be deleted (`forget`); recall returns similarity scores so weak matches are visible |

## Data layer (IBM Db2)

| Threat | Risk | Mitigation |
|---|---|---|
| SQL injection in ShipSafe itself | High | All values bound with `?` markers, including row limits; schema identifier validated; Bandit shows 0 medium/high findings |
| Credential exposure | High | Credentials only from environment or `~/.shipsafe/.env`; connection strings never logged; `PWD=` redacted |
| Tampering with history | Medium | `AUDIT_LOG`, `GUARD_EVENTS`, `FIX_ATTEMPTS` are INSERT/SELECT only for the app role; retention only through `SP_PURGE_HISTORY` |
| Partial writes | Medium | Assessment bundle saved in one transaction with rollback on error |
| Stale or dead connections | Low | Pool validates with a ping before reuse and replaces broken connections (tested by killing a real connection) |

## Team API and dashboard

| Threat | Risk | Mitigation |
|---|---|---|
| Unauthenticated access | High | Bearer tokens required on every route except health/readiness; stored as SHA-256 hashes |
| Privilege escalation | High | Roles enforced server-side on every route; admins cannot revoke their own token |
| Scanning arbitrary paths | High | `resolve_target()` allow-list (`SHIPSAFE_ALLOWED_ROOTS`); rejections are audited |
| Abuse through scans | Medium | Per-token rate limit, bounded worker pool, per-tool timeouts |
| Browser attacks | Medium | Strict CSP, `nosniff`, `no-referrer`, `no-store`; same-origin, CORS off by default |

## Known gaps

- The readiness check runs the target project's own test suite in the `pre-pr` and `deep` profiles. Use a
  container or CI sandbox for untrusted repositories.
- In-flight API scan jobs live in process memory (results are in Db2); restarting the API loses their progress.
- There is no SSO yet; tokens are the only authentication method for the team API.
