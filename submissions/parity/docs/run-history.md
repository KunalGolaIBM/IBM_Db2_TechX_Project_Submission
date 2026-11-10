# Run history

## What it does

Every pipeline run gets a durable record. The history is the base for audit and for regression mode later: rerun the same workload and compare against the last passing run.

## Records

`src/parity/history/types.py` holds plain data types:

- `ComparisonRecord` is one query outcome: query id, both SQL texts, status, risk score and label, note, and a short diff summary.
- `RunRecord` is one full run: run id, workload directory, start and finish times, exit code, and its records.

`build_diff_summary` joins the first differences into one short string. It truncates at 1000 characters so it always fits the table column.

## Stores

`src/parity/history/store.py` follows the same pattern as the knowledge base:

- `RunStore` is the interface: `start_run`, `save_records`, `finish_run`, `get_run`.
- `InMemoryRunStore` is for tests and local runs.
- `JsonRunStore` keeps the history in one JSON file. This works on any machine, including one without a working ibm_db driver. It also sets the start and finish times.
- `Db2RunStore` keeps history in Db2 as system of record. It uses two tables:

```sql
run (run_id, source_dir, started_at, finished_at, exit_code)
comparison_result (run_id, query_id, status, risk_score, risk_label, note, source_sql, db2_sql, diff_summary)
```

`save_run(store, source_dir, reports, exit_code)` is the one call a pipeline caller needs. It opens the run, saves all records, and closes the run with the exit code.

## History from the run command

```bash
parity run --dir samples --out parity-report.html --history parity-history.json
```

The run command saves the run into the history file and prints the run id. The HTML report title and the JSON summary also carry the run id. The history file accumulates every run of that workload, so run ids increment over time.

## Where the Db2 store runs

The Windows ibm_db driver fails with SQL1042C on this machine, so all Db2 admin DML runs inside the Linux bridge environment. This is the same rule the knowledge base store follows. Read the setup guide for the top docs note on it.

## Known limit

The Ids come from a Db2 identity column. `start_run` reads the generated id with `IDENTITY_VAL_LOCAL()`. This is safe for one writer at a time, which is what a parity run is.
