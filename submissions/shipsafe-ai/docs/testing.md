# Testing

**181 tests, 91% line and branch coverage, no mocks.** Every test that needs a database uses the real
IBM Db2 from `.env`, and every test that needs a model uses the real Granite models in Ollama.

## How it works

- `tests/conftest.py` drops and recreates a separate schema, `SHIPSAFE_TEST`, at the start of each run
  (`SYSPROC.ADMIN_DROP_SCHEMA`), so tests never touch your real `SHIPSAFE` data.
- If Db2 or a Granite model is missing, the affected tests **fail** with a message saying what to start.
  They are never skipped silently.
- Coverage is enforced at 90% (`fail_under = 90` in `pyproject.toml`).

## Run

```bash
cd submissions/shipsafe-ai
pip install -e ".[dev,scanners]"
pytest --cov=shipsafe                      # whole suite, about 5 minutes on a laptop GPU
pytest tests/test_guard.py tests/test_ast_rules.py   # fast checks, no model needed
cd extension && npm ci && npm test         # VS Code / Bob extension
```

## What is covered

| Area | File | Highlights |
|---|---|---|
| Code rules | `test_ast_rules.py` | 48 cases: real vulnerabilities found; mentions in comments, docstrings, strings and URLs ignored; taint through variables |
| Guard | `test_guard.py` | Verdicts, Bandit merge, JS/TS, syntax errors, size limits |
| Db2 SQL checker | `test_sql_checker.py` | Live PREPARE: SQL0206N / SQL0204N / SQL0104N with suggestions; static rules; SQLAlchemy catalog |
| Repository | `test_db2_repository.py` | Atomic save rolled back on error, cascades, diffs, tokens, audit, all three stored procedures, CHECK constraints |
| AI features | `test_ai_live.py` | Haystack memory scoped by project; LangChain answers with verified citations; **a Granite fix executed against a real Db2 table** proves the injection is gone and the query still works |
| MCP server | `test_mcp_server.py` | **Stdio end to end with the official MCP client, as Bob runs it**, plus every tool in-process |
| CLI | `test_cli.py` | Every command, including `setup`, `connect`, `check --staged` in a real git repo, `hook`, `fix`, `forget` |
| API | `test_api.py`, `test_platform.py` | Auth and roles, allow-listing, rate limits, scan jobs, exports, reindex |
| Platform | `test_platform.py` | Pool replaces a killed Db2 connection; unreachable Db2 fails fast; live pip-audit against PyPI/OSV; git discovery; log redaction |
| IDE configs | `test_integrations_config.py` | Bob / Claude / Cursor / VS Code config files merged without losing other servers |
| Extension | `extension/src/test` | Diagnostics, status text, config merge, Bob rules identical to the Python copy |

## Bugs the real-infrastructure tests found

Mocked tests would have passed all of these:

1. Every Db2 connect waited about 10 s (`localhost` → IPv6, Db2 forwarded on IPv4).
2. The MCP server froze on Windows while loading native libraries under the stdio transport.
3. Bandit and git subprocesses hung by inheriting the MCP stdin pipe.
4. Granite wrote `ibm_db` code that passed every security check but would fail at runtime.
5. Granite cited policy ids that do not exist.
6. Stored-procedure OUT parameters returned as NULL break the driver (CLI0110E); procedures must be
   called schema-qualified because routine resolution uses `CURRENT PATH`.
