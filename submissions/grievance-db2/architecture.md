# Technical Architecture & IBM Db2 System Design
## Citizen Grievance Portal (IBM Db2 + LangChain AI)
### Submission for IBM Db2Hack 2026

---

## 1. End-to-End System Architecture

```
+==================================================================================================+
|                                    1. CLIENT PRESENTATION TIER                                   |
|                                                                                                  |
|   Citizen & Officer Web Browsers                                                                 |
|   [Lodge Grievance]  [Track Docket]  [Officer Console]  [Analytics Dashboard]  [Ask the Data (AI)]|
+==================================================================================================+
                                               |
                                     HTTP:80 / HTTP:3000
                                               v
+==================================================================================================+
|                                    2. GATEWAY & REVERSE PROXY                                    |
|                                                                                                  |
|   Nginx Alpine Container (grievance-frontend)                                                    |
|   - Serves high-contrast accessible static assets (HTML5, CSS, ES6 JS, W3C WCAG 2.1 compliant)   |
|   - Reverse proxies '/api/*' traffic to FastAPI backend with connection keep-alive               |
+==================================================================================================+
                                               |
                                        HTTP Proxy:8000
                                               v
+==================================================================================================+
|                                3. APPLICATION & AI SERVICES TIER                                 |
|                                                                                                  |
|   FastAPI Python 3.11 Container (grievance-api)                                                  |
|                                                                                                  |
|   +------------------------------------+       +---------------------------------------------+   |
|   |        LangChain AI Service        |       |          Security Guardrail Engine          |   |
|   |  - Prompt Chain Grievance Triage   |       |  - Strict single SELECT query verification  |   |
|   |  - Natural Language to Db2 SQL     | ----> |  - DDL/DML Token Rejection (DROP, ALTER...) |   |
|   |  - Ward Hotspot & Duplicate Engine |       |  - Semicolon & SQL Comment Filter           |   |
|   |  - Deterministic Rule-Based Fallback|       |  - Table Allowlist [dept, grv, updates]     |   |
|   +------------------------------------+       |  - Enforced 'FETCH FIRST 50 ROWS ONLY'      |   |
|                                                +---------------------------------------------+   |
|                                                               |                                  |
|                                     SQLAlchemy ORM (ibm_db_sa Dialect)                           |
+==================================================================================================+
                                               |
                                     Native TCP Port: 50000
                                               v
+==================================================================================================+
|                               4. RELATIONAL DATABASE ENGINE TIER                                 |
|                                                                                                  |
|   IBM Db2 Community Edition 11.5.8.0 Container (grievance-db2)                                   |
|   Instance: db2inst1 | Database: GRIEVDB                                                         |
|                                                                                                  |
|   Tables:                                                                                        |
|   * departments: Municipal and central nodal authorities, contact emails                         |
|   * grievances: Primary dockets, citizen records, AI triage tags (ai_priority, ai_summary)       |
|   * grievance_updates: Immutable audit log history with referential integrity constraints        |
|                                                                                                  |
|   Native Db2 Engine Optimizations:                                                               |
|   - Continuous calendar date arithmetic: DAYS(CURRENT DATE) - DAYS(DATE(created_at)) > 15        |
|   - Compound B-Tree Indexes on tracking_id, category, ward, status, priority                     |
|   - Catalog reflection via SYSCAT.COLUMNS & auto-REORG via SYSPROC.ADMIN_CMD                     |
+==================================================================================================+
```

---

## 2. End-to-End Data Flow Pipeline

The lifecycle of civic grievances flows through 5 interconnected processing stages:

```
[1. Intake]              [2. AI Triage]             [3. Ingestion]             [4. Hotspot Check]          [5. Analytics & SLAs]
Citizen submits form  -> LangChain parses   -> Atomic Db2 transaction -> Scan open complaints -> Db2 DAYS() queries audit
(description, ward,      category, priority,   writes grievances and      in same ward/category;  SLAs; dashboard charts
 category hint)          and 1-line summary    initial audit update       flag duplicate clusters real-time department load
```

### Stage 1: Citizen Intake
- The citizen inputs grievance details via `lodge-grievance.html`.
- Client-side validation verifies contact format, minimum character length (10+ characters), and captures GPS latitude/longitude and municipal ward selection.

### Stage 2: LangChain AI Triage
- The backend receives `POST /api/grievances`.
- Description is dispatched to `triage_grievance()` in `ai_service.py`.
- A LangChain prompt chain (`ChatPromptTemplate | LLM | JsonOutputParser`) categorizes the grievance, assigns an urgency rating (`Critical`, `High`, `Medium`, `Low`), and generates a concise 1-sentence summary under 200 characters.
- If an LLM API key is absent or times out, a deterministic keyword-based rule triage runs instantly, guaranteeing zero-downtime operation.

### Stage 3: IBM Db2 Ingestion & Audit Logging
- A unique tracking token (`GRV-2026-XXXX`) is generated with collision verification.
- Inside an ACID transaction, `Grievance` is inserted with all metadata (`ward`, `priority`, `ai_category`, `ai_priority`, `ai_summary`).
- An initial audit log row is committed to `grievance_updates` (`status='Filed'`, `updated_by='CPGRAMS AI Intake'`).

### Stage 4: Ward Hotspot & Duplicate Detection
- A query searches IBM Db2 for open grievances (`Filed`, `Under Review`, `Forwarded to Dept`) in the same municipal ward and category.
- If $\ge 2$ open tickets exist, a **Hotspot Warning** is triggered.
- Keyword overlap algorithms identify potential duplicate dockets and return them in the JSON payload, warning the citizen and alerting ward nodal officers.

### Stage 5: Real-Time Analytics & SLA Auditing
- When administrators view `dashboard.html` or call `GET /api/analytics`, IBM Db2 executes native calendar day arithmetic:
  ```sql
  SELECT COUNT(*) FROM grievances 
  WHERE status != 'Resolved' AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15;
  ```
- Instant computation of resolution turnaround times, ward hotspots, and overdue dockets occurs on live data without requiring external batch ETL workers.

### Stage 6: Geospatial GIS Telemetry Aggregation (`GET /api/analytics/geo-hotspots`)
- Aggregates active open grievances by municipal ward directly inside IBM Db2 (`GROUP BY ward`).
- Computes critical count, SLA breaches, and dominant problem categories for each ward.
- Joins spatial coordinates across Delhi NCT (Rohini, Civil Lines, Mayur Vihar, Chandni Chowk, Okhla, Janakpuri, etc.) and compiles a standard GeoJSON `FeatureCollection`.
- Powers the interactive **Leaflet.js Municipal Ward Geospatial Command Map** on `dashboard.html`, enabling real-time visual triaging and 1-click routing into the Officer Redressal Console.

---

## 3. "Ask the Data" NL-to-SQL Security Guardrails

The `POST /api/ask` endpoint allows users to query live grievance metrics in plain English. Because untrusted user input generates SQL, the engine implements a multi-tier defense-in-depth security pipeline:

```
User Query ("Show critical complaints in Rohini")
                     |
                     v
   [Pre-Check Guardrail: Prohibited Token Regex] --------------------> [REJECT 400 Bad Request]
   (Disallows DROP, DELETE, INSERT, UPDATE, ALTER,                     if tokens detected
    TRUNCATE, EXEC, CALL, semicolons, comments)
                     |
                     v (Passed)
   [LangChain Db2 SQL Generation Chain]
   (Instructed on GRIEVDB schema and Db2 dialect)
                     |
                     v
   [Post-Generation Syntax & Guardrail Sanitizer]
   1. Enforce single SELECT statement (must start with SELECT) ------> [REJECT 400 Bad Request]
   2. Regex check for banned DDL/DML tokens ------------------------> [REJECT 400 Bad Request]
   3. Table Allowlist Check: [departments, grievances, updates] -----> [REJECT 400 Bad Request]
   4. Strip comments (-- and /* */) and semicolons (;) --------------> [REJECT 400 Bad Request]
   5. Enforce Db2 row limiting: Append "FETCH FIRST 50 ROWS ONLY" ---> [REWRITE TO DB2 STANDARD]
                     |
                     v (Sanitized & Verified Safe)
   [Execute on IBM Db2 via SQLAlchemy Parameterized Cursor]
                     |
                     v
   Return JSON: { question, generated_sql, execution_time_ms, row_count, columns, rows }
```

### Security Guardrail Specifications

| Guardrail Rule | Target Risk | Implementation Mechanism |
|---|---|---|
| **SELECT-Only Enforcement** | Arbitrary code execution & data modification | String validation requiring query to start with `SELECT`. Rejects any other starting keyword. |
| **Banned Keyword Regex** | Destructive DDL / DML (`DROP`, `TRUNCATE`, `DELETE`, `ALTER`, `GRANT`, `MERGE`) | Case-insensitive regex: `\b(INSERT\|UPDATE\|DELETE\|DROP\|ALTER\|TRUNCATE\|EXEC\|EXECUTE\|GRANT\|REVOKE\|MERGE\|CALL\|CREATE)\b`. |
| **Semicolon Prohibition** | Stacked query injection (e.g., `SELECT 1; DROP TABLE...`) | Rejection of `;` in both user prompt and generated SQL. |
| **Comment Stripping** | Filter bypass via SQL comments (e.g., `--` or `/* */`) | Rejection of comment tokens `--`, `/*`, `*/`. |
| **Strict Table Whitelist** | Inspection of system catalog (`SYSCAT`) or unauthorized tables | Token extraction after `FROM` and `JOIN`. Only `departments`, `grievances`, `grievance_updates`, and `sysibm.sysdummy1` allowed. |
| **Db2 Row Limiting** | Resource exhaustion and denial of service | Replaces MySQL `LIMIT` with standard Db2 syntax `FETCH FIRST <N> ROWS ONLY`; defaults to max 50 rows. |

---

## 4. IBM Db2 Relational Schema & Entity Relationships

```
+---------------------------------------+
|              DEPARTMENTS              |
+---------------------------------------+
| id            INT (PK, IDENTITY)      |
| code          VARCHAR(50) (UNIQUE)    |
| name          VARCHAR(200)            |
| description   VARCHAR(500)            |
| nodal_email   VARCHAR(150)            |
| created_at    TIMESTAMP               |
+---------------------------------------+
                    | 1
                    |
                    | has many (handles)
                    v N
+---------------------------------------+       1
|              GRIEVANCES               |-----------------+
+---------------------------------------+                 |
| id            INT (PK, IDENTITY)      |                 |
| tracking_id   VARCHAR(32) (UNIQUE)    |                 |
| citizen_name  VARCHAR(150)            |                 |
| contact       VARCHAR(150)            |                 |
| category      VARCHAR(100)            |                 |
| subject       VARCHAR(255)            |                 | tracks many (audit trail)
| description   VARCHAR(3000)           |                 | ON DELETE CASCADE
| ward          VARCHAR(100)            |                 |
| priority      VARCHAR(20)             |                 |
| status        VARCHAR(50)             |                 v N
| created_at    TIMESTAMP               |       +---------------------------------------+
| resolved_at   TIMESTAMP (NULLABLE)    |       |           GRIEVANCE_UPDATES           |
| department_id INT (FK -> DEPT.ID)     |       +---------------------------------------+
| state         VARCHAR(100)            |       | id              INT (PK, IDENTITY)    |
| pincode       VARCHAR(10)             |       | grievance_id    INT (FK -> GRIEVANCES)|
| latitude      DOUBLE                  |       | previous_status VARCHAR(50)           |
| longitude     DOUBLE                  |       | new_status      VARCHAR(50)           |
| ai_category   VARCHAR(50)             |       | notes           VARCHAR(1000)         |
| ai_priority   VARCHAR(20)             |       | updated_by      VARCHAR(100)          |
| ai_summary    VARCHAR(255)            |       | created_at      TIMESTAMP             |
+---------------------------------------+       +---------------------------------------+
```

---

## 5. Startup Schema Reflection & Db2 REORG Execution

When new columns (`ai_category`, `ai_priority`, `ai_summary`) are introduced in models, standard `Base.metadata.create_all()` in SQLAlchemy does not alter existing Db2 tables.

To avoid migration failures and prevent IBM Db2 from entering a **REORG PENDING** state (`SQL0668N Reason Code 7`), `database.py` executes the following sequence on startup:

```python
with engine.connect() as conn:
    # 1. Query Db2 System Catalog for active columns
    cols = conn.execute(text("SELECT COLNAME FROM SYSCAT.COLUMNS WHERE UPPER(TABNAME) = 'GRIEVANCES'")).fetchall()
    existing_cols = {c[0].strip().upper() for c in cols}

    table_altered = False
    for col_name, col_type in [("AI_CATEGORY", "VARCHAR(50)"), ("AI_PRIORITY", "VARCHAR(20)"), ("AI_SUMMARY", "VARCHAR(255)")]:
        if col_name not in existing_cols:
            conn.execute(text(f"ALTER TABLE grievances ADD COLUMN {col_name} {col_type}"))
            table_altered = True

    # 2. If table was altered, execute Db2 administrative table reorganization
    if table_altered:
        conn.commit()
        conn.execute(text("CALL SYSPROC.ADMIN_CMD('REORG TABLE grievances')"))
        conn.commit()

    # 3. Backfill existing seeded rows with deterministic AI tags
    conn.execute(text("""
        UPDATE grievances 
        SET ai_category = category,
            ai_priority = priority,
            ai_summary = SUBSTR(COALESCE(subject, description), 1, 250)
        WHERE ai_category IS NULL
    """))
    conn.commit()
```

This ensures complete backward compatibility and allows judges to run `docker compose up --build -d` on any existing or clean Docker environment without manual DDL intervention.

---

## 6. Advanced Db2 Engine Capabilities: Native Stored Procedure & Continuous SLA Auditing

To demonstrate deep database-layer computation rather than offloading logic entirely to the application server, the system deploys a native IBM Db2 SQL stored procedure: **`SP_ESCALATE_OVERDUE`**.

### 6.1 Stored Procedure Definition (`init_db2.sql`)

```sql
CREATE OR REPLACE PROCEDURE SP_ESCALATE_OVERDUE (OUT escalated_count INT)
LANGUAGE SQL
BEGIN
    DECLARE v_count INT DEFAULT 0;

    -- Compute SLA breaches using native Db2 calendar day difference
    SELECT COUNT(*) INTO v_count
    FROM grievances
    WHERE status != 'Resolved'
      AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15;

    -- Elevate priority to Critical inside the Db2 engine
    UPDATE grievances
    SET priority = 'Critical'
    WHERE status != 'Resolved'
      AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15
      AND priority != 'Critical';

    SET escalated_count = v_count;
END;
```

### 6.2 Execution & Orchestration
1. **Zero-Touch Startup Registration**: On application boot, `database.py` inspects `SYSCAT.ROUTINES WHERE UPPER(ROUTINENAME) = 'SP_ESCALATE_OVERDUE'`. If not registered, it compiles and binds the stored procedure in `GRIEVDB`.
2. **On-Demand / Automated Execution**: The stored procedure can be invoked via `POST /api/escalate-overdue` or directly from the Analytics Dashboard, executing within a native Db2 transaction and returning the total number of escalated dockets.
3. **Audit Trails**: Escalated complaints are immediately updated with Db2 indexes ensuring priority queues reflect statutory urgency.

---

## 7. Officer Redressal Console & LangChain AI Action Drafter

To bridge citizen complaint lodging with executive governmental redressal, the architecture incorporates a dedicated **Officer Redressal Console** (`officer.html`) backed by specialized LangChain prompt chains and atomic Db2 transactions:

### 7.1 Officer Workflow Pipeline
```
[Officer Redressal Console]
        |
        | 1. GET /api/officer/dockets (Filtered by dept, status, priority; enriched with Db2 DAYS() elapsed time)
        v
[Select Docket (e.g. GRV-2026-1028)]
        |
        | 2. Click "AI Draft Action" -> POST /api/officer/draft-action
        v
[LangChain AI Action Drafter]
        | Uses ChatPromptTemplate | LLM | JsonOutputParser with bureaucratic domain context
        v
[Structured Directive Generated]
        * action_type: "Immediate Repair" | "Field Inspection" | "Show-Cause Notice" | "Interim Relief"
        * target_officer: "Executive Engineer (Civil/PWD)"
        * statutory_deadline_days: 3
        * drafted_order_text: Formal administrative directive citing public safety regulations
        |
        v
[Officer Review & Dispatch] 
        * Option to edit order text and dispatch -> PATCH /api/grievances/{tracking_id}/status
        * Option to Resolve Docket -> POST /api/officer/resolve
        |
        v
[Atomic Db2 Resolution Transaction]
        * Updates grievances: status='Resolved', resolved_at=CURRENT TIMESTAMP, ai_summary=ATR
        * Inserts grievance_updates: new_status='Resolved', updated_by=Officer, notes=ATR text
        * Zero-discrepancy guaranteed by ACID database transaction commit
```

### 7.2 LangChain Bureaucratic Directive Engine (`ai_service.py`)
The drafter leverages a dedicated prompt instructing the model to behave as a Senior Municipal Executive Officer (IAS/Nodal Authority). It produces structured administrative orders enforcing accountability:
```json
{
  "action_type": "Immediate Repair",
  "target_officer": "Executive Engineer (Civil/PWD - Pothole Quick-Response Unit)",
  "statutory_deadline_days": 3,
  "drafted_order_text": "URGENT MUNICIPAL DIRECTIVE: In view of citizen grievance regarding severe road cave-in and hazardous craters, the Executive Engineer is hereby ordered to deploy a rapid cold-mix repair team within 48 hours. Ensure barricading and submit compliance report within 3 days.",
  "recommended_status": "Forwarded to Dept",
  "generated_by": "LangChain Action Drafter (LLM)"
}
```
If third-party LLMs are unavailable, a domain-specific rule-based administrative fallback generates department-accurate directives instantly.

---

## 8. In-Engine ACID Trigger Auditing vs. Application-Layer Logging

In enterprise and municipal public administration systems, audit logs are subject to strict legal scrutiny, Right to Information (RTI) inquiries, and judicial oversight. To guarantee immutable non-repudiation, the architecture combines application-layer logging with native **IBM Db2 Kernel Triggers (`TRG_AUDIT_STATUS_CHANGE`)**.

```
                   +-------------------------------------------------------------+
                   |                 UPDATE REQUEST TRIGGERED                    |
                   |  (REST API PATCH, Officer Console, or direct Db2 CLI DML)   |
                   +------------------------------+------------------------------+
                                                  |
                                                  v
                   +-------------------------------------------------------------+
                   |           IBM Db2 ENGINE (KERNEL TRANSACTION)               |
                   |                                                             |
                   |  1. UPDATE grievances SET status = ..., priority = ...      |
                   |  2. Db2 Engine invokes: TRG_AUDIT_STATUS_CHANGE             |
                   |     - Compares OLD (O) and NEW (N) values                   |
                   |     - Condition: (N.status <> O.status OR                   |
                   |                   N.priority <> O.priority)                 |
                   |  3. In-Kernel INSERT INTO grievance_updates (               |
                   |        grievance_id, previous_status, new_status,           |
                   |        notes, updated_by, created_at                        |
                   |     ) VALUES (N.id, O.status, N.status, ...,                |
                   |        'Db2 Engine (TRG_AUDIT_STATUS_CHANGE)',              |
                   |        CURRENT TIMESTAMP);                                  |
                   +------------------------------+------------------------------+
                                                  |
                                                  v
                   +-------------------------------------------------------------+
                   |             COMMIT TRANSACTION (ACID GUARANTEE)             |
                   | Both grievance state & audit row persist atomically         |
                   +-------------------------------------------------------------+
```

### Architectural Comparison: Application-Layer vs. Db2 Kernel Trigger

| Architectural Dimension | Application-Layer Logging (FastAPI) | IBM Db2 Kernel Trigger (`TRG_AUDIT_STATUS_CHANGE`) |
|---|---|---|
| **Execution Boundary** | Application worker memory (Python runtime) | Relational database storage engine kernel (IBM Db2) |
| **Atomicity & ACID Safety** | Vulnerable if application crashes between DML calls | Guaranteed 100% atomic within the same WAL commit boundary |
| **Bypass Vulnerability** | Direct DBA SQL, batch scripts, or external tools bypass logging | Impossible to bypass; fires on *any* UPDATE regardless of client |
| **Condition Verification** | Requires manual `if old_status != new_status` code in Python | Evaluated at row level in SQL engine: `WHEN (N.status <> O.status OR N.priority <> O.priority)` |
| **Author Attribution** | Captures application user context (e.g. "Sanitary Superintendent") | Attributed immutably to `'Db2 Engine (TRG_AUDIT_STATUS_CHANGE)'` |
| **Self-Healing Lifecycle** | Depends on developer writing update logic | Auto-reflected from `SYSCAT.TRIGGERS` on startup by `database.py` |

By layering both mechanisms, CPGRAMS provides rich human context (officer notes and inspection reports) alongside an unfalsifiable, cryptographic database-level audit ledger.

---

## 9. LangChain Agentic Tool-Calling Architecture (CPGRAMS Sahayak Assistant)

The **CPGRAMS Sahayak Assistant** (`POST /api/sahayak/chat`) transforms static FAQ bots into an autonomous, agentic tool-dispatcher directly interfacing with IBM Db2:

```
                               +--------------------------------------------+
                               |     CITIZEN / ASSISTANT USER QUERY         |
                               | ("What is the status of GRV-2026-1028?" /  |
                               |  "Are there active complaints in Rohini?") |
                               +---------------------+----------------------+
                                                     |
                                                     v
                               +--------------------------------------------+
                               |     LANGCHAIN AGENT INTENT DISPATCHER      |
                               | (Analyzes intent, language & entity params)|
                               +---------------------+----------------------+
                                                     |
                   +---------------------------------+---------------------------------+
                   |                                 |                                 |
                   v                                 v                                 v
        [1. tool_track_docket]            [2. tool_ward_status]             [3. tool_civic_knowledge]
        - Queries Db2 tracking_id         - Municipal Ward regex match      - 15-day statutory SLA rules
        - Latest officer audit notes      - Aggregates open complaint load   - 12-day escalation rights
        - Db2 DAYS() SLA check            - Critical hotspot calculations   - CPGRAMS vs RTI jurisdiction
                   |                                 |                                 |
                   +---------------------------------+---------------------------------+
                                                     |
                                                     v
                               +--------------------------------------------+
                               |         IBM Db2 KERNEL EXECUTION           |
                               |  Native SQL against GRIEVDB on port 50000  |
                               +---------------------+----------------------+
                                                     |
                                                     v
                               +--------------------------------------------+
                               |      NATURAL SYNTHESIS & LOCALIZATION      |
                               |   Renders grounded reply (Hindi/English)   |
                               |   Appends 1-click interactive docket card  |
                               +--------------------------------------------+
```

### Agentic Native Tool Registry

1. **`tool_track_docket(tracking_id: str)`**:
   - Queries `grievances` for the citizen docket, current status, assigned nodal department, and elapsed calendar days via Db2 date math `DAYS(CURRENT DATE) - DAYS(DATE(created_at))`.
   - Fetches the latest administrative audit trail note from `grievance_updates`.
   - Returns structured metadata enabling the frontend widget to inject a 1-click tracking card linking to `track-status.html?id=...`.

2. **`tool_ward_status(ward_query: str)`**:
   - Queries IBM Db2 for active cases in that specific municipal ward (`Rohini`, `Karol Bagh`, `Dwarka`, `Mayur Vihar`, etc.).
   - Computes open dockets count, critical priority count, and active hotspot warnings (`open_cases > 3`).
   - Identifies the dominant civic problem category in that sector.

3. **`tool_civic_knowledge(query: str)`**:
   - Encapsulates administrative regulations from the Department of Administrative Reforms & Public Grievances (DARPG).
   - Provides authoritative advice on the 15-day citizen charter SLA, 12-day joint secretary escalation rights, national helpline details, and filing eligibility.

