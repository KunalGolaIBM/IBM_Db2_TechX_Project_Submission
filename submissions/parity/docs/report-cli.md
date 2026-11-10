# Run command and report

## Usage

```bash
parity run --dir samples --out parity-report.html --json-out summary.json --bridge
```

- `--dir` is a folder with `.sql` files.
- `--out` is the HTML report path.
- `--json-out` is an optional machine readable summary.
- `--history` is an optional run history file. It stores every run with a run id, and the run id appears in the report title and the JSON summary.
- `--bridge` uses the Linux bridge for Db2. Use it on Windows.
- `--concurrency` runs queries in parallel, bounded by the number given. The default is 1, which keeps runs sequential and simple to debug. Report order always matches the workload order.

Schema and data sync must happen before the run. The pipeline assumes both databases hold the same data.

## Pipeline

1. Ingest and deduplicate queries from the folder.
2. Write queries are marked NOT_COMPARABLE and never executed.
3. Each read query is translated with the rule translator.
4. The runner executes both versions and compares.
5. Risk score and report entries are collected.
6. HTML and JSON files are written.

## Exit codes

- 0: every query MATCH.
- 1: at least one MISMATCH.
- 2: errors or not comparable queries, with no mismatch.

CI fails the build on 1 and 2.

## Report

The HTML report is one self contained file with no external assets. It shows a pass and fail table, source and Db2 SQL, risk score per query, and the first differences with both values.

Risk score is a simple formula in `src/parity/report/risk.py`. Mismatch adds 20. Each diff adds weight by kind. The score caps at 100. Labels are LOW, MEDIUM, and HIGH.

## Known limit

Table quoting in the pipeline covers the first table of each query. Complex multi table queries need a real SQL parser in a later branch.
