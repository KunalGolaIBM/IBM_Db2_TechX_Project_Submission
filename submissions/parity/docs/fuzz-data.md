# Edge case data generation

## What it does

The fuzzer makes tricky test rows for each table. The same rows load into both databases. Any difference in results then comes from the databases, not from the data.

## Value library

`src/parity/fuzz/values.py` holds one list per category:

- `null`: NULL.
- `empty_string`: empty text.
- `single_space`: one space.
- `trailing_space`: text with trailing spaces.
- `mixed_case`: upper, lower, and mixed case.
- `unicode`: accented text, CJK text, emoji.
- `long_string`: 40 characters. Cut to the column width, so narrow columns stay safe.
- `extreme_int`: zero, minus one, max and min int.
- `rounding_number`: half values that rounding rules treat differently.
- `dst_date`: daylight saving change dates and a leap date.
- `timezone_date`: January and July timestamps in UTC.

## Schema awareness

Plans read the Postgres schema. NOT NULL columns never get the null category. The values fit the column type: a rounding value only goes into a decimal column, and a text value is cut so that the byte count fits the Db2 column width. The primary key keeps a fresh value so the rows do not clash with the base data. Skipped categories are recorded on the plan.

Categories are picked by column type. Text columns get text edge cases. Number columns get extreme and rounding values. Date columns get DST and timezone dates.

## Plan and rows

`src/parity/fuzz/plan.py` builds a `FuzzPlan` from a table definition. Row generation starts from a base row and changes one or two columns per row. A seed makes every run repeatable. The plan id is a stable hash.

## Limits of v1

- The plan is built by type rules, not by an agent yet. The agent fuzzer comes in a later branch.
- Row generation changes random columns. It does not yet target the exact columns a query filters on.
