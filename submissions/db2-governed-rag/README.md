# Governed RAG: Clearance-Aware Vector Search Inside Db2

The same question, asked as a **public**, **internal** or **restricted** user, retrieves only the documents that role may read. The clearance rule and the vector search run in one Db2 SQL statement, so restricted text is never returned to the LLM for an unauthorised role.

## How Db2 is used
- `VECTOR(384, FLOAT32)` column and `VECTOR_DISTANCE(..., COSINE)` (Db2 12.1.2+).
- Document metadata (`clearance`, `category`, `priority`, `department`) stored as JSON and filtered with `JSON_VALUE` in the `WHERE` clause of the same statement that ranks by distance.
- Connector: `ibm-db-haystack` (`IBMDb2DocumentStore`, `IBMDb2EmbeddingRetriever`) over `ibm_db`.

## Prerequisites
- Python 3.10+
- IBM Db2 12.1.2 or later, reachable over TCP/IP, with a user that can create tables
- Ollama with `qwen2.5:7b` (not needed with `--no-llm`)

## Setup
```bash
cd submissions/db2-governed-rag
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r src/requirements.txt
cp .env.example .env     # set DB2_HOST, DB2_PORT, DB2_DB, DB2_USERNAME, DB2_PASSWORD
```

## Run
```bash
cd src
python index.py                                                    # writes 30 documents to table gov_kb
python query.py "How was the security incident handled?"           # runs the question as all 3 roles
python query.py --no-llm "How was the security incident handled?"  # retrieval only
```

| Role | Clearance levels retrieved |
|---|---|
| public user | public |
| internal user | public, internal |
| restricted user | public, internal, restricted |

## Check the data in Db2
```sql
SELECT id, JSON_VALUE(SYSTOOLS.BSON2JSON(meta), '$.clearance' RETURNING VARCHAR(100)) AS clearance
FROM gov_kb;
```

## Tests
```bash
pip install pytest && python -m pytest tests -q
```
`tests/test_filters.py` checks that each role's filter is translated into a SQL `IN (...)` predicate and that the dataset contains all three clearance levels. It does not need a database.

## Data
30 fictional documents in `src/data/documents.jsonl`. Regenerate with `python build_dataset.py` from `src/`.

## Dependency licenses
haystack-ai, ibm-db-haystack, ibm_db, sentence-transformers and the model `all-MiniLM-L6-v2`: Apache-2.0.
