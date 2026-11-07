# System Health & Repository Audit

**Tested commit:** `70bd714` (main; the brief referenced `7619ae2`, but main has advanced through PRs #2 and #3)
**Test date:** 2026-11-06
**Environment:** macOS Apple Silicon, Python 3.11.9, Node 20.17.0, IBM Db2 12.1.5 on `localhost:50000`, Ollama `qwen2.5:7b-instruct`.

## Overall status

| Check | Status | Evidence |
| --- | --- | --- |
| Frontend starts | PASSED | `GET http://localhost:3000` → 200; Playwright loads with no console errors |
| Backend starts and `/health` responds | PASSED | `{"status":"ok","service":"aegis-api","version":"0.2.0",...}` |
| Db2 connection | PASSED | `/api/db/health` → connected, server `TESTDB` |
| Required tables | PASSED | `DOCUMENTS`, `PASSAGES`, `VERIFICATION_SESSIONS`, `CLAIMS`, `VERIFICATION_RESULTS`, `EVIDENCE_LINKS` |
| LangChain invokes configured model | PASSED | Live paper-demo and 40-case runs completed with `qwen2.5:7b-instruct` |
| PDF ingestion | PASSED | LoRA PDF: HTTP 201, 91 passages, 0.79 s; page provenance stored |
| Verification history persists | PASSED | Session #501 reopened from `GET /api/verifications` |
| JSON export | PASSED | `aegis-session-501.json`, report version 1.0, 4 claims |
| Markdown export | PASSED | `aegis-session-501.md`, contains report header and claims |
| Frontend API calls | PASSED | Playwright: history, documents, evaluation, downloads all 200 |
| No secrets in Git | PASSED | Tracked files scanned for DB/API/SSH patterns; only `.env.example` tracked |
| Python dependencies | PASSED | `pip check`: no broken requirements |
| Node dependencies | PASSED | `npm ls` resolves Next 14.2.35, React 18.3.1, TypeScript 5.9.3 |
| API contracts | PASSED (with schema checks) | Unit/API tests: 49 passed, 2 integration skipped |
| Database migrations | PASSED | `init_db.py` run twice successfully; idempotent migrations applied |
| Schema constraints | PASSED | 15 constraints, 18 indexes in `AEGIS` |
| GitHub Actions | PASSED | Latest main CI run `42123408181` completed success |

## Detailed evidence

### Runtime versions

- Python 3.11.9; FastAPI 0.162.0; Pydantic 2.14.3; `ibm_db` 3.3.0
- LangChain 1.4.9 / langchain-openai 1.7.4
- Node 20.17.0; Next.js 14.2.35; React 18.3.1
- IBM Db2 Community Edition 12.1.5, schema `AEGIS`
- Ollama `qwen2.5:7b-instruct` (local); provider/model are environment-configurable

### Test suites

```text
backend unit/API:      50 passed, 2 skipped (real-Db2 integration gated)
real Db2 integration: 2 passed with AEGIS_TEST_DB2=1
evaluation utilities: 8 passed
frontend typecheck:   pass
frontend lint:        pass
frontend build:       pass
```

The skipped tests are the two real-Db2 integration tests and are not counted as passes in the default run. They were executed separately and passed.

### Database

- Six required tables present.
- 15 primary/foreign/unique/check constraints and 18 indexes in `AEGIS`.
- `DOCUMENTS` has `PROCESSING_STATUS`, `EXTERNAL_ID`; `PASSAGES` has char offsets; sessions have completion time/duration; results have numeric analysis/human-review status; evidence links have relationships.
- `init_db.py --stats` succeeded twice in a row; the second run applied no destructive changes.

### PDF and provenance

- `lora.pdf` uploaded through `POST /api/documents`: 91 passages, HTTP 201, 0.79 s.
- The three demo papers are stored with page numbers; verification evidence returns page and passage IDs.
- Scanned/encrypted PDFs are rejected (unit tests).

### History and export

- Session #501 (4 claims, 1 supported / 2 contradicted / 1 insufficient) is persisted and returns from `/api/verifications`.
- JSON export: `application/json`, filename `aegis-session-501.json`.
- Markdown export: `text/markdown`, filename `aegis-session-501.md`.
- Exports contain persisted records only.

### Secrets

- `.env` and frontend `.env.local` are gitignored.
- Tracked secret scan found no DB password, API key, GitHub token, or SSH key patterns.
- Demo PDFs and SciFact data are gitignored.

## Findings

1. The brief's commit reference (`7619ae2`) is stale; `70bd714` is the tested main commit.
2. The `ibm_db` macOS/arm64 `exec_immediate` parameter-marker crash remains a platform quirk; the app uses prepared statements and explicit statement cleanup.
3. The local 7B model is slow; this is expected and handled with a 600 s request timeout.
4. One mobile overflow defect and one numerical entity-matching defect were found later in testing and fixed on the QA branch (see the master report).

## Limitations of this audit

- No dependency vulnerability scan (e.g., `pip-audit`/`npm audit`) was run.
- No load/soak test.
- No public deployment test.
- The frontend uses the local API; production network behavior was not tested.
