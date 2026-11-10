# MediTwin AI — Technical Decisions

## TD-001: Database — IBM Db2 Community Edition via Docker

**Decision:** Use Db2 Community Edition in Docker container.
**Rationale:** No Db2 installation exists. Docker provides fastest path to a running instance. Db2 Community Edition is free and approved for hackathon.
**Fallback:** Native Windows Db2 installer if Docker cannot be installed.

## TD-002: Gemini API via LangChain

**Decision:** Use `langchain-google-genai` with `gemini-2.0-flash` model.
**Rationale:** LangChain is an approved hackathon framework. Gemini API avoids local LLM resource consumption. `google-genai` SDK is already installed.

## TD-003: No Vector Search in MVP

**Decision:** Use relational queries, indexed metadata, and keyword retrieval.
**Rationale:** The proposal explicitly says "Vector search is optional" and we must version-gate it. Db2 Community Edition may not support VECTOR type. The application must work fully without it.

## TD-004: Streamlit Single-App Architecture

**Decision:** Single `app.py` with page-based navigation using `st.navigation`.
**Rationale:** Streamlit's built-in multipage support is clean and sufficient. No need for a separate backend API server for a demo prototype.

## TD-005: Parameterized Query Templates (No Dynamic SQL)

**Decision:** All Db2 queries use `ibm_db.prepare()` + `ibm_db.execute()` with parameter markers.
**Rationale:** Security requirement. The LLM must never generate or execute arbitrary SQL. Predefined templates cover all required query patterns.

## TD-006: Pydantic for All Structured Data

**Decision:** Use Pydantic v2 models for observation extraction, validation, and API contracts.
**Rationale:** Already installed (v2.13.4). Provides strict type validation, serialization, and integrates with LangChain structured output.

## TD-007: LangGraph Minimal Workflow

**Decision:** One LangGraph `StateGraph` with conditional routing for ingestion vs. query paths.
**Rationale:** The proposal states "LangGraph is optional orchestration." Keep it simple — one graph, clear nodes, typed state. No multi-agent swarm.

## TD-008: Audit Log is Append-Only

**Decision:** AUDIT_LOG table is insert-only. No updates or deletes.
**Rationale:** Maintains full history of all actions for traceability. Required by the data integrity specification.

## TD-009: Review Status Gate

**Decision:** Only APPROVED observations appear in timeline and Q&A results.
**Rationale:** Core safety requirement. Extracted observations default to PENDING. Human must explicitly approve before data enters trusted views.

## TD-010: Synthetic Data Only

**Decision:** All patient data is explicitly synthetic with demo identifiers.
**Rationale:** Hackathon requirement. No real PHI. Patients use codes like DEMO-001.

