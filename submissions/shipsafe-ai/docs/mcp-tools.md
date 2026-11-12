# MCP tool reference

ShipSafe exposes 11 tools over MCP (stdio). Every tool returns JSON text. The calling IDE's name from the
MCP handshake (`bob`, `claude-code`, `shipsafe-vscode`, ...) is stored with each guard event and memory.

| Tool | Arguments | Returns | Db2 |
|---|---|---|---|
| `shipsafe_check_code` | `code`, `filename` | `verdict` (clean/warn/block), `issues[]`, `summary`, `checks`, `duration_ms`, `notes` | `GUARD_EVENTS` insert; policy per issue from `POLICY_VECTORS` |
| `shipsafe_check_files` | `paths[]` (relative, max 50) | overall `verdict`, `files[]` (one check result each) | same as above |
| `shipsafe_fix_code` | `code`, `filename` | `verified`, `fixed_code`, `diff`, `rounds`, `issues_before/after`, `plan`, `policies`, `fix_id` | `FIX_ATTEMPTS` insert |
| `shipsafe_check_sql` | `sql` | `verdict`, `valid`, `issues[]` (code, severity, message, suggestion), `result_columns`, `parameter_markers`, `db2` | `PREPARE` only, then rollback |
| `shipsafe_db2_schema` | `schema?`, `tables?[]` | `tables[]` (columns, primary key, foreign keys, indexes), `views[]` | catalog via SQLAlchemy `ibm_db_sa` |
| `shipsafe_ask_standards` | `question`, `category?` | `answer`, `cited`, `unverified_citations`, `citations[]`, `latency_ms` | `VECTOR_DISTANCE` on `POLICY_VECTORS` |
| `shipsafe_remember` | `text`, `kind` (decision/convention/gotcha/todo), `tags?[]`, `project?` | `id`, `stored`, `table` | `MEMORY_VECTORS` upsert (Haystack) |
| `shipsafe_recall` | `query`, `project?`, `top_k` (1–25), `kind?` | memories with `text`, `kind`, `tags`, `author`, `score` | vector search with metadata filters |
| `shipsafe_readiness_check` | `workspace` (default `.`), `profile` (quick/pre-pr/deep) | `status` (PASS/PASS_WITH_WARNINGS/BLOCKED), `counts`, `top_findings`, `risk` | atomic assessment save; `CALL SP_PROJECT_RISK` |
| `shipsafe_session_report` | `since_minutes` | `by_client[]` (checks, blocked, warned, issues caught, verified fixes), `recent_fixes` | `CALL SP_GUARD_SUMMARY` (result set) |
| `shipsafe_status` | none | Db2 connection details, Ollama models | `SYSIBMADM.ENV_INST_INFO` |

## Example: check before writing

Request:

```json
{"name": "shipsafe_check_code",
 "arguments": {"filename": "deploy.py", "code": "import subprocess\nsubprocess.run(cmd, shell=True)\n"}}
```

Response (shortened):

```json
{
  "verdict": "block",
  "language": "python",
  "issues": [{
    "rule_id": "CMD-SHELL", "severity": "high", "line": 2,
    "title": "Process started through the shell",
    "fix": "Pass an argument list with `shell=False`: `subprocess.run([\"git\", \"status\"], check=True)`.",
    "sources": ["bandit", "shipsafe_code_rules"],
    "policy": {"doc_id": "POL-SEC-004", "title": "Safe Process Execution and Dynamic Code Policy"}
  }],
  "summary": "2 issue(s) in deploy.py, worst: high. Do not write this code as-is; fix the blocking issues first."
}
```

## Rule catalogue (guard)

| Rule | Severity | Catches |
|---|---|---|
| `SQLI-DYNAMIC` | critical | SQL built from runtime values (f-string, `+`, `%`, `.format`) reaching `execute`, `exec_immediate`, `prepare`, `read_sql`; followed through variables |
| `SQLI-IDENTIFIER` | low | SQL text that interpolates only constants or `int()` casts |
| `DB2-API-MISUSE` | high | `ibm_db.exec_immediate` with `?` or a tuple; fetching rows from the result of `ibm_db.execute()` |
| `CMD-SHELL` | high | `subprocess.*(shell=True)`, `os.system` / `os.popen` with a non-literal |
| `CODE-EVAL` | critical | `eval` / `exec` on a non-literal |
| `DESER-UNSAFE` | high | `pickle`/`marshal`/`dill` loads, `yaml.load` without a safe loader |
| `TLS-VERIFY-OFF` | high | `verify=False` |
| `DEBUG-ENABLED` | medium | `app.run(debug=True)` |
| `TEMPFILE-MKTEMP` | medium | `tempfile.mktemp()` |
| `JS-EVAL`, `JS-INNERHTML`, `JS-CHILD-EXEC` | critical / high | `eval`, `new Function`, `innerHTML =`, `child_process.exec` with dynamic input (JS/TS) |
| `SEC-001` … `SEC-005` | critical / high | AWS keys, Db2 passwords, GitHub tokens, private keys, API secrets |
| `PY-SYNTAX` | high | Python that does not parse |
| Bandit `Bxxx` | as rated | Every Bandit check, merged with the rules above by line and family |

## SQL checker issue codes

| Code | Severity | Meaning |
|---|---|---|
| `SQL0104N` / `SQL0204N` / `SQL0206N` / … | high | Db2 rejected the statement at PREPARE: syntax, unknown object, unknown column (with suggestions) |
| `NO-WHERE` | high | UPDATE or DELETE without WHERE |
| `TEMPLATE-PLACEHOLDER` | high | `%s`, `%(name)s` or `{name}` placeholders: string formatting, not binding |
| `MULTI-STATEMENT` | medium | More than one statement in a string |
| `DESTRUCTIVE-DDL` | medium | DROP / ALTER / TRUNCATE |
| `SELECT-STAR`, `UNBOUNDED-READ`, `INLINE-LITERAL` | low | Maintainability and performance hints |
