# Db2 workload management for model-generated SQL

"Ask the ledger" is the one place AsOf runs SQL a language model wrote. Before it runs, `askledger.validate` makes sure
it is a single `SELECT` over six audit views with allow-listed functions (SQLGlot, IBM's Db2 dialect), and it runs as a
read-only analyst user. That decides what a query may read. It cannot tell how expensive a valid query is: a six-way
cross join of the audit views is a perfectly valid `SELECT`. So Db2 itself limits what the analysts' queries may cost,
with a workload and three thresholds ([`07_wlm.sql`](../src/asof/sql/07_wlm.sql)).

## What Db2 enforces

Every connection whose session user holds role `ASOF_ANALYST` (the all-domain analyst `asofread` and the domain
analysts `airread` and `bankread`, see [row permissions](row-permissions.md)) lands in workload `WL_ASOF_ANALYST`.
Everyone else stays in Db2's default user workload, untouched.

| Threshold | Condition | When it acts | SQL4712N reason |
|---|---|---|---|
| `TH_ASOF_ANALYST_COST` | `ESTIMATEDSQLCOST > 1000000` timerons | before the query runs: the optimizer's estimate | 7 |
| `TH_ASOF_ANALYST_ROWS` | `SQLROWSRETURNED > 10000` | when the next row would pass the limit | 8 |
| `TH_ASOF_ANALYST_TIME` | `ACTIVITYTOTALTIME > 10 SECONDS` | while it runs (checked periodically) | 9 |

All three `STOP EXECUTION`: the statement fails with `SQL4712N` and SQLSTATE `5U026`, naming the threshold.
[`wlm.py`](../src/asof/wlm.py) turns that into the plain refusal the Ask page shows (status `STOPPED`), for example
"Db2 refused to run this query: the optimizer estimated it at more than 1,000,000 timerons, the limit for analyst
queries". The model gets one more try with that reason, like any other Db2 error.

This holds for any client of those users, not only AsOf: a script that logs in as `asofread` with the password and
skips the validator still meets the same limits. The app's own controls stay in place on top: the statement timeout
(`SQL_ATTR_QUERY_TIMEOUT`, 10 s) and the 200-row cap.

## Choosing the limits

The optimizer's estimates, from `EXPLAIN`, for the five recorded Ask the ledger examples over 10,000 decisions with
two citations each (a scratch schema loaded by `asof.chainbench`, no `RUNSTATS`): 49, 641, 641, 1,191 and 215
timerons. The cost limit of 1,000,000 is about 800 times the costliest of them. Estimates grow with the data, which is
why there is that much headroom; a deployment with a far larger ledger should look at its own (`python -m asof.explain`)
before lowering the limit.

Deliberately heavy queries over the seeded policy timeline (64 clause versions), on a freshly installed schema like
the tests' own:

| Query | Estimated cost (timerons) | What stops it |
|---|---|---|
| Three-way cross join of `V_POLICY_TIMELINE`, sorted on the clause text | 53,579,378,688, or under 1,000,000 in the tests' own schema | cost or rows |
| Four-way cross join of `V_AUDIT_CLAIMS`, `COUNT(*)` | 142,919,328 | cost |
| Three-way cross join, 262,144 rows returned | 95,182 | rows |
| Four-way cross join of `V_POLICY_TIMELINE`, `COUNT(*)` | 17 | time (16.7 million combinations) |
| Six-way cross join of `V_POLICY_TIMELINE`, `COUNT(*)` | 1 (in the 10,000-decision schema) | time |
| A recursive count to 300,000,000 | 0 | time |

The `COUNT(*)` cross joins show why one limit is not enough: the same four-way join was estimated at 109,399,424
timerons in the 10,000-decision schema and at 17 here, and the six-way one at 1. A cost limit cannot catch what the
optimizer misjudges, so the time limit is there too, and the rows limit catches a cheap query that returns too much.
The row limit is 50 times Ask the ledger's own cap of 200 rows (it fetches at most 201), so block prefetching cannot
reach it. The time limit equals the app's own statement timeout.

The test suite's Ask the ledger tests (`tests/test_db2_askledger.py`) and the replay of the five recorded examples
(`tests/test_db2_replay.py`) pass with the workload in place.

## Tests

[`tests/test_db2_wlm.py`](../tests/test_db2_wlm.py) connects as the analyst users directly, bypassing the validator:

- a sorted three-way cross join of `SYSCAT.COLUMNS` (8,338 rows; estimated at 365,275,512,832 timerons) is refused
  before it runs (reason 7), for `asofread` and for a domain analyst. The catalog is used because its statistics
  are real, while the estimates for the seeded views swing (table above);
- a cheap query returning more rows than the limit is stopped (reason 8);
- a recursive query with a low estimate that would run for minutes is stopped after a little over 10 seconds
  (reason 9);
- the analysts' connections land in `WL_ASOF_ANALYST`, the runtime user's do not, and the live thresholds match
  `wlm.py`;
- through Ask the ledger's own path, a six-way cross join of the timeline view comes back as a `STOPPED` result
  with the plain message (the test raises the app's own timeout past Db2's, so the stop is Db2's, on cost or time).

[`tests/test_wlm.py`](../tests/test_wlm.py) keeps `07_wlm.sql` and `wlm.py` in step and checks the message mapping.

## Spike findings (Db2 12.1.5.0 Community Edition, IBM's stock image)

Workload management works on Community Edition: `CREATE WORKLOAD`, `GRANT USAGE ON WORKLOAD` and `CREATE THRESHOLD ...
STOP EXECUTION` for `ESTIMATEDSQLCOST`, `SQLROWSRETURNED` and `ACTIVITYTOTALTIME` were all accepted and enforced.

- `CREATE WORKLOAD ... SESSION_USER ROLE ('X')` checks that the role exists (`SQL0204N`), so `07_wlm.sql` creates
  `ASOF_ANALYST` first; the grants file then finds it.
- Without `USAGE` on the workload, Db2 maps the connection to its default workload, past the thresholds, so the grant
  is part of the design, and a test checks where connections land.
- `ACTIVITYTOTALTIME > 5 SECONDS` and `> 15 SECONDS` are refused (`SQL0644N`); 10 and 20 are accepted. The spike's
  10-second limit stopped a query after 11.1 s.
- Db2 refuses a second threshold with the same condition on the same workload (`SQL4722N`).
- A workload is dropped only once it is disabled and has no thresholds (`SQL2090N`); `python -m asof.wlm --drop`
  does it in that order.

## Setup, reset and drop

The workload and thresholds are database-level, like the roles and the 32K tablespace, and shared by every AsOf schema
(`ASOF`, the tests' `ASOF_TEST`, the benchmarks' scratch schemas). Setup creates each one if it is missing; dropping or
resetting a schema leaves them alone, since other schemas still use them. `python -m asof.wlm` shows them and where
each current connection landed; `python -m asof.wlm --drop` removes them (setup creates them again). To change a limit
on a database that has them, use `ALTER THRESHOLD` and update `07_wlm.sql` and `wlm.py` to match (a Db2 test fails
while they differ).
