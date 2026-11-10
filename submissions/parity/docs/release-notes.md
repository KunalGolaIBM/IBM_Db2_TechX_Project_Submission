# Release notes

## Version 1.0.0

Parity 1.0.0 is the first release with the whole loop proved on live databases: find a silent difference, fix it, prove the fix on both databases, and remember the lesson.

## What is in this release

- **The Parity Engine.** Plain Python. It runs both queries, normalizes the values and compares them. It is the only judge. MATCH, MISMATCH, ERROR, and NOT_COMPARABLE come from it alone.
- **Schema and data sync.** Postgres to Db2 with the width and the precision kept, and a checksum that proves both databases hold the same rows.
- **Rule translator.** Seven named rules with a select list scanner, so a rewrite never touches a WHERE clause or an ORDER BY. Plus a type aware rule that needs the column types.
- **Edge case fuzzer.** Eleven value categories that fit the column type, loaded into both databases as the same rows.
- **Agent fix loop.** Diagnostician, Fixer, and the proof of every proposed fix on both databases. Three tries, then a human.
- **Knowledge base in Db2.** A VECTOR column, cosine search, verified only results, and a human review step.
- **Run history and regression mode.** Every run is kept, and a run is compared against the last passing one.
- **One command report.** A self contained HTML file and a JSON summary, with exit codes for a pipeline.
- **Offline replay.** A recorded run repeats with no API key and no network.

## The live evidence

Every number below comes from a run against real PostgreSQL 16 and real IBM Db2 12.1.5.0.

| Run | Result |
|---|---|
| Sample workload, clean data | 130 of 130 MATCH, exit 0 |
| Sample workload, edge case data | 113 MATCH, 17 MISMATCH |
| The same run with the agent loop | 114 MATCH, 16 MISMATCH, 0 errors |

The fuzzer found nine confirmed differences between the two databases. Three of them are the dangerous kind:

- Db2 treats an empty string and a string of blanks as equal. A filter on an empty string returns a different set of rows.
- Db2 overflows on a sum of an integer column. A report that sums an amount column fails after the migration.
- A limit over a sort key that is not unique picks different rows. Both queries run, both return the same number of rows, and the rows are different.

The agent loop proved the first one can be fixed: it explained the blank value rule, rewrote the filter to use the length of the value, and the engine proved the rewrite on both databases.

## Known limits

These are honest limits, not surprises.

- Parity gives strong evidence from real execution. It is not a formal proof.
- It cannot find a difference that its data never triggers.
- Only read only queries run. Write queries are tagged and never executed.
- Stored procedures and dynamic SQL are marked for human review.
- The agent loop was proved against a local model double that speaks the same shape as a real model. The loop, the gateway, the proof and the audit trail are the real ones. A run against a real model has not happened yet, because there is no API key in this environment.
- The sample workload is one domain. It has not run on a real application workload yet.
- The continuous integration workflow exists on a branch and is not merged.

## The state of the roadmap

Phases 1, 2, 3, 4, 6, 7 and 8 of the roadmap are built and proved. Phase 5, the agent loop, is built and proved with a model double. Phase 9, hardening, has the failure mode tests, the timeouts, the metrics, the parallel run and the security sign off. Phase 10, the pilot with an outside team, has not started. Phase 11 is the version 2 work.

## Getting started

The migration guide walks through a migration from end to end: docs/migration-guide.md.

The supported versions are in docs/supported-versions.md. The known differences between the two databases are in docs/divergence-catalog.md, with a probe for each one.
