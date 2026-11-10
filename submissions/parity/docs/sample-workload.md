# Sample workload

## What it is

`samples/workload.sql` holds 129 read queries over a small shop schema. It is the workload that shows what Parity is for. The queries come from real application patterns: reports, filters, joins, aggregates, date math, sorting, and subqueries.

The schema has four tables: customers, products, orders, and order_items. The data is fixed, so every run compares the same rows.

## Seed the data

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v $PWD/scripts:/app/scripts \
  -e PARITY_SOURCE_HOST=host.docker.internal \
  -e PARITY_SOURCE_USER=parity -e PARITY_SOURCE_PASSWORD=change-me \
  -e PARITY_SOURCE_DB=parity_source \
  -e PARITY_DB2_HOST=host.docker.internal \
  -e PARITY_DB2_USER=db2inst1 -e PARITY_DB2_PASSWORD=change-me \
  -e PARITY_DB2_DB=parity \
  parity-bridge python /app/scripts/seed_workload.py
```

The script creates the four tables in Postgres, fills them with fixed data, then syncs schema and data to Db2. It prints a checksum for each table so you can see both databases hold the same rows.

## Run it

```bash
parity run --dir samples --out parity-report.html --json-out parity-summary.json --bridge
```

## Live result

On Db2 12.1.5.0 and Postgres 16 the workload gives:

- 129 queries MATCH
- 0 mismatches
- 0 errors

The match rate is 1.0 and the run exits with code 0. The run was repeated at concurrency 4 with the same result.

## What the workload found

Running this workload found two engine bugs and one translation gap. Both engine bugs caused false mismatches on every decimal and boolean column. The translator then needed a select list scanner, because Db2 names an unaliased expression by its text and Postgres names it by the function. See the divergence catalog for the full list.

## Known limits

- The workload is one domain. A real application has more query shapes.
- The data is small. Volume and performance are not tested here.
- A clean run here does not mean a clean run on a real application. The workload shows that the engine and the translator agree on these query shapes.
