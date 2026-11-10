# Replay command

## What it does

`parity replay` reruns a workload using only recorded gateway responses. It never touches the network. This is the demo path: a reviewer can reproduce a run with no API key.

## Usage

```bash
parity replay --dir samples --cache parity-llm-cache.json --out parity-report.html --json-out parity-summary.json --bridge
```

- `--dir` is a folder with `.sql` files.
- `--cache` is the recorded gateway cache file. It is required.
- `--out`, `--json-out`, and `--history` behave the same as `parity run`.
- `--bridge` uses the Linux bridge for Db2. Use it on Windows.

## Behavior

- Queries the rules can translate still go through the rules first.
- Queries the rules cannot translate go to the replay gateway. A cache hit returns the recorded Db2 SQL. A cache miss marks the query `NOT_COMPARABLE` with a `replay cache miss` note. The run continues, so all misses show in one report.
- The LLM usage section of the JSON summary counts calls and cache hits. In replay every hit is from cache.

## Difference from `parity run --replay`

`parity run --replay` records nothing and uses the cache you pass with `--llm-cache`. `parity replay` is a named subcommand whose only job is the offline rerun. Both share the same exit codes: 0 all match, 1 any mismatch, 2 errors or not comparable.
