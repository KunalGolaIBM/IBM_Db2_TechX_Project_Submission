# Migration guide

This guide walks through a migration from PostgreSQL to IBM Db2 with Parity.

## 1. Get the environment ready

```bash
git clone https://github.com/Amitk003/Parity.git
cd Parity
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS or Linux: source .venv/bin/activate
pip install -e ".[dev,db]"
docker compose up -d
```

The compose file starts a PostgreSQL 16 container and an IBM Db2 12.1.5.0 container. The Db2 container needs a few minutes to create its database the first time.

On Windows the Db2 driver cannot reach a server, so the Db2 side runs inside the bridge container. Parity handles that for you with the `--bridge` flag.

## 2. Put your schema and data into both databases

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v $PWD/scripts:/app/scripts \
  -e PARITY_SOURCE_HOST=host.docker.internal \
  -e PARITY_SOURCE_USER=parity -e PARITY_SOURCE_PASSWORD=change-me \
  -e PARITY_SOURCE_DB=parity_source \
  -e PARITY_DB2_HOST=host.docker.internal \
  -e PARITY_DB2_USER=db2inst1 -e PARITY_DB2_PASSWORD=change-me \
  -e PARITY_DB2_DB=parity \
  parity-bridge python /app/scripts/seed_workload.py
```

For your own project, point the settings at your databases and use the same sync code: `introspect_postgres`, `build_create_table`, and `copy_table` in `src/parity/sync/`. The checksum proves both databases hold the same rows.

## 3. Collect your SQL

Put the queries in a folder as `.sql` files, one statement per line. Look at `samples/workload.sql` for the shape. Then check what Parity makes of them:

```bash
parity ingest --dir workload
```

It prints the query count, how many are read only, how many the rules cannot translate, and which tables you touch.

## 4. Run the comparison

```bash
parity run --dir workload --out parity-report.html --json-out parity-summary.json --history parity-history.json --bridge
```

Exit codes: 0 every query matched, 1 at least one mismatch, 2 an error or a query that could not be compared. The HTML file is the report you attach to a ticket.

## 5. Test the edge case data

Normal data hides most differences. Load the edge case rows into both databases and run the workload again:

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v $PWD/scripts:/app/scripts -v $PWD/workload:/app/workload \
  -e PARITY_SOURCE_HOST=host.docker.internal \
  -e PARITY_SOURCE_USER=parity -e PARITY_SOURCE_PASSWORD=change-me \
  -e PARITY_SOURCE_DB=parity_source \
  -e PARITY_DB2_HOST=host.docker.internal \
  -e PARITY_DB2_USER=db2inst1 -e PARITY_DB2_PASSWORD=change-me \
  -e PARITY_DB2_DB=parity \
  parity-bridge python /app/scripts/fuzz_workload.py --dir /app/workload --rows 20
```

See docs/fuzz-run.md for what it does and how to read the result.

## 6. Let the agent try to fix a mismatch

```bash
export PARITY_LLM_BASE_URL=https://your-model-endpoint/v1
export PARITY_LLM_MODEL=your-model
export PARITY_LLM_API_KEY=your-key
parity run --dir workload --fix-loop --bridge
```

The Diagnostician explains the difference, the Fixer proposes a rewrite, and the engine proves the rewrite on both databases. A fix that does not prove itself is not accepted. After three tries the query goes to a human.

## 7. Remember what worked

```bash
parity kb-capture --history parity-history.json --store db2
parity kb-review --action list --store db2
parity kb-review --action approve --title "the title from the list" --store db2
```

Every proven rewrite becomes a candidate. A human approves the good ones, and an approved lesson is found by search in the next run.

## 8. Keep it green

Run the same workload on every change and compare against the last passing run:

```bash
parity run --dir workload --history parity-history.json --regression --bridge
```

The regression section names the queries that broke since the last passing run. See docs/regression.md.

## What Parity cannot do yet

- It only runs read only queries. Write queries are marked and never executed.
- It cannot find a difference that its data never triggers.
- It proves one workload at a time. It does not read your application code.
