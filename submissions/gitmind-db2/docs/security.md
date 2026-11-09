# GitMind 2.0 — Security Specification & Threat Model

## 1. Credentials & Secret Management
- **Zero Secrets in Repository:** Credentials (`DB2_PASSWORD`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `GITHUB_TOKEN`) are loaded solely via environment variables or uncommitted `.env` files.
- **Log Sanitization:** `Db2ConnectionManager` uses `sanitize_conn_str()` to mask all passwords with `********` across logs, diagnostics, and CLI outputs.
- **In-Flight Secret Redaction:** Source code files and commit diffs pass through `utils.security.redact_secrets()` before generating vector embeddings or sending context to external LLMs.

## 2. Least-Privilege Database Roles
GitMind 2.0 supports segregated database credentials:
- **Migration Role (`DB2_ADMIN`):** Grants `CREATE TABLE`, `ALTER TABLE`, and DDL privileges required to run `gitmind db2 migrate`.
- **Runtime Application Role (`GITMIND_APP`):** Grants `SELECT`, `INSERT`, `UPDATE`, and `DELETE` exclusively on application tables (`GITMIND_*`).
- **Audit Role (`GITMIND_AUDIT`):** Grants `SELECT` and `INSERT` privileges on `GITMIND_AUDIT_EVENTS`, with `UPDATE` and `DELETE` explicitly denied to enforce an immutable audit trail.

## 3. SQL Injection Defense
- 100% of relational queries across `data/db2/connection.py`, `data/db2/migrations.py`, and `data/repository_memory.py` utilize parameterized queries (`?` placeholders).
- Zero user strings are concatenated into dynamic SQL statements.
- Identifiers and schema names are validated against strict alphanumeric allowlists.

## 4. Prompt Injection & Untrusted Data Boundaries
- Git commit messages, pull request titles, issue descriptions, and code comments are treated as untrusted user data.
- Input is sanitized via `sanitize_agent_input()`, disarming system tags and code-fence escapes.
- Agents operate with explicit tool allowlists and strictly structured Pydantic outputs (`AgentFinding`, `EvidenceReference`).

## 5. Non-Destructive Git Guardrails
- `run_safe_git_command` enforces a read-only allowlist (`log`, `show`, `diff`, `status`, `blame`, `reflog`).
- Potentially destructive operations (`git reset --hard`, `git push --force`, `git branch -D`, `git stash drop`, `git clean`) are intercepted and blocked by default, requiring explicit developer confirmation.
