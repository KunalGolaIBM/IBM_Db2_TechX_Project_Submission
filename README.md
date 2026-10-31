# Db2 Support RAG

> **One-Line Pitch:** A privacy-first support assistant that keeps retrieval inside IBM Db2: support questions are embedded locally, filtered by category, and ranked with Db2 vector search before an optional answer model sees the context.

## Problem Statement

Db2 operators often search runbooks, incident notes, and tuning guidance across disconnected tools. A support assistant should find the right guidance quickly without exporting the knowledge base to an application-side vector store.

## Solution Overview

This CLI seeds a small fictional support knowledge base and retrieves the five closest articles for a question. Db2 performs both metadata filtering and cosine-distance ranking. The deterministic local embedding baseline makes the sample reproducible offline; it can be replaced with an IBM watsonx or sentence-transformer embedding service without changing the Db2 schema or retrieval contract.

## IBM Db2 Integration

- **Edition:** Db2 Community Edition 12.1.2+ or Db2 on IBM Cloud.
- **Connector:** `ibm_db`.
- **Schema:** `DB2SUPPORT.SUPPORT_ARTICLES` stores title, body, category, and `VECTOR(8, FLOAT32)` embedding.
- **Retrieval:** `VECTOR_DISTANCE(embedding, VECTOR(?, 8, FLOAT32), COSINE)` runs in Db2, with an optional parameterized category predicate and `FETCH FIRST 5 ROWS ONLY`.
- **Safety:** credentials come from environment variables and the user question is passed as a bound parameter rather than interpolated into SQL.

## AI / LLM Architecture

The included embedding is a deterministic baseline for a zero-key demo. In a production deployment, replace `embed()` with a managed embedding model such as watsonx.ai Granite embeddings, then pass the returned context to an answer model. The retrieval boundary remains Db2-native.

## Tech Stack

Python 3.10+, IBM `ibm_db`, IBM Db2 vector SQL, and a standard-library CLI.

## Setup & Installation

```bash
cd submissions/db2-support-rag
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r src/requirements.txt
copy .env.example .env  # Windows; use cp on macOS/Linux
```

Set `DB2_HOST`, `DB2_PORT`, `DB2_DB`, `DB2_USERNAME`, and `DB2_PASSWORD` in `.env`. Never commit the real `.env` file.

## Running the Project

```bash
cd src
python seed.py
python query.py "How do I resolve a deadlock?" --category transactions
python query.py "How does Db2 rank vectors?" --category vectors
```

## Testing & Verification

The tests verify embedding stability, vector dimensions, SQL parameterization, and the Db2 vector-distance query without requiring a live database:

```bash
pip install pytest
python -m pytest tests -q
```

## Known Limitations & Roadmap

- The sample embedding is intentionally small and is not a substitute for a production language model.
- The demo does not ship a UI or LLM key; the next step is a FastAPI endpoint with watsonx.ai answer generation and Db2 audit logging.
- Add tenant-aware authorization predicates and a Db2 vector index when the corpus grows.

## Team Members & Credits

Yasharth Singhal (`Yasharth-Singhal`) — Db2 integration, retrieval design, tests, and documentation.
