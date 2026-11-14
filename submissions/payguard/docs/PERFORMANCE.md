# Measured performance

Measurements were taken locally on 13-14 November 2026. These are actual executions,
not capacity estimates.

| Version | Requests completed | Failures | Requests/sec | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| Baseline, shared Db2 connection and lock | 2524 | 0 | 43.69 | 1100 ms | 1500 ms |
| First pooled version | 3943 | 0 | 68.09 | 580 ms | 1500 ms |
| Final pool + bounded knowledge caches | 5582 | 0 | 94.60 | 440 ms | 1000 ms |

The first pooled run improved throughput but not p95. Reusing a DB2VS instance only on
its own exclusive pooled connection, caching static example retrieval, and removing
duplicate access logs produced the final result. The measured final p95 is lower; this
is one local run per version rather than a statistical guarantee.

## Environment and workload

- Windows host, Intel Core i5-1135G7 at 2.40 GHz; 4 physical / 8 logical processors;
  8,216,137,728 bytes physical RAM reported by Windows.
- Python 3.12.10, Locust 2.47.0, local-hash-v1 with 768 dimensions.
- Real Docker Db2 Community Edition 12.1.5.0, image digest
  `sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6`.
- One Uvicorn process, pool minimum 2 / maximum 10 in the final version.
- Ten fixed Nigerian scam/safe messages, cycled per client, with `region=NG` and
  `explain=false`. No Gemini or PayPal requests are included.
- 50 concurrent users, spawn rate 10 users/sec, requested duration 60 seconds, no think
  time. Locust calculates throughput over its observed statistics interval, which can
  differ slightly from the requested duration.
- Final database snapshot: 25 playbooks, 14 entities, 14 community reports and 90
  examples. The training CSV changed from 105 to 90 rows after removal of the 15
  held-out overlaps. The baseline persisted row counts were not separately captured;
  this is a before/after application measurement, not an isolated pool-only benchmark.
- Screening history accumulates between runs. No reset was used on the existing local
  database. Warm caches, a repeated small corpus, local hardware activity and growing
  history affect results; this does not establish production or multi-host capacity.
- Per-IP quota is raised to 100000 only in the benchmark helper process. The deployed
  default remains 60/minute. No failures, rate-limit responses or degraded responses
  were accepted as successful screenings by the load script.
- Native ANN index creation was rejected by this Db2 installation (SQL0614/54008).
  These measurements use exact cosine search and the region pre-filter, not ANN.

## Reproduction

Install dependencies with `python -m pip install -r requirements-dev.txt`, start Docker
Db2, configure the private connection settings and run `python src/seed.py`.

Terminal 1:

```bash
python scripts/serve_benchmark.py
```

Terminal 2:

```bash
python -m locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s \
  --host http://127.0.0.1:8000 --csv .artifacts/after-final --only-summary
```

The helper disables AI and sandbox payments in its own environment. The load task fails
responses with missing verdicts or `degraded=true`. Locust's quitting hook saves final
statistics to `.artifacts/after-final_summary.json`.

For the baseline, use commit `ac66ebb` in a separate checkout with the original CSV,
the same private database settings and the checked-in load script. Run the original
server as `python -m uvicorn main:app --app-dir src --host 127.0.0.1 --port 8000 --no-access-log`,
then the identical Locust command with `--csv .artifacts/before`.
Do not run two benchmark servers on the same port or run integration tests concurrently
with the measured workload.

[Final raw summary](results/load-after.json), [baseline console summary](results/load-before.json),
[intermediate summary](results/load-intermediate.json), and periodic CSV snapshots are
checked in. The original baseline script did not yet have the final-summary hook:
its final console output reported 2524 requests and 43.69 requests/sec. The last periodic
CSV snapshot lags it (2510 requests), so the console figures are the baseline used here.
Locust percentiles use histogram rounding; p95 is approximate.

## Query plans and limits

```bash
python scripts/explain.py --output .artifacts/explain.json
```

The recorder captures production repository SQL and refreshes RUNSTATS before EXPLAIN.
[Recorded plans](results/explain.json) show entity lookup using `PG_UQ_ENTITY` and
`PG_IX_REPORT_ENTITY`, velocity using `PG_IX_SCREEN_PAYEE`, and playbook filtering using
`PG_IX_PATTERN_REGION` before an exact cosine-distance sort. Optimizer costs in that JSON
are estimates, not measured execution times.

Migration 003 attempts vector indexes only on Db2 12.1.5+. This installation rejected
both cosine and Euclidean probes, including a 32 KB tablespace attempt after enabling
`DB2_VECTOR_INDEXING=YES` and restarting the local instance. The migration is deferred,
not falsely recorded as applied. A capable installation can apply it on the next seed.
No production-scale dataset, ANN recall, hosted network or Gemini-under-load benchmark
was completed; those are explicit limits of these results.
