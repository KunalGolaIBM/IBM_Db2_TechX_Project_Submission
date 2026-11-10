# Divergence catalog

This page lists the Postgres versus Db2 differences that Parity has actually seen on live databases. Only differences seen on both databases count as real. Hypotheses stay hypotheses.

## Confirmed divergences

### 1. Unaliased aggregate column name

- Query: `SELECT COUNT(*) FROM demo_users`
- Postgres column name: `count`
- Db2 column name: `1`
- Category: COLUMN_NAME
- Why it matters: the query is a valid silent mismatch. Both databases run it, but the column name differs.
- Fix: the `aggregate_alias` rule rewrites a bare aggregate to `COUNT(*) AS COUNT`. After the fix the same query returns MATCH on live databases.

### 2. Trailing space and Unicode text

- Input: fuzzed rows with a trailing space and with Unicode text
- Source result: kept the trailing space and the accented character
- Target result: returned an empty string for those rows
- Category: VALUE
- Why it matters: text handling differs on Db2 12.1.5.0 for these edge case values, so a migration can change answers without an error.
- Status: open. This is the leading live demo target for the Diagnostician agent.

### 3. SELECT without FROM

- Query: `SELECT 1`
- Postgres: returns `1`
- Db2: fails with SQL0104N
- Category: ERROR
- Why it matters: simple sanity queries used in health checks can fail on Db2 even when they pass on Postgres.

### 4. Expression SELECTs without FROM

- Queries: `SELECT 'a ' = 'a'`, `SELECT LENGTH('café')`, `SELECT ROUND(2.5)`, `SELECT CASE WHEN '' IS NULL THEN 'null' ELSE 'notnull' END`, `SELECT 1/2`, `SELECT 0.1 + 0.2`, `SELECT 'HELLO' LIKE 'hello'`
- Postgres: all return a value
- Db2: all fail with an error
- Category: ERROR
- Why it matters: the same root cause as entry 3, but wider. Any expression-only query fails on Db2. Probes in `samples/probes.sql` reproduce all of them.

### 5. Unaliased expression column name

- Query: `SELECT UPPER(name) FROM customers WHERE id = 1`
- Postgres column name: `upper`
- Db2 column name: `1`
- Category: COLUMN_NAME
- Why it matters: the mismatch is not limited to aggregates. Any unaliased function call in the select list gets the expression text as its name on Db2.
- Scale: found 9 times in a 129 query sample workload, which is 7 percent of the workload. The cases are `EXTRACT`, `UPPER`, `LENGTH`, `SUBSTRING`, and a multiplication.
- Status: fixed. The `alias_expressions` rule gives every unaliased select item the name Postgres gives it, using a select list scanner instead of a regex. The workload now matches completely.

### 6. Aggregate scale on decimals

- Query: `SELECT AVG(credit_limit) FROM customers`
- Postgres value: `1786.2766666666666667` (16 decimal places)
- Db2 value: `1786.2766666666666666666` (19 decimal places)
- Category: VALUE
- Why it matters: the two engines keep a different scale for a computed average. The values differ by 3.34e-17.
- Status: known and handled. Parity compares decimals exactly first and then forgives a difference below 1e-9 absolute. A difference that no decimal scale can store is not a real difference. A real difference such as one unit of a DECIMAL(18,6) column is always reported.

### 7. Empty string and blank string compare equal on Db2

- Query: `SELECT COUNT(*) FROM customers WHERE country = ''`
- Postgres: 2 rows
- Db2: 3 rows
- Query: `SELECT COUNT(*) FROM customers WHERE country = ' '`
- Postgres: 1 row
- Db2: 3 rows
- The stored values are identical on both sides. One value is an empty string, one is a single space, one is NULL.
- Category: VALUE
- Why it matters: Db2 treats an empty string and a string of blanks as equal in a comparison. Postgres does not. A filter on an empty string returns a different set of rows, so a report or a join can silently change.
- Status: open. This is the risk that the roadmap listed first, and it is now confirmed on live databases.

### 8. SUM of an integer column overflows on Db2

- Query: `SELECT SUM(quantity) FROM order_items`
- Postgres: `SUM` of an integer returns a bigint, so the sum does not overflow.
- Db2: `SUM` of an INTEGER returns an INTEGER. The sum overflows and the query fails with SQL0802N.
- Category: ERROR
- Why it matters: the query works on Postgres and fails on Db2 once the numbers grow. A report that sums an amount column can crash after the migration.
- Status: fixed. The `sum_to_bigint` rule casts an integer column to a bigint inside SUM. The rule needs the column type, so the translator takes the source schema. A decimal column is never cast, because that would change the value.

### 9. LIMIT over a sort key that is not unique picks different rows

- Query: `SELECT id, order_date FROM orders ORDER BY order_date DESC LIMIT 5`
- Postgres and Db2 both put the NULL rows first for a descending sort. The order of the rows that tie on the sort key is different on each database, so the LIMIT window holds different rows.
- Category: VALUE
- Why it matters: this is the worst kind of silent difference. Both queries run, both return five rows, and the rows are different. A paginated list shows a different page on each database.
- Status: open. It cannot be fixed in the tool, because SQL does not define the order of tied rows. It must be reported, and the fix belongs to the query, for example a unique sort key.

## Matched probes (no divergence)

These hypotheses were tested live and both databases agreed:

- `SELECT name FROM customers ORDER BY name` including NULL ordering.
- `SELECT COUNT(*) FROM customers WHERE name IS NULL`.
- Text comparison with a trailing space in a stored column.
- NULL sort position in a descending sort. Both databases put the NULL rows first for a descending sort.

## The fuzz run that found these

A fuzz run over the sample workload loads 20 edge case rows into every table of both databases and then runs the whole workload. The first run reported 15 mismatches and 4 errors out of 129 queries. Most of them came from two real differences: the empty string and blank string rule, and the integer sum overflow. Eight were only a different order of tied rows, which Parity now reports as its own difference kind instead of a wrong value.

## Divergences that were fixed

These were found live and Parity now handles them:

- Unaliased aggregate column name, and then every unaliased select expression. The `alias_expressions` rule names each select item the way Postgres names it. It uses a select list scanner, so it never touches a WHERE clause or an ORDER BY.
- `OFFSET` without `LIMIT`, fixed by the `offset_to_rows` rule. Db2 needs `OFFSET n ROWS`.
- `SUM` of an integer column overflowing, fixed by the `sum_to_bigint` rule. The rule needs the column type from the source schema.
- Db2 tables now get the primary key of the source table. A Db2 table without the key would accept duplicate rows that Postgres rejects.
- Db2 returns a DECIMAL column as text. The Db2 executor now converts decimal columns before compare.
- Db2 returns a BOOLEAN column as an integer. The comparator now treats `true` as `1` and `false` as `0`.

## Engine bugs found by the sample workload

The 129 query workload exposed two false positives in the engine. Both were real bugs in Parity, not in the databases:

- Db2 returns a DECIMAL column as text, for example `1000.000000`, while Postgres returns a Decimal. Comparing them reported a type difference. The Db2 executor now converts decimal columns using the driver column type.
- Db2 returns a BOOLEAN column as an integer, while Postgres returns a boolean. The comparator now treats `true` as `1` and `false` as `0`.

The workload also exposed a bridge problem. Under parallel runs a container can fail to start. The bridge now retries once and keeps the real reason in the error message.

## Hypotheses still to confirm

These are expected from the proposal but have not been reproduced on live databases by Parity yet. Do not quote them as facts.

- NULL versus empty string in comparison and joins.
- Rounding rules for decimal values that need half-up or half-even rounding.
- Timezone offset handling for timestamp with time zone values.
- Implicit cast behavior that changes values between the databases.
- Mixed case sort order beyond the tested sample data.

## How to add a new entry

1. Run the probe on both databases.
2. Record the SQL, both outputs, and the category.
3. Add the query to `samples/probes/probes.sql`.
4. Add a row here with status confirmed or open.

## How to run the probes

```bash
parity run --dir samples/probes --bridge
```

The probes live in their own folder so the sample workload folder holds only real workload queries.

## Known limits

This catalog is small. It grows as the probe suite grows. It never claims a difference that has not been seen on both databases. The trailing space value difference is still open: the probe that would test it has no FROM clause, so Db2 rejects it.
