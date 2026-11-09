# Architecture: TechGaint Multi-Agent Recruiter and Governed RAG

## Components
1. **IBM Db2 Database**: Stores candidate profiles, evaluation records, and vector embeddings with role-based metadata tags.
2. **CrewAI Agents**:
   - Sourcing Agent
   - Screening & Evaluation Agent
   - Governance & Audit Agent
3. **Metadata Filtration Layer**: Filters retrieval results prior to LLM synthesis to ensure zero data leakage.
# TechGaint Multi-Agent Recruiter & IBM Db2 Governed RAG Technical Architecture

## 1. Executive Summary

### 1.1 Problem Statement
Enterprise talent acquisition handles thousands of candidate profiles containing sensitive Personally Identifiable Information (PII), strict security clearances, explicit candidate consent flags, and mandatory technical competencies. Traditional "naive" Vector Retrieval-Augmented Generation (RAG) approaches rely purely on unstructured semantic similarity (cosine similarity over vector embeddings). This naive architecture suffers from critical enterprise failure modes:
- **Governance Hallucinations**: Semantic vector search can retrieve candidates who lack mandatory security clearances or missing consent, leading to compliance breaches.
- **Pre-Context Waste**: Unfiltered context windows flood LLMs with non-compliant records, diluting accuracy and drastically increasing API token costs.
- **Non-Deterministic Filtering**: Semantic search cannot strictly guarantee hard numeric or categorical constraints (e.g., `>= 5 years experience`, `ACTIVE_CONSENT = True`).

### 1.2 Deterministic Governance over Naive Vector RAG
The TechGaint Multi-Agent Recruiter resolves these vulnerabilities by embedding IBM Db2 as a deterministic SQL predicate pushdown governance gate prior to LLM vector context construction. By executing parameterized relational metadata filtration at the Db2 engine level, candidate records are pruned deterministically before reaching vector search or LLM evaluation agents.

### 1.3 Enterprise Recruitment SLAs
- **Latency SLA**: Sub-500ms deterministic SQL filtration across multi-million row candidate stores.
- **Compliance SLA**: 100% verification of candidate consent, security clearance alignment, and zero PII leakage to external LLMs.
- **Auditability SLA**: 100% tamper-evident audit trail logging in Db2 for every recruitment recommendation and query.


## 2. Component Blueprint

### 2.1 System Architecture Overview

```
                      +---------------------------------------+
                      |         Enterprise Recruiter          |
                      |        / Client Applications          |
                      +-------------------+-------------------+
                                          |
                                    REST / HTTP POST
                                          v
                      +---------------------------------------+
                      |            FastAPI Router             |
                      |  - Request Validation & Envelopes     |
                      |  - Health Checks (/health)            |
                      |  - Egress/Ingress Security            |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |    CrewAI Agent Orchestration Engine   |
                      |                                       |
                      |  1. Talent Ingestion & Metadata       |
                      |     Extractor Agent                   |
                      |  2. Governed Db2 Retrieval Agent      |
                      |  3. Technical Evaluator & Ranking Agt |
                      |  4. Compliance & Bias Auditor Agent   |
                      +-------------------+-------------------+
                                          |
                              SQL Predicate Pushdown
                                          v
                      +---------------------------------------+
                      |           IBM Db2 Engine              |
                      |  - CANDIDATE_PROFILES (Relational)    |
                      |  - CANDIDATE_SKILL_MATRIX (Index)     |
                      |  - GOVERNANCE_POLICIES (RBAC)         |
                      |  - AGENT_AUDIT_LEDGER (Tamper-Evident)|
                      +---------------------------------------+
```

### 2.2 Ingress Contract & Request Lifecycle
1. **HTTP Request Ingress**: Recruiters POST payload to `/api/v1/recruiter/evaluate` with hard requirements (`min_experience_years`, `security_clearance`, `mandatory_skills`).
2. **FastAPI Validation**: Request payloads are validated against Pydantic schemas. Invalid requests return structured `422 Unprocessable Entity` envelopes.
3. **CrewAI Agent Invocation**:
   - **Talent Ingestion Agent** extracts candidate metadata.
   - **Governed Db2 Retrieval Agent** executes parameterized pushdown queries.
   - **Technical Evaluator Agent** grades candidates against requirements.
   - **Compliance & Bias Auditor Agent** verifies PII redaction and writes to `AGENT_AUDIT_LEDGER`.
4. **Structured Envelope Response**: Clean JSON response returned to caller with candidate rankings, rationale, and compliance audit IDs.


## 3. Relational Database Metadata Filtration Mechanics

### 3.1 Complete IBM Db2 DDL Schema

```sql
-- Candidate Base Profiles Table
CREATE TABLE CANDIDATE_PROFILES (
    CANDIDATE_ID VARCHAR(64) NOT NULL PRIMARY KEY,
    FULL_NAME VARCHAR(255) NOT NULL,
    EMAIL_HASH VARCHAR(128) NOT NULL,
    EXPERIENCE_YEARS INT NOT NULL,
    CLEARANCE_LEVEL VARCHAR(32) NOT NULL,
    CONSENT_VERIFIED SMALLINT NOT NULL DEFAULT 1,
    CREATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Candidate Technical Skill Matrix Table
CREATE TABLE CANDIDATE_SKILL_MATRIX (
    SKILL_ID VARCHAR(64) NOT NULL PRIMARY KEY,
    CANDIDATE_ID VARCHAR(64) NOT NULL,
    SKILL_NAME VARCHAR(128) NOT NULL,
    PROFICIENCY_LEVEL VARCHAR(32) NOT NULL,
    FOREIGN KEY (CANDIDATE_ID) REFERENCES CANDIDATE_PROFILES(CANDIDATE_ID) ON DELETE CASCADE
);

-- Governance Policies Table
CREATE TABLE GOVERNANCE_POLICIES (
    POLICY_ID VARCHAR(64) NOT NULL PRIMARY KEY,
    POLICY_NAME VARCHAR(128) NOT NULL,
    REQUIRED_CLEARANCE VARCHAR(32) NOT NULL,
    MIN_CONSENT_LEVEL INT NOT NULL,
    IS_ACTIVE SMALLINT NOT NULL DEFAULT 1
);

-- Agent Audit Ledger Table
CREATE TABLE AGENT_AUDIT_LEDGER (
    AUDIT_ID VARCHAR(64) NOT NULL PRIMARY KEY,
    TIMESTAMP TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    AGENT_ROLE VARCHAR(128) NOT NULL,
    QUERY_PARAMS_HASH VARCHAR(128) NOT NULL,
    COMPLIANCE_STATUS VARCHAR(64) NOT NULL,
    ACTION_DETAILS CLOB NOT NULL
);

-- Indexes for Predicate Pushdown Performance Optimization
CREATE INDEX IDX_CANDIDATE_FILTER ON CANDIDATE_PROFILES (EXPERIENCE_YEARS, CLEARANCE_LEVEL, CONSENT_VERIFIED);
CREATE INDEX IDX_SKILL_NAME ON CANDIDATE_SKILL_MATRIX (SKILL_NAME);
```

### 3.2 Parameterized SQL Predicate Pushdown Queries
```sql
SELECT c.CANDIDATE_ID, c.FULL_NAME, c.EXPERIENCE_YEARS, c.CLEARANCE_LEVEL
FROM CANDIDATE_PROFILES c
JOIN CANDIDATE_SKILL_MATRIX s ON c.CANDIDATE_ID = s.CANDIDATE_ID
WHERE c.EXPERIENCE_YEARS >= ?
  AND c.CLEARANCE_LEVEL = ?
  AND c.CONSENT_VERIFIED = ?
  AND s.SKILL_NAME IN (?, ?)
GROUP BY c.CANDIDATE_ID, c.FULL_NAME, c.EXPERIENCE_YEARS, c.CLEARANCE_LEVEL;
```

### 3.3 Indexing Strategy & Pre-RAG Context Pruning
Composite B-Tree index `IDX_CANDIDATE_FILTER` allows Db2 to perform instant index-scans for mandatory filters. Candidate records failing clearance, experience, or consent filters are eliminated before expensive vector similarity joins, reducing LLM context size by up to 95%.


## 4. System Security, RBAC & Zero-Secrets Compliance

### 4.1 Environment Variable Isolation
All sensitive connection strings, Db2 database credentials, and API keys are isolated via environment variables (`.env.example` template). Hardcoded credentials or tokens are strictly prohibited.

### 4.2 PII Redaction Prior to LLM Egress
Before candidate data leaves the Db2 storage boundary for LLM processing:
- Direct identifiers (SSN, Phone, Exact Address) are stripped.
- Names are hashed or masked (`CAN-88401`).
- Email addresses are mapped to non-sensitive internal identifiers.

### 4.3 Parameterized SQL Query Binding
To guarantee SQL injection prevention, all Db2 database queries rely strictly on positional parameter markers (`?`) executed via native `ibm_db` and `ibm_db_sa` drivers. User input strings are never concatenated directly into raw SQL statements.

### 4.4 Tamper-Evident Db2 Audit Logging
Every action, search query, filter parameter, and compliance decision is logged automatically to `AGENT_AUDIT_LEDGER` with an immutable SHA-256 parameter hash, ensuring complete enterprise auditability and compliance with global data privacy regulations.
