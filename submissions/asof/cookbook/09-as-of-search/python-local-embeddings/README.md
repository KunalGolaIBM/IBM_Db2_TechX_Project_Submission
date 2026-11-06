# As-of search with local embeddings

> **Last checked 2026-11-06**: verified by executing the notebook end to end with nbconvert. The same
> claim returned clause version `2026-01-01` for 10 March and `2026-05-01` for 2 June from one
> statement; `FOR PORTION OF BUSINESS_TIME` split the row; `FOR SYSTEM_TIME AS OF` replayed the old text.
> Checked on: Db2 12.1.5.0 Community Edition (Docker, x86 image under Rosetta) · macOS 14 arm64 · Python 3.12.8.

[← As-of search](../README.md)

> Store dated policy clauses in a Db2 bitemporal table with a native `VECTOR` column, and ask "which
> clause, in force on this date, best matches this claim?" in one SQL statement.

![Db2](https://img.shields.io/badge/store-Db2%2012.1.2%2B%20VECTOR%20%2B%20temporal-054ada)
![Embeddings](https://img.shields.io/badge/embeddings-all--MiniLM--L6--v2%20on%20CPU-0f62fe)
![Python](https://img.shields.io/badge/Python-3.12-blue)

A customer who booked in March and one who booked in June ask the same question, and the right answer
differs because the policy changed on 1 May. The notebook loads three fictional clauses, changes one of
them from 1 May, and shows the as-of query, the automatic row split and the replay of what the database
held before the change. No API key, no model download beyond the 90 MB embedding model.

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then set DB2_PASSWORD
jupyter nbconvert --to notebook --execute --inplace as-of-search.ipynb   # or open it in VS Code
```

The notebook creates its own schema, `ASOF_RECIPE`, and drops it in the last cell. It needs a user that
may create tables (the instance owner, `db2inst1`, in a Community Edition container).

## Expected output

| Step | You should see |
|---|---|
| Connect | `DB2/LINUXX8664 12.01.0500` (any 12.1.2 or later) |
| The change on 1 May | Two `BRV-002` rows: `2026-01-01` to `2026-05-01`, and `2026-05-01` to `9999-12-31` |
| As-of query | `2026-03-10: BRV-002 from 2026-01-01` (before travel only) and `2026-06-02: BRV-002 from 2026-05-01` (retroactive within 90 days) |
| Replay | For 2 June, the database held the old text before the change was recorded, and holds the new text now; one row in history |

## Concepts

### Two clocks

`BUSINESS_TIME` (`BUS_START`, `BUS_END`) is when a clause applies to customers. `SYSTEM_TIME` is when the
database held a row; Db2 sets it and moves replaced rows to the history table by itself.
`PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS)` makes two versions of one clause on the same
day impossible.

### One statement, not two systems

```sql
SELECT c.CLAUSE_ID, c.BUS_START, c.CLAUSE_TEXT,
       VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
FROM CLAUSE FOR BUSINESS_TIME AS OF ? AS c
ORDER BY DIST
FETCH FIRST 2 ROWS ONLY
```

The date filter and the similarity ranking are one query. A separate vector store would need its own
copy of every version and its own idea of which one is in force; here there is nothing to keep in step.

### `FOR PORTION OF` and replay

`UPDATE CLAUSE FOR PORTION OF BUSINESS_TIME FROM '2026-05-01' TO '9999-12-31' SET ...` changes the clause
from 1 May only; Db2 splits the row at the boundary. Adding `FOR SYSTEM_TIME AS OF <moment>` in front of
`FOR BUSINESS_TIME AS OF` reads the table as it stood at that moment: the evidence for "what did our
system know when it answered?"

## Appendix: Apple Silicon

IBM's Db2 image is x86 only. Under Colima with Rosetta it runs, but IBM's setup script needs a login
shell to find `db2` (see AsOf's README, "Why AsOf builds its own Db2 image"). Fenced routines such as
`SYSPROC.ENV_GET_INST_INFO` crash there, so the notebook reads the server level from the driver instead.
