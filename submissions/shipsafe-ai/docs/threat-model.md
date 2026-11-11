# ShipSafe AI: Threat Model

| Threat | Risk | Mitigation in the code |
|---|---|---|
| Malicious content in the scanned repository | High | Files are read as text. ShipSafe never imports or edits scanned code. The only code it runs is the project's own test suite, and only in the `pre-pr`/`deep` profiles. |
| Path traversal out of the workspace | High | `SafeExecutionBoundary.validate_path_containment` resolves paths and rejects anything outside the workspace root. |
| Command injection through scanner invocation | High | Every subprocess uses a fixed argument list with `shell=False`, a timeout and an output cap. |
| Secret leakage via storage or reports | High | Evidence snippets go through `redact_secrets` (AWS keys, private keys, GitHub tokens, `password=`/`token=` patterns) before they reach Db2, reports or MCP clients. |
| Db2 credential exposure | High | Credentials come only from environment variables or a git-ignored `.env`. `DB2_SECURITY=SSL` is supported. The connection string is never logged. |
| SQL injection in ShipSafe itself | High | All values are bound with `?` markers. The schema name is validated as an identifier. Row limits are cast to `int`. |
| Prompt injection through policy documents | Low | Retrieved policy text is shown as a quote. No LLM acts on it, and retrieval cannot change findings or the gate. |
| False confidence from skipped checks | Medium | Skipped or unsupported checks are recorded as `skipped` and prevent a clean `PASS`. |

## Known gaps
- Output from external scanners (for example Gitleaks JSON) is parsed defensively, but not yet validated against a schema.
- The test-runner check executes the target project's tests. Run ShipSafe in a container or CI sandbox when assessing untrusted repositories.
