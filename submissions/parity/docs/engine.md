# Parity Engine

The engine is the only judge in Parity. It is plain Python code. It never calls a model.

## What it does

- Takes two result sets. One from the source database. One from Db2.
- Normalizes values. Then compares them.
- Returns MATCH, MISMATCH, ERROR, or NOT_COMPARABLE.

## Files

- `src/parity/engine/result.py` - result types. Status, diff kinds, result set.
- `src/parity/engine/normalize.py` - value rules. Decimal, datetime to UTC, bytes, NULL.
- `src/parity/engine/compare.py` - the compare logic and `EngineConfig`.
- `src/parity/engine/nondeterministic.py` - finds `now()`, `random()`, `uuid`, and similar calls.
- `src/parity/engine/executor.py` - database interface. Tests use an in memory version.

## Compare rules

- Column names compare without case. Column order must match.
- Row order is ignored unless the SQL has ORDER BY.
- Duplicate rows count. Rows compare as a multiset.
- Integers must match exactly. They never go through float.
- Decimals compare exactly first. A difference below 1e-9 absolute is then forgiven, because no decimal scale can store it. The two engines keep a different scale for a computed average, and that is not a real difference. A real difference, such as one unit of a DECIMAL(18,6) column, is always reported.
- Floats use a small tolerance. Default is 1e-9 relative.
- A boolean compares with 1 and 0, because Db2 returns a boolean column as an integer.
- NULL equals NULL. NULL never equals an empty string.
- Text compares exactly. Trailing space changes get their own category.
- Timestamps become UTC before compare. A naive timestamp is treated as UTC.
- All settings are saved in the result. Nothing is hidden.

## Db2 value types

The ibm_db driver returns a DECIMAL column as text, for example `1000.000000`. Postgres returns the same value as a Decimal. `src/parity/engine/db2_types.py` converts decimal columns before compare, using the driver column type. Without this step every decimal column reports a false type mismatch.

## Error cases

- Bad row width in a result set raises `ValueError` at build time.
- Negative float tolerance raises `ValueError`.
- A missing preset result in the test executor raises `KeyError`.

## Nondeterministic queries

Some queries cannot be compared safely. Examples: `now()`, `random()`, `gen_random_uuid()`, `current_timestamp`. The detector lists these calls. The caller must pin the value to a fixed one in both databases, or mark the query as NOT_COMPARABLE. It must never pass silently.

## Tests

Run:

```bash
pip install -e .
pytest
ruff check src tests
```

All tests pass. Tests cover identical results, ORDER BY, row count, NULL vs empty string, trailing spaces, decimal exactness, float tolerance, column order, duplicate rows, UTC timestamps, Db2 decimal conversion, and boolean against integer.
