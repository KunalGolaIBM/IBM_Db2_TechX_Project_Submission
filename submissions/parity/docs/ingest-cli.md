# Ingest command

## What it does

`parity ingest` inspects a workload directory without touching any database. It loads and deduplicates the SQL files, then prints a summary. Use it to check a workload before a full run.

## Usage

```bash
parity ingest --dir samples
```

## Output

- Total queries after deduplication.
- Read only count and write count.
- Count of queries the translation rules cannot handle.
- The tables the workload touches.

A missing directory fails with a `directory not found` error.
