# Database executors

This document explains how Parity talks to PostgreSQL and Db2.

## Config

Settings come from environment variables. See `.env.example`.

- `PARITY_SOURCE_HOST`, `PARITY_SOURCE_PORT`, `PARITY_SOURCE_USER`, `PARITY_SOURCE_PASSWORD`, `PARITY_SOURCE_DB` for PostgreSQL.
- `PARITY_DB2_HOST`, `PARITY_DB2_PORT`, `PARITY_DB2_USER`, `PARITY_DB2_PASSWORD`, `PARITY_DB2_DB` for Db2.

The loader lives in `src/parity/config.py`. It never invents a password. Missing values raise a clear error.

## Safety guard

`src/parity/engine/safety.py` allows only SELECT queries and WITH ... SELECT queries. Writes, DDL, and blocked words inside WITH raise `ValueError` before the SQL reaches the database.

## PostgreSQL executor

`src/parity/engine/postgres.py` uses psycopg.

- Sets `statement_timeout` on the server for each query.
- Caps rows. Default limit is 100000. A larger result raises `ValueError`.
- Returns a `ResultSet` with column names and rows.

## Db2 executor

`src/parity/engine/db2.py` uses the official `ibm_db` driver.

- Caps rows the same way.
- Returns a `ResultSet`.
- Db2 timeout is handled by the caller in a later branch. The interface keeps the timeout parameter so both executors match.

### Known issue on Windows

On Windows, the `ibm_db` pip driver can fail with `SQL1042C` even when the Db2 server is healthy and the port is open. This was seen on 2026-11-09: the server answered queries inside the container, the port test passed, but the Windows driver could not connect in any connection string form.

This is a client driver limit, not a Parity code bug. The fix in the next branch is a Linux container bridge: Parity already runs databases in containers, so the Db2 driver will run in a Linux container too. Until then, use Linux or WSL for live Db2 tests. PostgreSQL live tests work on Windows.

## Docker

`docker-compose.yml` starts both databases.

```bash
docker compose up -d
docker compose ps
docker compose down -v
```

Postgres listens on 5432. Db2 listens on 50000. First Db2 start is slow. Wait for the health check.

## Install

```bash
pip install -e ".[db]"
```

This installs `psycopg` and `ibm_db`. Tests for executors use mocks. They need no live database.
