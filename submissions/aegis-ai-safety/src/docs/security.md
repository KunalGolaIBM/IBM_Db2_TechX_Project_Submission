# Security

AEGIS is a single-user research application. It is not a hardened multi-tenant
service, and it must not be exposed publicly without authentication and transport
security in front of it.

## Threat model

Primary untrusted inputs:

- AI-generated research text pasted by the user.
- Uploaded PDF/TXT/MD evidence, including text that contains adversarial instructions.
- Model output, which may contain fabricated passage IDs or malformed JSON.
- The network path to the LLM provider and Db2.

## Implemented controls

### Secrets

- All credentials come from environment variables or a gitignored `.env`.
- `.env`, `frontend/.env.local`, and downloaded demo PDFs are excluded from Git.
- Errors returned to clients never include DSNs, passwords, or raw stack traces.
- Server logs record SQLSTATE/SQLCODE and error classes, not credentials or full
  document content.

### Upload and document processing

- Allowed content types: PDF, plain text, Markdown; allowed extensions `.pdf`, `.txt`,
  `.md`.
- Size cap: 10 MB (`AEGIS_MAX_UPLOAD_BYTES`), enforced while reading the stream.
- PDF files must contain a `%PDF` header.
- Encrypted PDFs are rejected.
- Image-only/scanned PDFs are rejected with a clear error rather than falsely marked as
  parsed. OCR is not implemented.
- Documents are stored as passages with provenance; uploaded files are not executed.
- Processing is pure Python/PyMuPDF; no shell commands are derived from uploads.

### SQL and database

- All user values are bound through prepared statements
  (`ibm_db.prepare` + `bind_param` + `execute`).
- Schema identifiers come from validated configuration, not request data.
- Foreign keys and cascading rules prevent orphaned evidence links.
- Explicit transactions wrap multi-row writes; failures roll back.
- Statements and connections are freed/closed explicitly.
- Db2 should never be exposed directly to the public internet.

### Request handling

- Pydantic validation for lengths, IDs, formats, and query parameters.
- Request timeout (`AEGIS_REQUEST_TIMEOUT_SECONDS`, default 600s).
- LLM timeout and bounded retries.
- Explicit CORS allow-list (`AEGIS_CORS_ORIGINS`); no wildcard by default.
- Typed error envelopes replace internal exception details.
- React escapes displayed user/document content by default.
- Report exports are generated from persisted records, not raw client input.

### Prompt injection

- Research text and passages are treated as data, delimited in prompts, and explicitly
  described as untrusted.
- The model is never asked to execute instructions from documents.
- Returned passage IDs are validated against the actual retrieved candidate set.
- Definitive labels without a valid citation are downgraded.
- Prompt injection cannot be completely eliminated by prompting; the human-review
  requirement and evidence inspector are the backstop.

### LLM data disclosure

- Claim extraction sends the submitted research response to the configured provider.
- Verification sends one claim plus only the retrieved candidate passages (top K), not
  complete documents.
- If a hosted provider is used, that provider receives those excerpts. Users should
  not submit confidential documents without reviewing the provider's data policy.
- The provider is configurable; local Ollama can be used to keep inference local.

## Known gaps

- No user accounts, authorization, per-user isolation, or row-level security.
- No rate limiting or abuse protection.
- No malware scanning of uploads.
- No PII detection/redaction.
- No application-level encryption at rest; rely on Db2/storage encryption.
- No CSRF concern in the current tokenless API, but also no authentication.
- No security audit or penetration test has been performed.
- Exports and history have no access control; protect the deployment at the network or
  proxy layer.
- CORS is not a substitute for authentication.
- The local development stack listens on localhost; do not bind Db2 or the API to a
  public interface without a deliberate deployment review.

## Reporting

If you find a security issue, open a private advisory or contact the repository owner
rather than filing a public exploit report.
