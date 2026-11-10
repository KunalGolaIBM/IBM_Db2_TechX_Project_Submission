# MediTwin AI — System Architecture Specification

## 1. Executive Summary

**MediTwin AI** is a clinical record intelligence platform engineered for **IBM Db2Hack 2026**. It solves a fundamental problem in modern digital health: clinical data is fragmented across disconnected laboratory PDFs, physician notes, and repeated diagnostic panels. Clinicians and reviewers spend substantial time manually comparing dates, reconciling incompatible units, and hunting for source documentation.

MediTwin AI bridges this gap by converting unstructured synthetic medical documents into a verified, longitudinal patient timeline where **every observation is permanently linked to its exact document, page, and text snippet**.

```
                           +-------------------------------------+
                           |            Streamlit UI             |
                           +-------------------------------------+
                                      /               \
                                     /                 \
                     [ Pipeline A: Ingestion ]   [ Pipeline B: Intelligence ]
                                   v                     v
                        +--------------------+  +--------------------+
                        |      LangGraph     |  |      LangGraph     |
                        | Ingestion Workflow |  |    Query Workflow  |
                        +--------------------+  +--------------------+
                                   |                     |
                        +--------------------+  +--------------------+
                        |  LangChain + LLM   |  | Parameterized Query|
                        |   Extraction &     |  |     Templates      |
                        | Pydantic Validator |  |   (Zero Dynamic)   |
                        +--------------------+  +--------------------+
                                   |                     |
                        +--------------------+           |
                        | Human Review Gate  |           |
                        | (PENDING->APPROVED)|           |
                        +--------------------+           |
                                   \                     /
                                    \                   /
                                     v                 v
                           +-------------------------------------+
                           |         IBM Db2 System of Record    |
                           |   (ibm_db Prepared Transactions)    |
                           +-------------------------------------+
```

---

## 2. Core Architectural Principles

1. **IBM Db2 as Authoritative System of Record:** The database is the single source of truth. The LLM performs language extraction and summarization, never factual record keeping.
2. **Deterministic Computation:** Longitudinal trends (absolute change, percentage delta) are computed deterministically in Python rather than entrusted to LLM arithmetic.
3. **Mandatory Human-in-the-Loop Gate:** All newly extracted observations default to `PENDING`. Only `APPROVED` records enter trusted timelines and evidence-grounded Q&A.
4. **Zero Dynamic SQL:** The LLM is never provided database credentials and never generates executable SQL. All queries use pre-compiled prepared statements with parameter markers (`?`).
5. **Strict Provenance:** Every observation retains `source_document`, `source_page`, and `source_snippet`.
6. **Medical Safety Safeguards:** Strict enforcement of synthetic demo data, no autonomous disease diagnosis, no medication prescribing, and explicit clinical disclaimers.

---

## 3. Detailed Data Pipelines

### Pipeline A: Document Ingestion & Verification

```mermaid
sequenceDiagram
    autonumber
    actor User as Clinical Reviewer
    participant UI as Streamlit Dashboard
    participant P as PyMuPDF Parser
    participant LC as LangChain Extractor
    participant VAL as Pydantic Validator
    participant DB as IBM Db2 Database
    participant AL as Audit Logger

    User->>UI: Uploads synthetic report (PDF/TXT)
    UI->>P: Validate extension & size limit (<=10MB)
    P->>P: Extract text page-by-page & compute SHA-256 hash
    UI->>DB: INSERT into DOCUMENT (parse_status='PARSED')
    UI->>LC: Extract observations with Gemini prompt
    LC->>VAL: Parse structured JSON into ExtractedObservation models
    VAL->>VAL: Validate date formats, normalize codes, flag missing units
    VAL->>DB: INSERT into OBSERVATION (review_status='PENDING')
    VAL->>AL: Log EXTRACTION_COMPLETE event
    UI->>User: Display editable Human Review interface
    User->>UI: Reviews, corrects values/units, clicks Approve
    UI->>DB: UPDATE OBSERVATION SET review_status='APPROVED'
    UI->>AL: Log OBSERVATION_APPROVED event
    UI->>User: Update Patient Workspace Timeline
```

#### Step Details:
1. **Validation:** Checks MIME type, PDF/TXT extension, and 10MB file size ceiling.
2. **Page Mapping:** PyMuPDF segments text by individual page number (1-indexed) and preserves character offsets.
3. **LangChain Extraction:** A constrained prompt instructs Gemini to output a strict JSON array of observations with source snippets.
4. **Pydantic Validation:** `ExtractedObservation` validates that:
   - Dates are standardized to `YYYY-MM-DD` and not in the distant future.
   - Test codes are normalized to standard identifiers (`HBA1C`, `FBS`, `CHOL`, `TSH`, etc.).
   - Values with missing units or dates trigger `needs_review=True`.
5. **Human Review Gate:** Observations are staged in Db2 with `PENDING` status. The clinician reviews side-by-side with document excerpts and can edit values before approving.

---

### Pipeline B: Patient Intelligence & Evidence Q&A

```mermaid
sequenceDiagram
    autonumber
    actor User as Clinician / Reviewer
    participant UI as Ask MediTwin UI
    participant RS as Retrieval Service
    participant TS as Timeline Service
    participant DB as IBM Db2 Database
    participant AS as Answer Service (Gemini)
    participant AL as Audit Logger

    User->>UI: Submits question ("How did HbA1c change?")
    UI->>RS: Parse question & identify metric (e.g. HBA1C)
    RS->>DB: Query approved observations (WHERE review_status='APPROVED')
    DB-->>RS: Return ordered observation rows + file references
    alt Insufficient Records
        RS->>UI: Return mandated "insufficient approved records" message
    else Approved Records Found
        RS->>TS: Compute deterministic trend (first, latest, delta, pct)
        TS-->>AS: Supply trend summary & unit compatibility check
        RS-->>AS: Supply retrieved rows with source snippets & page numbers
        AS->>AS: Gemini synthesizes grounded explanation citing sources
        AS->>AS: Safety check verifies no diagnostic or prescriptive language
        AS->>UI: Render response with Answer + Evidence Cards + Sources
        UI->>AL: Log QUESTION_ASKED event
    end
```

#### Step Details:
1. **Query Template Selection:** Standard clinical aliases map natural phrasing to verified metrics (`HbA1c` -> `HBA1C`, `fasting sugar` -> `FBS`).
2. **Parameterized Retrieval:** `SELECT ... FROM OBSERVATION WHERE patient_id = ? AND test_code = ? AND review_status = 'APPROVED' ORDER BY observed_at ASC`.
3. **Deterministic Trend Calculation:** Calculates first recorded value, latest recorded value, absolute difference, and percentage delta. Verifies unit compatibility before calculating.
4. **Grounded Generation:** Gemini receives only retrieved database rows and computed metrics. It cannot query external knowledge to speculate on patient health.
5. **Evidence Display:** Every returned fact renders with an expandable evidence card displaying test name, value, unit, date, source file, page number, and original snippet.

---

## 4. LangGraph Workflow Architecture

MediTwin AI employs a unified, typed `StateGraph` with explicit conditional branching:

```mermaid
graph TD
    START([Start]) --> classify_request[1. classify_request]
    
    classify_request -->|Upload Request| parse_document[2. parse_document]
    classify_request -->|Question Request| retrieve_evidence[7. retrieve_evidence]
    classify_request -->|Unknown| finalize_response[10. finalize_response]
    
    parse_document -->|Parse Success| extract_observations[3. extract_observations]
    parse_document -->|Parse Failed| finalize_response
    
    extract_observations --> validate_extraction[4. validate_extraction]
    validate_extraction --> human_review_gate[5. human_review_gate]
    human_review_gate --> finalize_response
    
    retrieve_evidence --> generate_answer[8. generate_answer]
    generate_answer --> safety_check[9. safety_check]
    safety_check --> finalize_response
    
    finalize_response --> END_NODE([End])
```

State is managed by a typed `MediTwinState` model preserving complete execution context, intermediate payloads, validation flags, and audit traces.

---

## 5. IBM Db2 Database Schema Architecture

The relational schema is implemented in `db/schema.sql`:

```mermaid
erDiagram
    PATIENT ||--o{ DOCUMENT : "has"
    PATIENT ||--o{ OBSERVATION : "owns"
    PATIENT ||--o{ TIMELINE_EVENT : "experiences"
    DOCUMENT ||--o{ OBSERVATION : "contains"
    DOCUMENT ||--o{ TIMELINE_EVENT : "documents"

    PATIENT {
        INTEGER patient_id PK
        VARCHAR demo_code UK
        VARCHAR display_name
        INTEGER birth_year
        TIMESTAMP created_at
    }

    DOCUMENT {
        INTEGER document_id PK
        INTEGER patient_id FK
        VARCHAR file_name
        VARCHAR document_type
        CLOB extracted_text
        TIMESTAMP uploaded_at
        VARCHAR parse_status
        VARCHAR source_hash
    }

    OBSERVATION {
        INTEGER observation_id PK
        INTEGER patient_id FK
        INTEGER document_id FK
        VARCHAR test_code
        VARCHAR test_name
        DECIMAL value_numeric
        VARCHAR value_text
        VARCHAR unit
        DECIMAL reference_low
        DECIMAL reference_high
        DATE observed_at
        INTEGER source_page
        VARCHAR source_snippet
        DECIMAL extraction_confidence
        VARCHAR review_status
        VARCHAR reviewed_by
        TIMESTAMP reviewed_at
        TIMESTAMP created_at
    }

    TIMELINE_EVENT {
        INTEGER event_id PK
        INTEGER patient_id FK
        VARCHAR event_type
        TIMESTAMP event_time
        VARCHAR title
        VARCHAR summary
        INTEGER related_document_id FK
    }

    AUDIT_LOG {
        INTEGER audit_id PK
        VARCHAR actor_id
        VARCHAR action
        VARCHAR entity_type
        INTEGER entity_id
        CLOB details_json
        TIMESTAMP logged_at
    }
```

### Key Database Guarantees:
- **Foreign Key Cascades:** Deleting a synthetic test patient automatically purges dependent documents and observations.
- **Append-Only Audit Log:** `AUDIT_LOG` has no foreign key cascade and no update/delete procedures.
- **Check Constraints:** `review_status IN ('PENDING', 'APPROVED', 'REJECTED')`, `parse_status IN ('PENDING', 'PARSED', 'FAILED')`.
- **Prepared Execution:** All CRUD operations in `db/repository.py` use prepared statements with positional parameters (`?`).

---

## 6. Security, Compliance & Medical Safety

| Requirement | Implementation Detail |
|-------------|-----------------------|
| **Synthetic Data Only** | Strict use of artificial identifiers (`DEMO-001`, `DEMO-002`, `DEMO-003`). No PHI/PII stored. |
| **No Autonomous Diagnosis** | LLM temperature set to 0.1–0.2; prompt explicitly restricts output to reporting stored values. |
| **Safety Filter Node** | `safety_check` node inspects generated text for diagnostic or prescriptive keywords and appends mandatory disclaimers. |
| **Zero SQL Injection** | No SQL string concatenation. Repository uses prepared statements exclusively. |
| **Credential Protection** | Database credentials and API keys stored in `.env`; omitted from Git and prompts. |
| **Traceability** | 100% of approved observations link to source document, page, and snippet. |

