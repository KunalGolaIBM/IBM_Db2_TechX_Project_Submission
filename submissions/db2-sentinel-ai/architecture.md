# System Architecture — Db2 Sentinel AI

## Overview

**Db2 Sentinel AI** is an enterprise-grade autonomous surveillance and regulatory compliance platform engineered for mission-critical banking environments. The architecture bridges modern **Cyclical Multi-Agent State Machines (LangGraph)** with **IBM Db2 12.1+ Enterprise Database capabilities**, including native vector similarity search (`VECTOR` data types and `VECTOR_DISTANCE`), Common Table Expressions (`WITH RECURSIVE`), analytical window functions, ACID-compliant agent state checkpointing, and immutable cryptographic audit logging.

---

## Architecture Diagrams

### 1. High-Level System Architecture

```mermaid
graph TD
    Client["Enterprise Compliance Dashboard (Streamlit / REST API)"]
    
    subgraph "Application & Agent Orchestration Layer"
        Runner["Sentinel Execution Engine"]
        Checkpointer["Db2 State Checkpointer"]
        
        subgraph "LangGraph State Machine"
            Screening["1. ScreeningAgent<br>(Sanctions & Threshold Rules)"]
            Investigator["2. ForensicInvestigatorAgent<br>(Vector Search & Account Histories)"]
            GraphRisk["3. GraphRiskAgent<br>(Recursive CTE Circular Flow)"]
            SARDrafter["4. SARDrafterAgent<br>(FinCEN / RBI Compliant Filings)"]
            Supervisor["5. SupervisorAgent<br>(Human-in-the-Loop & Freeze Execution)"]
        end
    end
    
    subgraph "Database & Storage Layer (IBM Db2 12.1+)"
        RelationalTables[("ACCOUNTS<br>TRANSACTIONS<br>SANCTIONS_WATCHLIST")]
        VectorStore[("AML_TYPOLOGIES<br>VECTOR(384, FLOAT32)<br>VECTOR_DISTANCE(COSINE)")]
        StatePersistence[("AGENT_CHECKPOINTS<br>(Thread Snapshots & State Blobs)")]
        AuditLedger[("AUDIT_TRAIL<br>SAR_FILINGS<br>(SHA-256 Signed Records)")]
    end

    Client -->|Trigger / Review Case| Runner
    Runner -->|Orchestrate| Screening
    Screening -->|Next Node| Investigator
    Investigator -->|Next Node| GraphRisk
    GraphRisk -->|Next Node| SARDrafter
    SARDrafter -->|Next Node| Supervisor
    Supervisor -->|Approval & Actions| Client

    Screening -.->|Screen against Watchlist| RelationalTables
    Investigator -.->|Native Vector Search| VectorStore
    Investigator -.->|Window Velocity Queries| RelationalTables
    GraphRisk -.->|Recursive CTE Loop Search| RelationalTables
    Supervisor -.->|Execute Account Freeze| RelationalTables
    Supervisor -.->|Commit Signed SAR Filing| AuditLedger
    
    Checkpointer <-->|Persist & Resume State| StatePersistence
    LangGraph -.->|Checkpoint at each step| Checkpointer
```

---

### 2. LangGraph Multi-Agent State Machine Flow

```mermaid
stateDiagram-v2
    [*] --> START
    START --> ScreeningNode: Intercept Transaction
    
    state ScreeningNode {
        [*] --> CheckSanctionsWatchlist
        CheckSanctionsWatchlist --> CheckStructuringThreshold
        CheckStructuringThreshold --> ComputeBaselineScore
    }
    
    ScreeningNode --> InvestigatorNode: Pass State & Flags
    
    state InvestigatorNode {
        [*] --> EmbedTransactionMemo
        EmbedTransactionMemo --> Db2VectorSearch: VECTOR_DISTANCE(EMBEDDING, 'COSINE')
        Db2VectorSearch --> Db2WindowAggregations: Historical Burst Velocity
        Db2WindowAggregations --> MatchTypologies
    }
    
    InvestigatorNode --> GraphRiskNode: Pass Typology Matches
    
    state GraphRiskNode {
        [*] --> ExecuteRecursiveCTE: WITH RECURSIVE TransferPaths
        ExecuteRecursiveCTE --> DetectClosedCycles: A -> B -> C -> A
        DetectClosedCycles --> AssessNetworkExposure
    }
    
    GraphRiskNode --> SARDrafterNode: Pass Network Topology
    
    state SARDrafterNode {
        [*] --> EvaluateRiskThreshold: Score >= 65?
        EvaluateRiskThreshold --> DraftFormalSAR: Yes (FinCEN / RBI Standard)
        EvaluateRiskThreshold --> ClearCase: No (Routine Clearance)
    }
    
    SARDrafterNode --> SupervisorNode: Pass Drafted Filing & Disposition
    
    state SupervisorNode {
        [*] --> ReviewRecommendedAction
        ReviewRecommendedAction --> ExecuteDb2Freeze: FREEZE_AND_FILE_SAR
        ExecuteDb2Freeze --> StoreSARFilingInDb2
        StoreSARFilingInDb2 --> SignCryptographicAuditTrail: SHA-256 Hash
    }
    
    SupervisorNode --> END: Complete Case Lifecycle
    END --> [*]
```

---

### 3. IBM Db2 Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    ACCOUNTS ||--o{ TRANSACTIONS : "sends (SENDER_ID)"
    ACCOUNTS ||--o{ TRANSACTIONS : "receives (RECEIVER_ID)"
    TRANSACTIONS ||--o| INVESTIGATION_ALERTS : "triggers (TX_ID)"
    INVESTIGATION_ALERTS ||--o| SAR_FILINGS : "results in (ALERT_ID)"
    
    ACCOUNTS {
        varchar(32) ACCOUNT_ID PK
        varchar(128) CUSTOMER_NAME
        varchar(32) ACCOUNT_TYPE
        varchar(64) JURISDICTION
        decimal(18-2) BALANCE
        varchar(16) RISK_RATING
        varchar(16) STATUS
        integer KYC_VERIFIED
        timestamp CREATED_AT
    }
    
    TRANSACTIONS {
        varchar(32) TX_ID PK
        varchar(32) SENDER_ID FK
        varchar(32) RECEIVER_ID FK
        decimal(18-2) AMOUNT
        varchar(8) CURRENCY
        varchar(32) CHANNEL
        timestamp TX_TIMESTAMP
        varchar(512) MEMO
        integer FLAG_ANOMALY
        vector(384) EMBEDDING
    }
    
    SANCTIONS_WATCHLIST {
        varchar(32) ENTITY_ID PK
        varchar(128) NAME
        varchar(256) ALIASES
        varchar(64) COUNTRY
        varchar(64) CATEGORY
        varchar(16) RISK_LEVEL
    }
    
    AML_TYPOLOGIES {
        varchar(32) TYPOLOGY_ID PK
        varchar(32) CODE
        varchar(128) TITLE
        clob DESCRIPTION
        varchar(64) CATEGORY
        clob RED_FLAGS
        vector(384) EMBEDDING
    }
    
    INVESTIGATION_ALERTS {
        varchar(32) ALERT_ID PK
        varchar(32) TX_ID FK
        integer RISK_SCORE
        varchar(128) RULE_TRIGGERED
        varchar(32) STATUS
        timestamp CREATED_AT
    }
    
    AGENT_CHECKPOINTS {
        integer CHECKPOINT_ID PK
        varchar(64) THREAD_ID
        integer STEP_NUM
        varchar(64) AGENT_NAME
        clob STATE_JSON
        timestamp CREATED_AT
    }
    
    AUDIT_TRAIL {
        integer AUDIT_ID PK
        timestamp CREATED_AT
        varchar(64) ACTOR
        varchar(64) ACTION
        clob DETAILS
        varchar(64) SIGNATURE_HASH
    }
    
    SAR_FILINGS {
        varchar(32) SAR_ID PK
        varchar(32) ALERT_ID FK
        varchar(64) FILING_REFERENCE
        varchar(128) PRIMARY_SUSPECT
        clob NARRATIVE_CLOB
        integer RISK_SCORE
        varchar(64) FILED_BY
        varchar(32) STATUS
        timestamp CREATED_AT
    }
```

---

## Component Breakdown

### 1. User Interface & Presentation Layer
- **Streamlit Enterprise Application** (`src/app.py`):
  - **Transaction Feed & Alerts**: Real-time tabular monitoring of wires with risk heatmaps.
  - **Multi-Agent Canvas**: Visual trace of agent thoughts, steps, and tool execution.
  - **Network Topology Graph**: Interactive network graph (`NetworkX`) visualizing circular routing loops and mule account clusters.
  - **SAR Studio & Audit Viewer**: Regulatory narrative viewer with one-click Markdown/PDF exports and immutable SHA-256 audit logs.
  - **Text-to-SQL Studio**: Natural language to SQL exploration over live Db2 tables.

### 2. Application Backend Layer
- **Db2 Connection Layer** (`src/db/connection.py`):
  - Dual-mode connection management supporting live **IBM Db2 12.1+** via native `ibm_db` and SQLAlchemy `ibm_db_sa`.
  - Automatic zero-setup local emulation engine for instant hackathon evaluation without requiring a 4GB Docker container.
- **Analytical Query Engine** (`src/db/queries.py`):
  - Db2 window aggregation for velocity anomaly scoring.
  - Recursive Common Table Expressions (CTEs) for multi-hop graph path and cycle discovery.
  - Vector similarity search via `VECTOR_DISTANCE`.

### 3. Database Layer (IBM Db2 12.1+)
- **Relational Consistency**: Strict foreign key constraints and transactional integrity (`ACID`).
- **Vector Storage**: Dedicated `VECTOR(384, FLOAT32)` columns on transaction memos and FATF AML crime typologies.
- **Agent State Persistence**: `AGENT_CHECKPOINTS` table storing serialized state snapshots at each agent transition.
- **Tamper-Evident Audit Ledger**: `AUDIT_TRAIL` table persisting every agent action, tool invocation, and decision signed with SHA-256 cryptographic hashes.

### 4. AI & Multi-Agent Orchestration Layer
- **LangGraph State Graph** (`src/agents/workflow.py`):
  - Five specialized agent nodes coordinated with cyclical state transitions.
  - Checkpoint persistence backed directly by IBM Db2.
- **Embedding Pipeline** (`src/utils/embeddings.py`):
  - Generates 384-dimensional dense semantic vectors compatible with IBM Granite embedding models (`ibm-granite/granite-embedding-311m-multilingual-r2`) and SentenceTransformers.

---

## Data Flow

```text
1. Transaction Arrival  ──> 2. Screening Check   ──> 3. Forensic Db2 Vector Query
                                                            │
                                                            ▼
6. Regulatory SAR Filing <── 5. Supervisor Sign-off <── 4. Recursive CTE Cycle Detection
```

1. **Transaction Interception**: Inbound wire transaction is received and logged into Db2 `TRANSACTIONS`.
2. **Rule Screening (`ScreeningAgent`)**: Evaluates transaction amounts against sub-threshold structuring limits ($9,000–$9,999) and screens party names against `SANCTIONS_WATCHLIST`.
3. **Forensic Vector Analysis (`ForensicInvestigatorAgent`)**: Computes dense vector representation of transaction memo; runs in-database Db2 `VECTOR_DISTANCE` against `AML_TYPOLOGIES`. Gathers rolling historical velocity via Db2 window functions.
4. **Network Cycle Detection (`GraphRiskAgent`)**: Executes recursive SQL CTEs to trace fund paths across counterparties and detect circular routing loops (A &rarr; B &rarr; C &rarr; A).
5. **SAR Compilation (`SARDrafterAgent`)**: Synthesizes forensic findings into a standardized 5-part FinCEN/RBI Suspicious Activity Report with citations to Db2 record IDs.
6. **Supervisor Enforcement (`SupervisorAgent`)**: Authorizes emergency account freezing in Db2, persists the formal SAR filing, and seals the record with a SHA-256 cryptographic signature in `AUDIT_TRAIL`.

---

## Security & Secrets Management
- **Zero Committed Credentials**: All production connection strings and API keys are read at runtime via environment variables (`.env`).
- **Input Sanitization**: All database interactions use parameterized SQL statements (`?` placeholders) to prevent SQL injection attacks.
- **Cryptographic Auditability**: Every state transition and regulatory action computes an immutable SHA-256 hash across the actor, timestamp, and payload.
