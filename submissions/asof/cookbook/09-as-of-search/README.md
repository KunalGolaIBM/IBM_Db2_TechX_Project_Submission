# As-of search

> What was true on a given date, ranked by meaning: Db2 temporal tables plus native `VECTOR` search in one statement.

A module for IBM's [Db2 AI Cookbook](https://github.com/IBM/db2-ai-cookbook), written in its format and
offered for contribution (see "Contributing" in AsOf's README). Needs **Db2 12.1.2+** (native `VECTOR`;
temporal tables are older).

| Recipe | What it shows | Needs | Last checked |
|---|---|---|---|
| [python-local-embeddings](python-local-embeddings/) | `FOR BUSINESS_TIME AS OF` + `VECTOR_DISTANCE` in one query, `FOR PORTION OF BUSINESS_TIME`, `FOR SYSTEM_TIME AS OF` replay | Db2 12.1.2+ · Python + a local CPU embedding model | ✅ 2026-11-06 |
