# Reproducibility Validation

## Method

A clean copy of the repository was created at `${TMPDIR}/aegis-repro-clean`, excluding
`.git`, `.context`, the existing virtualenv, `node_modules`, `.next`, downloaded PDFs,
and SciFact data. The only copied configuration was the local `.env` needed to reach
the existing Db2 instance.

## Steps executed

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cd frontend && npm ci && npm run build
.venv/bin/python database/init_db.py --stats
cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## Results

| Step | Result |
| --- | --- |
| Fresh Python virtualenv | PASSED |
| Backend dependency install | PASSED (`pip check` clean) |
| Fresh `npm ci` | PASSED (444 packages, 5 s cache-warm) |
| Production frontend build | PASSED |
| Db2 schema init/migrations | PASSED (all six tables present) |
| Backend startup | PASSED (port 8001) |
| `/health` and `/api/db/health` | PASSED (200) |
| Text document upload | PASSED (HTTP 201) |
| Export existing session | PASSED (200) |
| Real verification from clean copy | PASSED: 1 claim, SUPPORTED, 23.2 s |
| DB persistence from clean copy | PASSED (session created) |

The clean-copy verification returned a real model result, not a mock:
`SolarCell-X achieved 92% efficiency...` was `SUPPORTED` with the supplied evidence.

## Gaps and missing documentation found

- A clean clone must create `.env` with a real `DB2_PASSWORD`; the README states this.
- `frontend/.env.local` is optional because the default API URL is localhost:8000.
- `make demo-papers` requires network access to arXiv; the synthetic demo remains offline.
- The clean copy used the existing shared Db2 schema, not a separate database. A new
  developer would run `make db-init` against their own `TESTDB`.
- A full fresh macOS machine install (new Homebrew/pyenv) was not performed; the host
  already had Python/Node/Db2/Ollama.
- Frontend dev server was not restarted at a different port in the clean copy; the
  production build was validated instead.

## Verdict

The documented setup is reproducible from a clean working copy on this machine. The
remaining environmental requirement is an existing IBM Db2 instance with credentials.
