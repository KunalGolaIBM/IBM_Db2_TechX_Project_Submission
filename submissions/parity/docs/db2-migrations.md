# Db2 migrations

## What it does

The system of record tables are versioned. `src/parity/migrations.py` holds the list in order. `apply_migrations(admin)` creates only the tables that are missing, so a rerun is safe.

## Tables

- `001` run
- `002` comparison_result
- `003` known_difference with the VECTOR column
- `004` llm_cache

## Files

The same DDL lives in `migrations/` as SQL files for review. They are not executed directly. The Python registry is the runner. A later table gets the next version number.

## Why

Without versions, a schema change becomes a hand edit on the database. With versions, every run can bring a fresh database to the same shape with one call.
