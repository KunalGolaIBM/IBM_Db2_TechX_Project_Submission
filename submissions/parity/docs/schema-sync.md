# Schema sync

This document explains how Parity copies schema and data from PostgreSQL to Db2.

## Type mapping

`src/parity/sync/types.py` maps each PostgreSQL type to one Db2 type.

- `integer` becomes `INTEGER`.
- `character varying` becomes `VARCHAR(255)`.
- `text` becomes `VARCHAR(4000)`.
- `timestamp with time zone` becomes `TIMESTAMP WITH TIME ZONE`.
- `numeric` becomes `DECIMAL(18, 6)`.

Unknown types raise `ValueError`. Parity never guesses a type.

## Schema introspection

`src/parity/sync/schema.py` reads table and column info from PostgreSQL `information_schema`. It builds Db2 `CREATE TABLE` statements with quoted identifiers.

## Db2 admin client

`src/parity/sync/db2_admin.py` runs DDL and DML on the disposable Db2 test database only. It uses bound parameters for inserts, so values never become SQL text.

The read only workload path stays separate. Workload queries still go through `Db2Executor` and the safety guard.

## Data copy and checksum

`src/parity/sync/data.py` reads rows from PostgreSQL in batches, inserts them into Db2, and builds a SHA256 checksum over sorted rows. The checksum proves both databases hold the same data before any comparison runs.

## Docker note

The Db2 image is `icr.io/db2_community/db2:12.1.5.0`. The old `ibmcom/db2` image on Docker Hub only goes up to 11.5 and is being retired. Db2 12.1.5 is newer than the 12.1.2 minimum and still has the VECTOR type.

Start both databases with:

```bash
docker compose up -d
docker compose ps
```

First Db2 start takes several minutes. Wait for the container to finish setup before you run a comparison.
