# ClaimGuard AI - System Architecture Specification

**Project:** ClaimGuard AI (`claimguard-ai`)  
**Hackathon:** IBM Db2Hack 2026 (Individual Submission)  
**Participant:** Nitesh Barnwal ([@Nitesh0517](https://github.com/Nitesh0517))  
**Core Stack:** IBM Db2 Enterprise (`ibm_db`), LangChain, LangGraph, Google Gemini 3.6 Flash, FastAPI, React 18, Tailwind CSS

---

## 1. Architectural Overview

ClaimGuard AI is an enterprise insurance claim verification and fraud detection platform. It couples IBM Db2 as an ACID-compliant system of record with an autonomous multi-agent AI pipeline built on LangChain and LangGraph.

The system enforces strict **Human-in-the-Loop (HITL)** governance: AI agents analyze multimodal hospital bills, verify policy coverage limits, detect duplicate document hashes, and synthesize transparent 0–100 risk scores. The output is purely advisory; only authorized human claim examiners have the authority to legally approve, adjust, or reject claims.

```mermaid
graph TD
    subgraph Client_Layer ["Client Layer (Presentation)"]
        UI["React 18 + Vite SPA"]
        Tailwind["IBM Carbon Design System"]
        AxiosClient["Axios API Client + JWT Interceptors"]
    end

    subgraph API_Gateway ["Application & API Gateway (FastAPI)"]
        FastAPIApp["FastAPI Application (Python 3.11+)"]
        AuthMiddleware["JWT Authentication & RBAC"]
        SecurityValidator["File Sanitizer & SHA-256 Hasher"]
        RouterClaims["Claims & Intake Router"]
        RouterVerify["LangGraph Orchestration Router"]
        RouterAudit["Audit & Fraud Investigation Router"]
    end

    subgraph Agentic_Layer ["Multi-Agent AI Engine (LangChain + LangGraph)"]
        SupervisorNode["Supervisor Agent (LangGraph StateGraph)"]
        DocAgent["Agent 1: Document Extraction Agent (Gemini 3.6 Flash)"]
        DbAgent["Agent 2: Database Verification Agent (Db2 Rules)"]
        FraudAgent["Agent 3: Fraud Detection Agent (Hash & Collisions)"]
        DecisionAgent["Agent 4: Decision Support Agent (Explainable Scoring)"]
    end

    subgraph Data_Layer ["Enterprise Relational Layer (IBM Db2)"]
        Db2Manager["Db2 Connection Manager (ibm_db 3.3.0)"]
        T_Customers[("CUSTOMER_DETAILS")]
        T_Policies[("POLICY_DETAILS")]
        T_Claims[("CLAIM_RECORDS")]
        T_Docs[("DOCUMENT_RECORDS")]
        T_Alerts[("FRAUD_ALERTS")]
        T_Logs[("VERIFICATION_LOGS")]
        T_Users[("USERS")]
    end

    UI -->|HTTP / JSON / JWT| FastAPIApp
    FastAPIApp --> AuthMiddleware
    AuthMiddleware --> RouterClaims
    AuthMiddleware --> RouterVerify
    AuthMiddleware --> RouterAudit
    RouterVerify --> SupervisorNode

    SupervisorNode --> DocAgent
    DocAgent --> DbAgent
    DbAgent --> FraudAgent
    FraudAgent --> DecisionAgent
    DecisionAgent --> SupervisorNode

    DbAgent -->|Parameterized SQL| Db2Manager
    FraudAgent -->|Collision Lookups| Db2Manager
    SupervisorNode -->|Audit Persistence| Db2Manager
    RouterClaims -->|ACID Transactions| Db2Manager

    Db2Manager --> T_Customers
    Db2Manager --> T_Policies
    Db2Manager --> T_Claims
    Db2Manager --> T_Docs
    Db2Manager --> T_Alerts
    Db2Manager --> T_Logs
    Db2Manager --> T_Users
```

---

## 2. Multi-Agent AI Architecture (LangGraph Workflow)

The agentic pipeline is built with **LangGraph** using a shared `ClaimGuardState` TypedDict. Each specialized agent executes sequentially, augmenting the state with typed outputs.

```mermaid
stateDiagram-v2
    [*] --> START
    START --> DocumentExtraction : Scanned Bill / Invoice Uploaded
    
    state DocumentExtraction {
        [*] --> CheckGeminiKey
        CheckGeminiKey --> LangChainGemini : Key Present & Valid
        CheckGeminiKey --> RegexFallback : Key Missing / Offline
        LangChainGemini --> ValidatePydantic : Structured JSON
        RegexFallback --> ValidatePydantic : Regex Output
        ValidatePydantic --> [*]
    }
    
    DocumentExtraction --> DatabaseVerification : Extracted Data & Claim ID
    
    state DatabaseVerification {
        [*] --> QueryCustomerDb2
        QueryCustomerDb2 --> QueryPolicyDb2
        QueryPolicyDb2 --> CheckActiveDates
        CheckActiveDates --> CheckCoverageLimit
        CheckCoverageLimit --> ComputeHistoricalExposure
        ComputeHistoricalExposure --> [*]
    }
    
    DatabaseVerification --> FraudDetection : Policy Data & Extraction
    
    state FraudDetection {
        [*] --> CheckSHA256Collisions
        CheckSHA256Collisions --> CheckInvoiceCollisions
        CheckInvoiceCollisions --> CheckDateAnomalies
        CheckDateAnomalies --> CheckAmountOutliers
        CheckAmountOutliers --> PersistFraudAlerts
        PersistFraudAlerts --> [*]
    }
    
    FraudDetection --> DecisionSupport : Aggregated Signal Vector
    
    state DecisionSupport {
        [*] --> CalculateWeightedRiskScore
        CalculateWeightedRiskScore --> DetermineRecommendation
        DetermineRecommendation --> GenerateExplainableSummary
        GenerateExplainableSummary --> AttachDisclaimer
        AttachDisclaimer --> [*]
    }
    
    DecisionSupport --> SupervisorFinalize : Recommendation & Risk Score
    
    state SupervisorFinalize {
        [*] --> UpdateClaimDb2
        UpdateClaimDb2 --> WriteImmutableAuditLogs
        WriteImmutableAuditLogs --> [*]
    }
    
    SupervisorFinalize --> END
    END --> [*] : Structured Report Available for Human Review
```

### Agent Responsibilities:

1. **Document Extraction Agent (`document_agent.py`):**
   - Utilizes `langchain_google_genai.ChatGoogleGenerativeAI` with `gemini-3.6-flash`.
   - Ingests raw document text or scanned medical invoices.
   - Extracts: `patient_name`, `patient_id`, `hospital_name`, `hospital_invoice_number`, `admission_date`, `discharge_date`, `diagnosis`, `diagnosis_code` (ICD-10), `total_amount`, `currency`.
   - Resilient Fallback: If Gemini API is unconfigured or rate-limited, automatically falls back to deterministic regex extraction to ensure 100% system availability.

2. **Database Verification Agent (`database_agent.py`):**
   - Queries IBM Db2 relational tables using parameterized SQL via `Db2ConnectionManager`.
   - Validates claimant profile against `CUSTOMER_DETAILS`.
   - Verifies policy validity period (`start_date <= incident_date <= end_date`) and status (`ACTIVE`).
   - Cross-checks claim amount against `REMAINING_COVERAGE` in `POLICY_DETAILS`.
   - Analyzes prior claim history and cumulative payout exposures.

3. **Fraud Detection Agent (`fraud_agent.py`):**
   - Computes SHA-256 cryptographic hashes for every uploaded file and checks for cross-claim hash collisions.
   - Identifies duplicate hospital invoice numbers across different claimants.
   - Detects date anomalies (e.g., discharge date preceding admission date or claims submitted for future dates).
   - Generates weighted `FRAUD_ALERTS` records with severity levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).

4. **Decision Support Agent (`decision_agent.py`):**
   - Combines signals from previous agents into a transparent **0–100 risk score**:
     $$\text{Risk Score} = \min\left(100.0, \sum w_i \times \text{signal}_i\right)$$
   - Classifies risk: `LOW` (0–25), `MEDIUM` (26–50), `HIGH` (51–75), `CRITICAL` (76–100).
   - Generates recommendations: `APPROVE`, `INVESTIGATE`, or `REJECT`.
   - Supplies an executive summary and itemized factor list.
   - Strictly attaches the mandatory Human-in-the-Loop disclaimer: *AI output is advisory only; final approval belongs to a licensed human claim examiner.*

5. **Supervisor Agent (`workflow.py`):**
   - Orchestrates the LangGraph state machine.
   - Handles node transitions, execution tracking, error boundary containment, and state reconciliation.
   - Records an immutable chronological execution entry in `VERIFICATION_LOGS` for each step.

---

## 3. IBM Db2 Relational Architecture & Schema

IBM Db2 serves as the ACID-compliant system of record. All schemas enforce strict referential integrity with foreign key cascading constraints and indexed lookup paths.

```mermaid
erDiagram
    CUSTOMER_DETAILS ||--o{ POLICY_DETAILS : "owns"
    CUSTOMER_DETAILS ||--o{ CLAIM_RECORDS : "files"
    POLICY_DETAILS ||--o{ CLAIM_RECORDS : "covers"
    CLAIM_RECORDS ||--o{ DOCUMENT_RECORDS : "contains"
    CLAIM_RECORDS ||--o{ FRAUD_ALERTS : "triggers"
    CLAIM_RECORDS ||--o{ VERIFICATION_LOGS : "logs"
    USERS ||--o{ CLAIM_RECORDS : "adjudicates"
    USERS ||--o{ FRAUD_ALERTS : "resolves"

    CUSTOMER_DETAILS {
        VARCHAR customer_id PK
        VARCHAR first_name
        VARCHAR last_name
        VARCHAR email UK
        VARCHAR phone
        DATE date_of_birth
        VARCHAR national_id UK
        VARCHAR address
        TIMESTAMP created_at
    }

    POLICY_DETAILS {
        VARCHAR policy_id PK
        VARCHAR customer_id FK
        VARCHAR policy_number UK
        VARCHAR policy_type
        VARCHAR status
        DATE start_date
        DATE end_date
        DECIMAL max_coverage_amount
        DECIMAL remaining_coverage
        DECIMAL deductible
        DECIMAL copay_percentage
        TIMESTAMP created_at
    }

    CLAIM_RECORDS {
        VARCHAR claim_id PK
        VARCHAR policy_id FK
        VARCHAR customer_id FK
        VARCHAR claim_number UK
        DATE incident_date
        DATE admission_date
        DATE discharge_date
        DECIMAL claim_amount
        DECIMAL approved_amount
        VARCHAR hospital_name
        VARCHAR hospital_invoice_number
        VARCHAR diagnosis_code
        VARCHAR diagnosis_description
        VARCHAR status
        DECIMAL risk_score
        VARCHAR risk_level
        CLOB decision_notes
        VARCHAR reviewed_by FK
        TIMESTAMP submitted_at
        TIMESTAMP updated_at
    }

    DOCUMENT_RECORDS {
        VARCHAR document_id PK
        VARCHAR claim_id FK
        VARCHAR document_name
        VARCHAR document_type
        VARCHAR file_path
        VARCHAR file_hash
        BIGINT file_size_bytes
        VARCHAR mime_type
        CLOB extracted_data
        TIMESTAMP uploaded_at
    }

    FRAUD_ALERTS {
        VARCHAR alert_id PK
        VARCHAR claim_id FK
        VARCHAR alert_type
        VARCHAR severity
        VARCHAR description
        CLOB evidence_details
        SMALLINT is_resolved
        VARCHAR resolved_by FK
        CLOB resolution_notes
        TIMESTAMP created_at
    }

    VERIFICATION_LOGS {
        VARCHAR log_id PK
        VARCHAR claim_id FK
        VARCHAR agent_name
        VARCHAR action
        VARCHAR status
        CLOB details
        INTEGER execution_time_ms
        TIMESTAMP created_at
    }

    USERS {
        VARCHAR user_id PK
        VARCHAR username UK
        VARCHAR email UK
        VARCHAR hashed_password
        VARCHAR full_name
        VARCHAR role
        SMALLINT is_active
        TIMESTAMP created_at
    }
```

### Database Performance & Security Indexing:
- `IDX_CLAIMS_POLICY`: B-Tree index on `CLAIM_RECORDS(POLICY_ID)` for instant historical lookups.
- `IDX_CLAIMS_CUSTOMER`: Index on `CLAIM_RECORDS(CUSTOMER_ID)`.
- `IDX_CLAIMS_STATUS`: Index on `CLAIM_RECORDS(STATUS)` for rapid queue filtering.
- `IDX_DOCUMENTS_HASH`: Index on `DOCUMENT_RECORDS(FILE_HASH)` for sub-millisecond duplicate document collision detection.
- `IDX_CLAIMS_INVOICE`: Index on `CLAIM_RECORDS(HOSPITAL_INVOICE_NUMBER)` to catch invoice reuse across different claimants.

---

## 4. Security & Compliance Architecture

1. **SQL Injection Defense:**
   - 100% of SQL executions against IBM Db2 utilize the native `ibm_db.prepare()` and `ibm_db.execute()` API with bound parameter tuples. Zero raw string interpolation or formatted query execution exists.
2. **Cryptographic Password Protection:**
   - Passwords for claims examiners and admins are hashed using **PBKDF2-HMAC-SHA256** with **600,000 iterations** and a 16-byte cryptographically secure salt (`os.urandom(16)`), compliant with NIST SP 800-132.
   - Verification uses constant-time comparison via `hmac.compare_digest` to prevent side-channel timing attacks.
3. **Session Authentication & Token Security:**
   - Stateless JWT tokens signed with HMAC-SHA256 (`HS256`).
   - Tokens include user ID (`sub`), role (`EXAMINER`, `ADMIN`), issued-at (`iat`), and expiration (`exp`) timestamps.
   - Expired or signature-tampered tokens return HTTP 401 Unauthorized immediately.
4. **File Upload Hardening:**
   - Whitelist enforcement: only `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, and `.txt` are permitted.
   - File size ceiling: strict 10 MB limit prevents denial-of-service memory exhaustion.
   - Path traversal prevention: filenames are sanitized using `os.path.basename()` before disk storage.
5. **Secrets & Environment Governance:**
   - Real credentials reside solely in runtime environment variables.
   - `.env` is strictly gitignored by default. `.env.example` contains non-functional dummy placeholders.

---

## 5. Human-in-the-Loop (HITL) Adjudication Flow

ClaimGuard AI enforces a strict distinction between AI intelligence and legal authority:

```mermaid
sequenceDiagram
    autonumber
    actor Claimant as Policyholder / Provider
    participant Frontend as React Dashboard
    participant Backend as FastAPI Backend
    participant Orchestrator as LangGraph Multi-Agent Engine
    participant Db2 as IBM Db2 Database
    actor Examiner as Licensed Human Examiner

    Claimant->>Frontend: Submits Claim & Uploads Hospital Invoice
    Frontend->>Backend: POST /api/claims & POST /api/claims/{id}/documents
    Backend->>Db2: INSERT into CLAIM_RECORDS & DOCUMENT_RECORDS
    Backend-->>Frontend: 201 Created (Claim ID: CLM-XXXX)

    Frontend->>Backend: POST /api/verification/{claim_id}
    Backend->>Orchestrator: run_claim_verification(claim_id)
    Orchestrator->>Db2: Query Policies, Historical Claims, Document Hashes
    Orchestrator->>Orchestrator: Document -> Database -> Fraud -> Decision Agents
    Orchestrator->>Db2: Persist FRAUD_ALERTS & VERIFICATION_LOGS
    Orchestrator-->>Backend: Final State (Risk Score, Advisory Recommendation)
    Backend-->>Frontend: Verification Complete (Status: success)

    Examiner->>Frontend: Reviews Claim Details, Extracted Bills & Fraud Alerts
    Note over Examiner,Frontend: Examiner reads AI advisory score & inspects physical bills
    Examiner->>Frontend: Submits Final Decision (APPROVED / REJECTED / INVESTIGATE)
    Frontend->>Backend: PUT /api/claims/{id}/decision (with Examiner JWT)
    Backend->>Db2: Atomic Transaction: Update STATUS & Deduct REMAINING_COVERAGE
    Backend-->>Frontend: 200 OK (Updated Claim & Remaining Balance)
```
