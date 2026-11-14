# Testing PayGuard

Use Python 3.12 and install `requirements-dev.txt`. The default suite uses local hash
embeddings and the seeded in-memory repository. It disables external Gemini and PayPal
calls and needs no database or API keys.

```bash
python -m ruff check src tests loadtest scripts
python -m mypy src
python -m pytest -q --cov=src --cov-report=term-missing --cov-report=json:.artifacts/unit-coverage.json
```

Coverage targets the actual scoring, signals, analyst, presenter and Db2 repository
implementations, rather than their compatibility wrappers. Recorded results and exact
line counts are in [verification.json](results/verification.json).

The suite covers all 13 current rule families with positive/negative examples, Pidgin,
empty/4000-character/emoji messages, phone/NUBAN boundaries, amounts and numeric overflow.
Security checks include DML/DDL, multiple statements, comments, embedding wildcards,
comma joins, non-allow-listed tables, CTE disguises, arbitrary functions and SELECT INTO.
Checkout tests inject fake amounts and model-proposed ALLOW/negative-risk instructions.

Concurrency tests check exclusive pool leases, capacity, deadlines, reconnects, failed
factories, transaction cleanup and in-flight cache invalidation. DB-API contract tests
verify parameter binding, decoding and transaction boundaries; they do not simulate
SQL semantics. The live integration tests execute the actual SQL.

## Real Docker Db2

```bash
docker compose up -d
# Wait for Setup has completed in docker logs payguard-db2.
python src/seed.py
python -m pytest --db2 -q -m db2
python -m pytest --db2 -q --cov=src --cov-report=json:.artifacts/full-coverage.json
```

`PAYGUARD_DB2_TEST=1` remains an alternative to `--db2`. The registered `db2` marker is
skipped by default. Enabling it fails if Db2 is unavailable; it never substitutes an
in-memory database. Use a test database. Tests clean up their generated report entities
and screenings.

The integration suite verifies migrations, idempotent loading, real vector evidence,
IBM DB2VS and LangChain tools, 50 parallel screenings, 50 concurrent reports against one
account, failed-report rollback, analyst presets and platform checkout end to end.
Assertions require no duplicate entity, distinct IDs, the exact report count, BLOCKED
status and no degraded results during successful concurrent screening.

## Frozen held-out evaluation

```bash
python scripts/evaluate.py --output .artifacts/evaluation-memory.json
python scripts/evaluate.py --db2 --output .artifacts/evaluation-db2.json
```

The original training CSV duplicated all 15 held-out texts. Those rows are removed;
the loader retires their historical IDs from existing databases without reading the
held-out file. Tests assert disjoint knowledge/evaluation texts. Rules and thresholds
were not tuned on this set during the change.

The recorded real-Db2 matrix is `[[5,5],[0,5]]`: actual scam/safe rows and flagged/allowed
columns, with REVIEW and BLOCK counted as flagged. Precision is 1.0, recall 0.5 and
false-positive rate 0.0. This small, previously exposed dataset is not an independent
production benchmark. See the [individual predictions](results/evaluation.json).

## CI

The GitHub Actions workflow runs lint, mypy and unit coverage on pushes and pull requests.
A separate Ubuntu job starts privileged Db2 Community Edition, generates a temporary
password, waits for setup, seeds and runs the actual integration tests. Coverage and
JUnit reports are uploaded as artifacts. A successful local run is distinct from the
remote Actions result.
