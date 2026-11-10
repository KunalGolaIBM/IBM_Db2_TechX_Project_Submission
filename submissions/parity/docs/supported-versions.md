# Supported versions

## What is tested

| Part | Version | How it was tested |
|---|---|---|
| PostgreSQL | 16 (Alpine container) | every live run in this project |
| IBM Db2 | 12.1.5.0 (Community container) | every live run in this project |
| Db2 minimum | 12.1.2 | the VECTOR type needs 12.1.2 or later |
| Python | 3.11 or later | every test run |
| Docker | any recent version | the Compose file and the bridge image |

The Compose file pins the exact images, so a fresh clone gets the same databases that were tested.

## Operating systems

| System | Status | Note |
|---|---|---|
| Linux | Supported | the direct Db2 driver works, and the bridge also works |
| macOS | Supported | same as Linux |
| Windows | Supported with the bridge | the Db2 driver cannot reach a server, so the Db2 side runs inside the bridge container. Parity does this for you with the `--bridge` flag |

## Database features

Parity reads the schema from PostgreSQL and maps the types to Db2.

- Integer, small integer, big integer, boolean, real, double precision
- Numeric and decimal with their precision and scale
- Character varying and character with their length
- Text, date, time, timestamp, timestamp with time zone
- Uuid, bytea, json, jsonb

The mapping keeps the width of a text column and the precision of a decimal, because a wider Db2 column would accept a value the source rejects. See docs/schema-sync.md.

## What is not supported yet

- Write queries. Parity only runs read only queries. A write query is tagged and never executed.
- Stored procedures and dynamic SQL. A procedure body is one block and is marked for human review.
- Database triggers, views with rules, and custom functions.
- Database links and federation.
- Db2 features with no PostgreSQL counterpart, for example recursive CTE with a different name.

## What is not proved yet

- A run against a workload from a real application. The sample workload is one domain with 130 queries.
- A run against a large data volume. The engine compares result sets, so a very large result uses a lot of memory.
- A model run against a real model. The agent loop was proved against a local fake server that speaks the same shape. The loop, the gateway, the proof and the audit trail are the real ones.
- A pilot with an outside team. Nothing has been run on someone else's workload yet.
