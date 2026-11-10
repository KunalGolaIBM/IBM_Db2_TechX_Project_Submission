# Ops runbook

## Start

```bash
docker compose up -d postgres db2
```

Wait until both containers show healthy. Then seed the sample data.

## Run

```bash
python -m parity.cli run --dir samples --out parity-report.html --json-out parity-summary.json --history parity-history.json --bridge
```

Exit codes: 0 means every query matched. 1 means at least one mismatch. 2 means errors or not comparable queries with no mismatch.

## When a database dies mid run

The runner returns `ERROR` with the executor message. It never hangs and never hides the error. Fix the database and rerun. The history file keeps earlier runs, so a regression compare still works.

## When the gateway is starved

In live mode every provider failing raises `all providers failed`. In replay mode a missing cache entry marks the query `NOT_COMPARABLE` with a `replay cache miss` note.

## Timeouts and row limits

Every execution carries a timeout. It must be positive. The default is 30 seconds. If you change it, change the CLI `--timeout` flag, not the code.

## Teardown

```bash
docker compose down
```

The Db2 data volume stays, so the next start is fast.
