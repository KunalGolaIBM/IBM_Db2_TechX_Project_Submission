# Security

This page lists the security checks we ran on ShipSafe itself, what they found, what we changed,
and the controls built into the product. The threat model is in [threat-model.md](threat-model.md).

## Checks run on ShipSafe's own code

| Check | Scope | Result |
|---|---|---|
| Bandit (`bandit -r src -ll`) | All Python source | **0 medium or high findings** (low-severity notes only, reviewed) |
| ShipSafe on itself (`shipsafe check src/shipsafe/**/*.py`) | All Python source | **WARN, no blocking issue** |
| npm audit (production dependencies) | VS Code extension, web dashboard, landing site | **0 vulnerabilities** in each |
| pip-audit | Installed Python environment | 1 transitive package with advisories (see accepted risks) |
| Secrets | Repository | No credentials committed; `.env` is git-ignored and the example file holds placeholders only |

### What the checks found, and the fixes

Running ShipSafe on its own source first returned **BLOCK**. We fixed each finding instead of
suppressing it:

| Finding | Where | Fix |
|---|---|---|
| B608: SQL text built with string formatting (row limits, an ORDER BY expression, a table name) | `db2/repository.py`, `knowledge/policy_store.py` | Row limits are now bound as `?` parameter markers in `OFFSET ? ROWS FETCH FIRST ? ROWS ONLY`; the ORDER BY expression and table name are plain constant strings. The values were never user input, but now no SQL text is assembled at runtime. |
| B310: `urllib.urlopen` accepts `file://` and custom schemes | `llm/granite.py` | Replaced with `httpx` and an explicit `http`/`https` check |
| B103: git hook written with mode `0o755` | `cli_ide.py` | Mode `0o700`, executable by the owner only |

### Accepted risk

| Package | Advisory | Why it is accepted | Mitigation |
|---|---|---|---|
| `chromadb` 1.5.9 (pulled in by CrewAI) | PYSEC-2026-311, -3813, -3814, -3815 | No fixed version is published. ShipSafe does not use Chroma: the crew runs with `memory=False`, no knowledge sources, and no Chroma server is started. | Re-check with `pip-audit` on each release; upgrade when a fix ships. |

## Bugs found by testing on real infrastructure

These were found because every test runs against the real Db2 and real Granite, with no mocks:

1. **Db2 connections waited about 10 s each.** `localhost` resolved to IPv6 first, while the Docker/WSL
   port forward for Db2 listens on IPv4. ShipSafe now uses `127.0.0.1` for local hosts and adds
   `CONNECTTIMEOUT=10`, so an unreachable database fails fast instead of hanging.
2. **The MCP server could freeze on Windows.** Loading native libraries (numpy/OpenBLAS) while the
   stdio transport waits on stdin can deadlock. Native modules are now loaded before the transport starts.
3. **Subprocesses could hang the IDE.** Bandit and git inherited the MCP stdin pipe. Every subprocess
   now gets an empty stdin, a fixed argument list, `shell=False` and a timeout.
4. **Anonymous telemetry.** CrewAI, LiteLLM and Haystack (PostHog) send usage data by default. ShipSafe
   switches all three off at import time.

## Controls in the product

**Code and data stay local**
- The guard checks code text in memory. It never reads or writes the user's files to do so; Bandit runs
  on a temporary copy that is deleted afterwards.
- Granite runs in the local Ollama. No hosted model API is called.

**Database**
- Every value is bound with `?` parameter markers. The only identifier ever used in SQL text is the
  schema name, validated as letters, digits and underscores.
- The SQL assistant only PREPAREs statements (deferred prepare off) and always rolls back. It never executes them.
- Assessments are saved in one transaction. `AUDIT_LOG`, `GUARD_EVENTS` and `FIX_ATTEMPTS` are
  append-only for the application role ([db2-least-privilege.sql](db2-least-privilege.sql)); retention
  runs inside `SP_PURGE_HISTORY` with the definer's rights.
- Credentials come only from the environment or a private settings file (`~/.shipsafe/.env`); log lines
  redact `PWD=`, bearer tokens and `ss_` tokens.

**IDE tools**
- Workspace tools resolve every path inside the workspace root and refuse anything outside it.
- Inline checks are limited to 400 KB per file; workspace checks to 50 files per call.
- A fix is applied only after the developer sees the diff, and only when it is verified (or after an
  explicit "Apply anyway" for unverified fixes).

**REST API and dashboard**
- Bearer tokens (256-bit) stored as SHA-256 hashes, roles viewer / operator / admin enforced on every route.
- Scan targets allow-listed, per-token rate limits, strict CSP and security headers, CORS off by default.

## Reporting a vulnerability

Open a private security advisory on the repository, or contact the maintainer listed in
`submission.json`. Please do not open a public issue for an unpatched vulnerability.
