# MediTwin AI — IBM Db2 Database Schema Documentation

## 1. Overview

MediTwin AI uses **IBM Db2 Community Edition** as its authoritative, ACID-compliant relational system of record.
All database access is conducted through prepared SQL statements via the official `ibm_db` Python connector, guaranteeing defense against SQL injection.

---

## 2. Entity-Relationship Diagram

```
+-------------------+       1:N       +-------------------+
|      PATIENT      |----------------<|     DOCUMENT      |
+-------------------+                 +-------------------+
        |                                       |
        | 1:N                                   | 1:N
        v                                       v
+-------------------+       N:1       +-------------------+
|  TIMELINE_EVENT   |>----------------|    OBSERVATION    |
+-------------------+                 +-------------------+

+-------------------+
|     AUDIT_LOG     |   (Append-Only, Immutable)
+-------------------+
```

---

## 3. Table Definitions

### 3.1 PATIENT
Stores identity and basic demographic metadata for synthetic demonstration subjects.

| Column | Data Type | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|
| `patient_id` | `INTEGER` | No | Auto (IDENTITY) | `PK` | Synthetic patient unique surrogate key |
| `demo_code` | `VARCHAR(20)` | No | - | `UNIQUE` | Human-readable synthetic code (e.g. `DEMO-001`) |
| `display_name` | `VARCHAR(100)` | No | - | - | Synthetic full name |
| `birth_year` | `INTEGER` | Yes | - | - | Birth year (e.g. 1985) |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | - | Record creation timestamp |

---

### 3.2 DOCUMENT
Stores ingested medical documents, text bodies, and page maps.

| Column | Data Type | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|
| `document_id` | `INTEGER` | No | Auto (IDENTITY) | `PK` | Document unique surrogate key |
| `patient_id` | `INTEGER` | No | - | `FK -> PATIENT` | Patient owning this document |
| `file_name` | `VARCHAR(255)` | No | - | - | Original uploaded filename |
| `document_type`| `VARCHAR(50)` | No | `'LAB_REPORT'` | - | Category (LAB_REPORT, CLINICAL_NOTE, etc.) |
| `extracted_text`| `CLOB` | Yes | - | - | Complete extracted text content |
| `uploaded_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | - | Ingestion timestamp |
| `parse_status` | `VARCHAR(20)` | No | `'PENDING'` | `CHECK IN ('PENDING', 'PARSED', 'FAILED')` | Document parse state |
| `source_hash` | `VARCHAR(64)` | Yes | - | - | SHA-256 integrity hash of raw file bytes |

**Indexes:**
- `idx_document_patient` ON `DOCUMENT(patient_id)`
- `idx_document_status` ON `DOCUMENT(parse_status)`

---

### 3.3 OBSERVATION
Stores discrete extracted medical measurements and observations.

| Column | Data Type | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|
| `observation_id` | `INTEGER` | No | Auto (IDENTITY) | `PK` | Observation unique surrogate key |
| `patient_id` | `INTEGER` | No | - | `FK -> PATIENT` | Associated synthetic patient |
| `document_id` | `INTEGER` | No | - | `FK -> DOCUMENT` | Source document reference |
| `test_code` | `VARCHAR(50)` | Yes | - | - | Standard clinical abbreviation (HBA1C, FBS, etc.) |
| `test_name` | `VARCHAR(200)` | No | - | - | Full descriptive test name |
| `value_numeric`| `DECIMAL(12,4)`| Yes | - | - | Quantified numeric measurement |
| `value_text` | `VARCHAR(500)` | Yes | - | - | Qualitative/text observation when not numeric |
| `unit` | `VARCHAR(50)` | Yes | - | - | Measurement unit (%, mg/dL, mmol/L, etc.) |
| `reference_low`| `DECIMAL(12,4)`| Yes | - | - | Lower bound of source reference range |
| `reference_high`| `DECIMAL(12,4)`| Yes | - | - | Upper bound of source reference range |
| `observed_at` | `DATE` | Yes | - | - | Date observation was taken |
| `source_page` | `INTEGER` | Yes | - | - | Page number in source document (1-indexed) |
| `source_snippet`| `VARCHAR(500)` | Yes | - | - | Exact text excerpt from original report |
| `extraction_confidence`| `DECIMAL(3,2)`| Yes | - | - | Model extraction confidence (0.00 to 1.00) |
| `review_status`| `VARCHAR(20)` | No | `'PENDING'` | `CHECK IN ('PENDING', 'APPROVED', 'REJECTED')` | Verification state |
| `reviewed_by` | `VARCHAR(100)` | Yes | - | - | Reviewer user or role identifier |
| `reviewed_at` | `TIMESTAMP` | Yes | - | - | Review timestamp |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | - | Extraction ingestion timestamp |

**Indexes:**
- `idx_obs_patient` ON `OBSERVATION(patient_id)`
- `idx_obs_patient_test` ON `OBSERVATION(patient_id, test_code)`
- `idx_obs_review` ON `OBSERVATION(review_status)`
- `idx_obs_date` ON `OBSERVATION(observed_at)`

---

### 3.4 TIMELINE_EVENT
Stores notable chronological milestone markers across a patient's care journey.

| Column | Data Type | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|
| `event_id` | `INTEGER` | No | Auto (IDENTITY) | `PK` | Event unique surrogate key |
| `patient_id` | `INTEGER` | No | - | `FK -> PATIENT` | Associated synthetic patient |
| `event_type` | `VARCHAR(50)` | No | - | - | Category (LAB_PANEL, VISIT, DIAGNOSTIC) |
| `event_time` | `TIMESTAMP` | No | - | - | Timestamp of event occurrence |
| `title` | `VARCHAR(200)` | No | - | - | Short headline description |
| `summary` | `VARCHAR(1000)`| Yes | - | - | Narrative synopsis |
| `related_document_id`| `INTEGER` | Yes | - | `FK -> DOCUMENT` | Linked document if applicable |

**Indexes:**
- `idx_timeline_patient` ON `TIMELINE_EVENT(patient_id)`
- `idx_timeline_time` ON `TIMELINE_EVENT(event_time)`

---

### 3.5 AUDIT_LOG
An immutable, append-only log capturing critical platform operations for regulatory compliance.

| Column | Data Type | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|
| `audit_id` | `INTEGER` | No | Auto (IDENTITY) | `PK` | Audit entry surrogate key |
| `actor_id` | `VARCHAR(100)` | No | `'SYSTEM'` | - | User, reviewer, or system process identifier |
| `action` | `VARCHAR(50)` | No | - | - | Event type (`DOCUMENT_UPLOAD`, `OBSERVATION_APPROVED`, etc.) |
| `entity_type` | `VARCHAR(50)` | No | - | - | Affected entity (`PATIENT`, `DOCUMENT`, `OBSERVATION`) |
| `entity_id` | `INTEGER` | Yes | - | - | Primary key ID of affected record |
| `details_json`| `CLOB` | Yes | - | - | JSON serialized context payload |
| `logged_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | - | Unmodifiable server timestamp |

**Indexes:**
- `idx_audit_time` ON `AUDIT_LOG(logged_at)`
- `idx_audit_entity` ON `AUDIT_LOG(entity_type, entity_id)`

---

## 4. Query Security & Transaction Management

- **Transaction Scope:** Inserting documents, extracting observations, and updating review decisions are executed within explicit `transaction()` blocks. Errors trigger an immediate `ibm_db.rollback()`.
- **Prepared Statements:** All parameter substitutions utilize positional binding:
  ```python
  stmt = ibm_db.prepare(conn, "SELECT * FROM OBSERVATION WHERE patient_id = ? AND test_code = ?")
  ibm_db.bind_param(stmt, 1, patient_id)
  ibm_db.bind_param(stmt, 2, test_code)
  ibm_db.execute(stmt)
  ```
- **Zero Raw Dynamic SQL:** The LLM has zero direct SQL execution rights. Queries are strictly dispatched via repository methods.

