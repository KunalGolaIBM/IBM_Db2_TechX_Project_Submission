# Security & Adversarial Testing

## Method

Live requests against the local API plus direct service checks. Raw results:
`reports/security_results.json`. Harmless payloads only; no destructive SQL or shell
commands.

## Results

| Test | Status | Evidence |
| --- | --- | --- |
| Malformed PDF | PASSED | `%PDF` header with invalid body → HTTP 422 |
| Unsupported extension | PASSED | `.exe` → HTTP 400 |
| Empty upload | PASSED | HTTP 400 |
| Oversized upload (>10 MB) | PASSED | HTTP 400; streamed limit enforced |
| Invalid UTF-8 text | PARTIALLY PASSED | Accepted via latin-1 fallback, no crash; this is permissive and documented |
| SQL injection in title/passage | PASSED | Stored as literal text; `DOCUMENTS` table remained queryable |
| XSS payload in title | PASSED with caveat | Stored/returned as JSON; React renders it as text, not executable markup |
| Path traversal filename | PASSED | `../../evil.txt` sanitized to `evil.txt` |
| CORS preflight | PASSED | Allowed origin `http://localhost:3000`, explicit methods/headers |
| Missing `LLM_API_KEY` | PASSED | `ConfigurationError`; no fabricated model output |
| Unreachable LLM endpoint | PASSED | `LLMUnavailableError` / 503-class behavior; key not echoed |
| Invalid evidence IDs | PASSED (unit) | Fabricated IDs discarded; definitive label downgraded |
| Prompt injection in evidence | PASSED | Ignored the injected instruction and contradicted the underlying false claim |
| Request timeout | PARTIAL | 120 s LLM and 600 s request timeouts configured; a forced slow-endpoint timeout was not executed |
| Sensitive strings in logs | CODE REVIEW ONLY | Request/document content is not logged by AEGIS; uvicorn access logs contain paths only |
| No raw DB/credential errors | PASSED | API error envelopes sanitized; DSNs never returned |

## Findings

1. **P2 — invalid UTF-8 is accepted via latin-1 fallback.** This avoids crashes but can
   silently alter text. It is documented; a future validation policy could reject
   non-UTF-8 text uploads.
2. **XSS is stored as data.** React escapes it, but any future non-React renderer must
   preserve escaping. The API itself does not sanitize stored content.
3. **No authentication or rate limiting.** The application is local/single-user; this
   is a known limitation and not a regression.
4. **Prompt injection cannot be guaranteed eliminated by prompting.** AEGIS validates
   cited passage IDs and now rejects definitive labels when cited passages lack
   claim-specific terms, but a semantic entailment verifier is still model-dependent.

## Not tested

- Forced slow-network timeout behavior.
- Malware scanning of uploads.
- Secret-manager integration.
- TLS, authentication, multi-tenant isolation.
- Denial-of-service/load testing.

## Recommendation

Before any public deployment, add authentication, rate limiting, TLS, upload malware
scanning, and a stricter UTF-8 policy. Keep Db2 off the public network.
