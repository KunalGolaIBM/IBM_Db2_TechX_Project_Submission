# CatalogLens — Technical Decisions & Architecture Trade-offs

This document details key software architecture decisions, trade-offs, and engineering principles adopted during the design and implementation of **CatalogLens**.

---

## 1. Grounding in Real Db2 Catalog Views (`SYSCAT`)

### Decision
Rely exclusively on IBM Db2 LUW standard system catalog views (`SYSCAT.TABLES`, `SYSCAT.COLUMNS`, `SYSCAT.TABCONST`, `SYSCAT.KEYCOLUSE`, `SYSCAT.REFERENCES`, `SYSCAT.INDEXES`, `SYSCAT.VIEWS`) rather than generic information_schema or simulated catalog files.

### Rationale
- Generic SQL dialects fail to capture Db2-specific constructs, such as table cardinality (`CARD`), column remarks, unique rules (`UNIQUERULE`), or composite key sequences (`COLSEQ`).
- By targeting `SYSCAT`, CatalogLens demonstrates genuine mastery of the IBM Db2 platform.
- The application also supports a built-in demonstration metadata source. This provides a fallback for exploration and offline tests, but it is not a live Db2 connection.

---

## 2. Deterministic Validation Alongside LLM Reasoning

### Decision
Do not let Claude act as the sole arbiter of database facts. Separate deterministic Python logic from semantic LLM reasoning.

### Rationale
- **What deterministic engines do best:** Metadata extraction, primary key indexing, relationship graph traversal, multi-hop dependency tracing, and foreign key verification. These are implemented as deterministic operations and are covered by automated tests.
- **What optional LLM reasoning can contribute:** Semantic interpretation, explanations of ambiguous column acronyms (e.g. `RET_STATUS_CD`), and verification questions. The deterministic fallback is the currently verified path.
- **The Evidence Validator Node:** Every entity, column, or relationship cited in Claude's output is cross-checked against the catalog metadata. If Claude claims a table `NON_EXISTENT_AUDIT` exists, the validator intercepts it, downgrades the claim's confidence to `< 0.50`, marks its status as `UNVERIFIED_ASSUMPTION`, and flags a warning.

---

## 3. Token Efficiency & Context Trimming

### Decision
Never pass the entire enterprise database schema into Claude's prompt context for a single-table question.

### Rationale
- An enterprise database may contain 300+ tables and 5,000+ columns, exceeding token limits and inducing latency.
- CatalogLens dynamically trims the prompt context to:
  1. The target table's columns, data types, nullability, and remarks.
  2. The table's immediate 1-hop declared and inferred relationships.
  3. Upstream and downstream dependent view names.
- This limits the context to information relevant to the selected table and avoids sending the entire schema for every investigation.

---

## 4. Inferred Relationship Detection Heuristics

### Decision
Implement multi-tier deterministic heuristics for relationship discovery before presenting candidate hypotheses to the developer.

### Heuristic Stages:
1. **Exact Column Name Match to Primary Key:**
   If a source column exactly matches a target primary-key column and no explicit foreign key is declared, the detector can produce a high-scoring candidate. The score is a heuristic, not a calibrated probability.
2. **Entity Prefix Matching:**
   If a source column shares an entity prefix with a target key (for example, `CUST_REF_NO` and `CUSTOMER_MST.CUST_ID`), the detector can produce a candidate link for manual verification.
3. **Data Type Compatibility Gate:**
   Check whether source and target column data types belong to the same family (`BIGINT` ~ `INTEGER` allowed; `VARCHAR` ~ `BIGINT` rejected). Incompatible pairs are discarded immediately.
4. **Distinction from Declared Foreign Keys:**
   Declared relationships are identified from Db2 foreign-key metadata. Inferred relationships are separately categorized as candidates and must not be treated as confirmed constraints.

---

## 5. Purposeful LangGraph Design vs. Artificial Chat Agents

### Decision
Use a single, stateful LangGraph pipeline with 6 specialized stages (`MetadataRetriever`, `SchemaAnalyzer`, `RelationshipInvestigator`, reasoning / fallback, `EvidenceValidator`, `ReportGenerator`) rather than simulating conversational back-and-forth between artificial agents.

### Rationale
- Simulating conversations between multiple LLM personas (e.g. "Architect Agent" talking to "DBA Agent") wastes tokens, produces non-deterministic outputs, and makes debugging difficult.
- A directed acyclic graph (DAG) of typed state transitions guarantees reproducible execution, clear progress telemetry in the UI, and modular unit testability.

---

## 6. Zero Arbitrary SQL Execution by the AI

### Decision
CatalogLens strictly prohibits Claude from generating and executing arbitrary DDL or DML against the user's database.

### Rationale
- Enterprise security compliance forbids AI agents from executing unconstrained queries or destructive commands (`DROP TABLE`, `ALTER TABLE`, `TRUNCATE`).
- Catalog inspection is implemented through read-only catalog queries defined in `backend/db/catalog_queries.py`. Query parameterization should be reviewed alongside any future query changes.
- Any recommended schema changes are presented as advice for the human database administrator to execute and test via the **IBM Db2 Developer Extension for VS Code**.
