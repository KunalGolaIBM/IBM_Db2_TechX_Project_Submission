# Regression mode

## What it does

Regression mode catches silent breaking changes over time. The Db2 statements can stay untouched and still change results after a version update or a config change. A run today should never lose ground against a run that was proven before.

The baseline is the newest run in the history file whose exit code was 0. Every comparable query matched at that time, so it is a safe reference point.

## Usage

```bash
parity run --dir samples --history parity-history.json --regression
```

Regression mode needs `--history`. The comparison happens before the current run is saved, so the baseline is always an older run.

## The four categories

- new regressions: the query passed in the baseline and fails now. This is the alarm case.
- repeat failures: the query fails in both runs. Known issue, tracked.
- fixed queries: the query failed before and passes now. Progress.
- unknown queries: the query was not part of the baseline run.

The output prints each non empty category. If nothing differs, it prints "no differences from the baseline".

## Where it shows up

- The command line prints the regression section before the report is written.
- The JSON summary gets a `regression` object with the baseline run id, the category lists, and a `has_regressions` flag for tooling.
- Exit codes stay the same as a normal run: 0 all match, 1 any mismatch, 2 otherwise.

## Where the code lives

- `src/parity/history/regression.py` holds the comparison. It takes report entries and a baseline run record, so it works with any store.
- `list_runs()` was added to the store interface and all three stores. It returns runs oldest first.
- The Db2 store lists runs without their records, which is enough for finding the baseline.

## Known limit

The baseline is the last passing exit code. If the history only holds failing runs, regression mode prints "no passing run in history yet" and compares nothing.
