# Workload ingestion

## What it does

Ingestion reads SQL from files and turns each statement into a tagged `WorkloadQuery` record.

Each record holds:

- The SQL text.
- Where it came from (file name or source name).
- A stable id from the SQL hash.
- Tables it touches, from FROM and JOIN clauses.
- Nondeterministic calls it uses, like `now()` or `random()`.
- Whether it is read only.
- Tags: `read_only`, `write`, `nondeterministic`, `has_tables`.

## Files

- `src/parity/ingest/models.py` - record type, tagging, hash, table extraction.
- `src/parity/ingest/loader.py` - split statements, load one file, load a directory, deduplicate.
- `samples/workload.sql` - a small sample workload for testing.

## Rules

- Empty SQL raises `ValueError`.
- Write queries are kept but marked `read_only = False`. The runner will refuse them later.
- Deduplication keeps the first copy and drops repeats by content hash.
- File order is sorted by file name, so runs are repeatable.

## Example

```python
from pathlib import Path
from parity.ingest.loader import load_sql_dir, deduplicate

queries = deduplicate(load_sql_dir(Path("samples")))
for query in queries:
    print(query.query_id, query.tables, query.tags)
```

## Limits of v1

- Statements split on semicolons. SQL with semicolons inside string literals needs a real parser in a later branch.
- Stored procedures load as one block. They are marked for human review later.
- Log and ORM sources plug into the same `tag_query` function. Only the file loader exists in this branch.
