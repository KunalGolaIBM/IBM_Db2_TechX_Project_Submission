# Db2Sentinel AI — Architecture & Technical Specifications
**IBM Db2 TechX Summit 2026 — Project Submission**  
**Category:** AI Engineering / Enterprise Database Security / Multi-Agent Systems  

---

## 1. Executive Architecture Overview

Db2Sentinel AI is an Agentic AI-powered enterprise database security, anomaly detection, and incident response platform. It elevates **IBM Db2** from passive relational storage into an active security intelligence layer. By coupling IBM Db2's native audit facilities and event monitors with **LangGraph** stateful multi-agent orchestration, Db2Sentinel AI autonomously investigates suspicious database behaviors, correlates multi-event attack timelines, calculates mathematically explainable risk scores, and routes containment actions to human database administrators for approval.

```
+-----------------------------------------------------------------------------------------+
|                                8. HUMAN GOVERNANCE LAYER                               |
|        Security Analyst Triage  *  DBA Approval Gate  *  Tamper-Evident Audit Log       |
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (Approval Tokens & Rollback Controls)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                               7. SECURITY DASHBOARD (REACT)                             |
|      Overview Console  *  Events Explorer  *  Alerts  *  AI Investigation  *  Approvals |
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (REST API & WebSockets)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                           6. APPLICATION BACKEND (FASTAPI)                              |
|          FastAPI REST API  *  Pydantic v2 Contracts  *  JWT Auth & RBAC Middleware       |
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (Workflow Execution & State Queries)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                           5. LANGGRAPH MULTI-AGENT ENGINE                               |
|   Supervisor Agent  *  Detection  *  Evidence  *  Investigation  *  Risk  *  Response   |
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (Event Triggers & Risk Metrics)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                        4. DETECTION & RISK ANALYTICS ENGINE                             |
|     6 Deterministic Rules  *  Statistical Z-Score Engine  *  Explainable Scoring (0-100)|
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (Parameterized SQL Queries via ibm_db)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                             3. IBM Db2 ENTERPRISE DATA LAYER                            |
|  SENTINEL_EVENTS  *  SENTINEL_ALERTS  *  SENTINEL_INCIDENTS  *  SENTINEL_INVESTIGATIONS |
|              SENTINEL_APPROVALS  *  SENTINEL_AUDIT_LOG  *  B-Tree Indexes               |
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (Normalized Batch Inserts via ibm_db)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                        2. INGESTION & NORMALIZATION PIPELINE                            |
|       Telemetry Ingestion  *  JSON Parser  *  Schema Validator  *  Deduplicator         |
+-----------------------------------------------------------------------------------------+
                                             ▲
                                             │ (Raw Event Feeds)
                                             ▼
+-----------------------------------------------------------------------------------------+
|                         1. ENTERPRISE DATA SOURCES (IBM Db2)                            |
|   Db2 Audit Facility (db2audit)  *  Activity Event Monitors  *  Synthetic Generator     |
+-----------------------------------------------------------------------------------------+
```

---

## 2. IBM Db2 Integration Architecture

### 2.1 Dual Telemetry Ingestion Paths
1. **Path A — Native Db2 Audit Facility (`db2audit`):**  
   Captures authentication (`AUTHENTICATION`), authorization failures (`CHECKING`), administrative actions (`SYSADMIN`), and context changes directly from the Db2 kernel. Raw records extracted via `db2audit extract` are parsed, normalized, and ingested into `SENTINEL_EVENTS`.
2. **Path B — Db2 Activity Event Monitors (`WRITE TO TABLE`):**  
   Configured via `CREATE EVENT MONITOR mon_act FOR ACTIVITIES WRITE TO TABLE`. Collects live DML/DDL query text, compilation metrics, execution CPU time, and rows read/returned for deep SQL anomaly detection.

### 2.2 Official Python Connector (`ibm_db`)
All interactions with IBM Db2 utilize the official IBM C-driver and DBI driver (`ibm_db`).
- **Encrypted TLS Wire Protocol:** Connection strings specify `SECURITY=SSL` and certificate paths.
- **Parameterized SQL Execution:** All queries are prepared using `ibm_db.prepare()` and executed with tuple parameter bindings (`ibm_db.execute()`), eliminating SQL injection risks.
- **Graceful Diagnostic Fallback:** When running in isolated demonstration or offline environments, the system seamlessly activates a local relational engine that replicates the exact same table schema, guaranteeing testability across diverse judging environments.

### 2.3 Relational Schema Definition
The database stores 6 core normalized entities:
- `SENTINEL_EVENTS`: Stores normalized database audit events (event type, username, source IP, SQL operation, object name, status, timestamp, raw details).
- `SENTINEL_ALERTS`: Stores triggered security alerts with rule classifications and severity levels.
- `SENTINEL_INCIDENTS`: Correlates multi-event security incidents with assigned severity and AI summary.
- `SENTINEL_INVESTIGATIONS`: Stores agent-specific findings, attack hypotheses, and confidence metrics.
- `SENTINEL_APPROVALS`: Stores human governance approval tokens, requested actions, and reviewer sign-offs.
- `SENTINEL_AUDIT_LOG`: Immutable audit trail with SHA-256 verification hashes recording all administrative actions.

---

## 3. Cybersecurity Detection & Risk Engine

### 3.1 Six Deterministic Security Rules
- **RULE 1: Brute Force Authentication:** Detects $\ge 5$ failed logins from the same source IP or account within 15 minutes.
- **RULE 2: Password Spraying Campaign:** Identifies single source IPs attempting logins across $\ge 3$ distinct accounts.
- **RULE 3: Privileged Activity & Catalog Reconnaissance:** Flags sensitive administrative queries or reconnaissance against catalog tables (`SYSCAT.DBAUTH`, `SYSCAT.TABLES`).
- **RULE 4: Unusual Query Activity:** Identifies statistical volume anomalies ($z$-score $\ge +3.0\sigma$) relative to historical baselines.
- **RULE 5: Sensitive Object Access:** Flags access to crown-jewel tables (e.g., `CUSTOMER_FINANCIAL_RECORDS`, `CREDIT_CARDS`).
- **RULE 6: Suspicious Operating Window:** Detects connections outside authorized business hours (e.g., 02:00 AM).

### 3.2 Transparent Mathematical Risk Scoring
Risk scores are calculated using a deterministic formula (0–100):
$$\text{Risk Score} = 0.30 \times \text{Dev}_{\text{Behavior}} + 0.25 \times \text{Sens}_{\text{Privilege}} + 0.25 \times \text{Anom}_{\text{DataVolume}} + 0.20 \times \text{Anom}_{\text{Auth}}$$

- **0–24:** LOW (Informational operational variance)
- **25–49:** MEDIUM (Isolated off-hours access or minor anomaly)
- **50–74:** HIGH (Repeated failed logins, catalog exploration)
- **75–100:** CRITICAL (Active data exfiltration or compromised privileged account)

---

## 4. LangGraph Multi-Agent Architecture

```
                  ┌──────────────────────┐
                  │        START         │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   DETECTION AGENT    │
                  │ Flags rule breaches  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    EVIDENCE AGENT    │
                  │ Correlates Db2 events│
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ INVESTIGATION AGENT  │
                  │ MITRE T1087 / T1213  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │      RISK AGENT      │
                  │ Computes 4-factor wt │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    RESPONSE AGENT    │
                  │ Containment proposals│
                  └──────────┬───────────┘
                             │
                             ▼
              [ HUMAN APPROVAL CHECKPOINT ]
              (No autonomous execution)
                             │
                             ▼
                  ┌──────────────────────┐
                  │     REPORT AGENT     │
                  │ Executive report gen │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │         END          │
                  └──────────────────────┘
```

### 4.1 Specialized Agent Roles
1. **Detection Agent:** Ingests normalized events, analyzes active detection rules, and scopes initial incident severity.
2. **Evidence Agent:** Correlates Db2 records chronologically, preserving immutable `source_event_id` citations to prevent LLM hallucinations.
3. **Investigation Agent:** Evaluates attack patterns, separates factual database evidence from hypotheses, and maps techniques to MITRE ATT&CK (T1087, T1213, T1110).
4. **Risk Agent:** Interprets the deterministic mathematical risk score and breaks down contributing factors.
5. **Response Agent:** Proposes non-destructive containment steps (session termination, account locks, firewall blocks) requiring explicit human sign-off.
6. **Report Agent:** Synthesizes the final executive report with full provenance citations.

---

## 5. Security & Human Governance

- **Read-Only Monitoring by Default:** The core service account in IBM Db2 is granted strictly `SELECT` permissions on security tables.
- **Human Approval Intercepts:** Critical actions (`FORCE APPLICATION`, `REVOKE CONNECT`) cannot execute autonomously. A signed approval token from an authorized DBA is required.
- **Tamper-Evident Audit Trail:** Every human and automated action is recorded in `SENTINEL_AUDIT_LOG` with a cryptographic SHA-256 hash.
- **Prompt Injection Defense:** Database SQL strings and user inputs are handled strictly as structured data values, never interpolated into LLM prompts.
