# Comparison runner and CLI

## Runner

`src/parity/runner.py` ties the parts together.

- `run_comparison(source, target, source_sql, target_sql)` runs both queries and compares the results.
- If the source SQL uses a nondeterministic call, it returns NOT_COMPARABLE before any query runs.
- If an executor fails, it returns ERROR with the error text. Nothing is hidden.
- MATCH only comes from the comparator. The runner never invents a verdict.

## CLI

`src/parity/cli.py` is the `parity` command.

```bash
parity compare --source-sql "SELECT 1" --target-sql "SELECT 1"
```

It reads database settings from the environment, runs the source SQL on PostgreSQL, the target SQL on Db2, prints the status and diffs, and exits with a code.

Exit codes:

- 0 for MATCH.
- 1 for MISMATCH.
- 2 for ERROR or NOT_COMPARABLE.

CI can use these codes directly. A lost parity fails the build.

## Live test result

The runner was tested against a live PostgreSQL container in Docker, Postgres against Postgres, on 2026-11-09.

- `SELECT 1` vs `SELECT 1` gave MATCH.
- `SELECT 1` vs `SELECT 2` gave MISMATCH with the exact diff row and both values.
- `SELECT now()` gave NOT_COMPARABLE and no query ran.

Db2 live testing will start with the schema sync branch. The Db2 executor is covered by mock tests until then.
