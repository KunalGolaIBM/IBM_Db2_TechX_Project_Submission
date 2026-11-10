# Fuzz run

## What it does

A fuzz run answers the question that normal tests cannot: does the query still return the same answer on tricky data? It loads edge case rows into both databases, runs the whole workload on both, and lets the engine decide.

## Run it

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v $PWD/scripts:/app/scripts -v $PWD/samples:/app/samples \
  -e PARITY_SOURCE_HOST=host.docker.internal \
  -e PARITY_SOURCE_USER=parity -e PARITY_SOURCE_PASSWORD=change-me \
  -e PARITY_SOURCE_DB=parity_source \
  -e PARITY_DB2_HOST=host.docker.internal \
  -e PARITY_DB2_USER=db2inst1 -e PARITY_DB2_PASSWORD=change-me \
  -e PARITY_DB2_DB=parity \
  parity-bridge python /app/scripts/fuzz_workload.py --dir /app/samples --rows 20
```

The run happens inside the bridge container because the Db2 driver only works there on this machine. Add `--out report.json` to save the findings.

## Steps

1. Read the schema of every table from Postgres, including the primary keys.
2. Build a fuzz plan for each table. The plan picks the edge case values that fit the column type.
3. Generate the rows. The primary key gets a fresh value so the rows do not clash with the base data.
4. Remove the rows of an earlier fuzz run, so the same seed gives the same dataset.
5. Load the same rows into Postgres and into Db2. Every insert uses bound parameters.
6. Run the workload on both databases and compare.

## What the first live run found

On the sample workload with 20 rows per table:

- 110 queries matched
- 15 queries mismatched
- 4 queries failed

The mismatches came from two real differences: Db2 treats an empty string and a string of blanks as equal, and Db2 sorts tied rows in a different order. The failures came from Db2 overflowing on a sum of integers. All of them are in the divergence catalog.

## After the schema aware translator

The `sum_to_bigint` rule needs the column types, so the translator now takes the source schema. With that rule the same fuzz run gives:

- 113 queries matched
- 16 queries mismatched
- 0 queries failed

The four failures are gone. The sixteen mismatches are all real: eight are a different order of tied rows, five come from the empty string and blank string rule, and three come from a LIMIT over a sort key that is not unique.

## The data must fit both databases

The fuzzer only generates values that load into both databases. Two rules matter:

- Db2 counts the bytes of a VARCHAR, Postgres counts the characters. A text value is cut so that the byte count fits.
- A rounding value only goes into a decimal column. A rounding value in an integer column is a data error and would hide the difference we look for.

## Known limits

- The fuzzer changes random columns. It does not yet target the exact columns a query filters on.
- The plans are built by type rules, not by an agent yet.
- The rows stay in the test databases after a run. The next run removes them first.
