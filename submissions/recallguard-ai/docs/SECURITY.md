# Security & Reliability

| Area | Control | Where |
|---|---|---|
| Secrets | Read from environment / `.env` only; `.env` git-ignored; `.env.example` has placeholders; secret fields use `repr=False` | `app/core/config.py` |
| SQL injection | Every statement uses `?` markers via `ibm_db_dbi`; no user input is interpolated. Dynamic `IN (?,?,…)` lists are built from counts only | `app/services/*`, test `test_parameterised_queries_are_injection_safe` |
| Input validation | Pydantic models with patterns and lengths (`source_ref` `^[A-Za-z0-9][A-Za-z0-9-]{2,29}$`); control characters stripped from free text; the referenced lot/batch must exist in Db2 | `app/schemas/api.py`, `services/incidents.py` |
| Uploads | Extension allow-list (pdf, txt, md, csv); `MAX_UPLOAD_MB` (default 10), enforced while reading; `%PDF` magic check; UTF-8 check for text; sanitised filename; SHA-256 de-duplication; no execution of content | `services/evidence.py` |
| Authorisation | Role → permission map; FastAPI dependency `require(perm)`; only `recall_manager`/`admin` can approve, reject, execute or verify evidence | `app/core/security.py` |
| Sensitive supplier data | `contact_email` / `contact_phone` returned as `[restricted]` unless the role has `supplier:sensitive` | `routes._redact_supplier` |
| Data integrity | PK/FK/UNIQUE/CHECK constraints in Db2; optimistic state transitions (`UPDATE … WHERE incident_status = ?`) | migrations, `services/incidents.py` |
| Audit | Append-only `AUDIT_LOGS` entry for every create, upload, transition, decision, action update and demo reset | `services/common.audit` |
| AI safety | Agents cannot issue notices or mark products safe. Human approval is mandatory. Unknown identifiers in AI text block verification. Fallback mode is labelled | `agents/` |
| Failure handling | Db2 connection retries (3×) then `DatabaseError` → HTTP 503. The app starts in degraded mode and `/health` reports the error. Failed LLM steps fall back and are logged | `database/db2.py`, `main.py` |
| Simulated vs real | `channel = 'SIMULATED'` on every recall action; `X-Data-Engine` header; DEV MODE banner; `is_demo` flag | throughout |
| CORS | Explicit origin list; only GET/POST and the three needed headers | `main.py` |

**Production hardening still required:**
- Replace header identity with OIDC/JWT (e.g. IBM Security Verify / App ID).
- Use TLS to Db2 (`DB2_SECURITY=SSL`).
- Move uploads to object storage with malware scanning.
- Add rate limiting.
