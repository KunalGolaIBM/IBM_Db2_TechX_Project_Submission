# Db2Sentinel AI — Enterprise Security Model & Threat Architecture

## 1. Overview & Threat Landscape

Enterprise relational databases such as IBM Db2 store an organization's most sensitive transactional records, intellectual property, financial ledgers, and personally identifiable information (PII). Attackers targeting relational databases seek to:
1. Compromise administrative credentials (`DBADM`, `SECADM`, `SYSADM`).
2. Bypass application-layer access controls via direct database connections.
3. Exfiltrate large data volumes without triggering threshold alerts.
4. Tamper with audit configurations to eliminate forensic evidence.

Db2Sentinel AI addresses these enterprise risks by coupling real-time telemetry streaming from IBM Db2 with an Agentic AI investigation pipeline governed by deterministic safety boundaries.

---

## 2. MITRE ATT&CK® Mapping for Database Threats

Db2Sentinel AI explicitly maps detected database anomalies and security events to the MITRE ATT&CK framework:

| MITRE Technique | Technique Name | Db2 Indicator of Compromise (IoC) | Sentinel Detection Rule | LangGraph Agent Response |
| :--- | :--- | :--- | :--- | :--- |
| **T1110.001** | Password Guessing / Brute Force | Multiple `SQL30082N` (Security processing failed with reason `24` - USERNAME AND/OR PASSWORD INVALID) within 60s window. | `RULE_BRUTE_FORCE` | Isolates attacking IP; queries historical connection baseline; initiates risk score. |
| **T1110.003** | Password Spraying | Sequential failed logins across multiple user accounts (`DB2INST1`, `APPUSER`, `ANALYST`) from single host/subnet. | `RULE_PASSWORD_SPRAY` | Groups affected accounts; correlates subnet CIDR; assigns high risk. |
| **T1078** | Valid Accounts / Privileged Abuse | Unscheduled administrative login during off-hours; unexpected `GRANT DBADM` or role modification. | `RULE_PRIVILEGE_ABUSE` | Validates against change management schedule; flags privilege escalation. |
| **T1005** | Data from Enterprise Repository | High-frequency `SELECT *` queries extracting >100,000 rows within 5 minutes without pagination. | `RULE_MASS_EXFILTRATION` | Calculates data volume deviation against 30-day baseline; recommends rate limiting. |
| **T1505.001** | SQL Injection / Tampering | Dynamic SQL containing tautologies (`'1'='1'`), union queries against `SYSCAT.TABLES`, or system command execution. | `RULE_UNUSUAL_QUERY` | Extracts AST parameters; isolates session handle; prepares kill command. |
| **T1485** | Data Destruction / Unauthorized DDL | `DROP TABLE`, `ALTER TABLE ... DROP COLUMN`, or `TRUNCATE` issued outside maintenance window. | `RULE_DESTRUCTIVE_DDL` | Immediate Critical alert; proposes session termination and schema freeze. |

---

## 3. Least-Privilege Database Access Architecture

Db2Sentinel AI enforces rigorous segregation of duties (SoD) between detection, investigation, and remediation:

```
+-------------------------------------------------------------------------------+
|                             IBM Db2 Database                                  |
+-------------------------------------------------------------------------------+
       ^                                 ^                                 ^
       | INSERT only                     | SELECT only                     | ADMIN (Controlled)
+---------------+               +-----------------+               +-------------------+
|  Telemetry    |               |  Detection &    |               |  Remediation      |
|  Ingest Agent |               |  Agent Pipeline |               |  Executor         |
+---------------+               +-----------------+               +-------------------+
   (Read-Only /                    (No DDL / No DML                  (Only executes after
    Append-Only)                    on Business Data)                 Human Approval)
```

1. **Ingest Account (`SENTINEL_INGEST`):**
   - Has `INSERT` permission only on `SENTINEL_EVENTS`.
   - Cannot read, update, or drop tables in any schema.
2. **Analysis & Agent Account (`SENTINEL_AGENT`):**
   - Has `SELECT` permission on `SENTINEL_*` tables and read-only views on `SYSCAT.TABLES`, `SYSCAT.ROLES`.
   - **Zero access** to customer business tables (`SALES`, `PAYMENTS`, `CUSTOMERS`).
   - Cannot execute administrative commands (`FORCE APPLICATION`, `REVOKE`, `DROP`).
3. **Remediation Account (`SENTINEL_ADMIN`):**
   - Credentials are held exclusively by the backend service and are locked behind a cryptographic authorization barrier.
   - Invocation requires an explicit status of `APPROVED` in `SENTINEL_APPROVALS` signed by a verified operator.

---

## 4. LLM Safety & Prompt Injection Defenses

Because Db2Sentinel AI utilizes Large Language Models (Gemini / OpenAI) within its investigation workflow, robust defenses against prompt injection and LLM hallucination are engineered into the core:

1. **Strict Separation of Data and Instructions:**
   - Raw SQL strings, user names, and error codes extracted from Db2 telemetry are encapsulated in structured JSON payloads before presentation to the LLM.
   - Raw user inputs are never concatenated directly into LLM system prompts.
2. **Schema-Enforced Pydantic Outputs:**
   - Every agent node parses its reasoning into strict Pydantic schemas (`AgentDecision`, `RiskScore`, `RemediationPlan`).
   - If the LLM generates unparseable or malicious text, the workflow immediately triggers the **Deterministic Rule Engine** fallback.
3. **Immutable Deterministic Fallback:**
   - Even without external LLM API access (e.g. air-gapped environments or API timeouts), the deterministic risk engine independently calculates the 4-factor risk score and generates standard Db2 containment syntax (`FORCE APPLICATION`, `REVOKE CONNECT`).

---

## 5. Human-in-the-Loop (HITL) Governance

Autonomous agents must never unilaterally alter production database state. Db2Sentinel AI implements human-in-the-loop controls via LangGraph interrupts:

1. **LangGraph StateGraph Checkpoint:**
   - The workflow compiles with an interrupt before the response execution node:
     ```python
     workflow.add_node("require_approval", human_approval_gate)
     workflow.add_edge("response_agent", "require_approval")
     ```
2. **Reviewer Decision Flow:**
   - **Pending:** Incident marked high/critical, remediation script staged in `SENTINEL_APPROVALS`.
   - **Approved:** Authorized DBA reviews command diff, signs off with rationale, and triggers backend execution.
   - **Rejected:** Operator marks remediation rejected with notes; incident status transitions to `CLOSED - REJECTED`.
3. **Tamper-Evident Audit Trail:**
   - All approvals, rejections, and command executions are recorded in `SENTINEL_AUDIT_LOG` with SHA-256 integrity hashes, client IP addresses, and timestamps.
