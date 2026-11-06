# Round 1 Proposal: Ideation & Architecture
## IBM Db2Hack 2026

**Project Title:** Db2 Sentinel AI: Autonomous Financial Crime Surveillance, Multi-Agent AML & Regulatory SAR Intelligence Platform  
**Participant:** Soham (soham092510@gmail.com | GitHub: @soham-092510)  
**Track:** AI Engineering / Enterprise Database AI  
**Repository:** https://github.com/soham-092510/IBM_Db2_TechX_Project_Submission  

---

### 1. Problem Statement
Global financial institutions face an estimated **\$3.1 Trillion** in illicit money laundering and terrorist financing annually. While enterprise banking universally relies on **IBM Db2** for mission-critical core ledgers and high-throughput transactions, existing Anti-Money Laundering (AML) compliance tooling relies on brittle keyword rules and isolated point-solutions. This creates three critical failures:
1. **95% False-Positive Rate**: Compliance teams waste 80% of their operational hours reviewing benign transactions.
2. **Investigation Fatigue**: A single alert takes 4–6 hours of manual ledger querying, counterparty tracing, and document drafting.
3. **Severe Regulatory Fines**: Missing filing deadlines (FinCEN 30-day mandate, RBI Suspicious Transaction Reporting) incurs billions in regulatory penalties and reputational damage.

Existing solutions extract sensitive financial data into disconnected third-party vector databases, introducing severe data privacy breaches (GDPR, PCI-DSS, SOC 2) and latency bottlenecks.

---

### 2. Proposed Solution & Key Features
**Db2 Sentinel AI** transforms IBM Db2 into an active, autonomous regulatory intelligence hub. It integrates **IBM Db2 12.1+ Native Vector Search**, **Recursive Common Table Expressions (CTEs)**, and **LangGraph cyclical multi-agent orchestration** to autonomously detect financial crime and compile legally compliant Suspicious Activity Reports (SARs) in **under 30 seconds**.

#### Core Features:
- **In-Database Semantic Vector Matching**: Indexes Financial Action Task Force (FATF) typologies using native Db2 `VECTOR(384, FLOAT32)` and `VECTOR_DISTANCE(..., 'COSINE')` inside atomic transactions.
- **Recursive CTE Circular Flow Traversal**: Detects multi-hop circular fund routing (A &rarr; B &rarr; C &rarr; A) directly within IBM Db2 via SQL Common Table Expressions without external graph databases.
- **Window Velocity Analytics**: Employs Db2 window functions (`AVG OVER PARTITION`) to identify burst structuring (smurfing) patterns just below statutory reporting limits ($9,000–$9,999).
- **LangGraph Checkpoint Persistence in Db2**: Preserves intermediate agent states, tool outputs, and decisions in Db2 `AGENT_CHECKPOINTS` for ACID reliability, pause-and-resume workflows, and courtroom replayability.
- **Automated FinCEN / RBI SAR Filing**: Generates formal 5-part regulatory Suspicious Activity Reports with line-item citations to Db2 transaction record IDs.
- **Immutable Cryptographic Audit Trail**: Computes SHA-256 cryptographic signatures on all enforcement actions and stores them in the Db2 `AUDIT_TRAIL` table.
- **Dual-Mode Engine**: Operates natively on live IBM Db2 12.1+ (via `ibm_db` and SQLAlchemy `ibm_db_sa`), with an embedded zero-setup local emulation engine for instant reproducible evaluation.

---

### 3. Selected Agentic AI Framework
- **Framework:** **LangGraph** (Cyclical Multi-Agent StateGraph) & **LangChain Core**.
- **Orchestration Architecture:**
  1. `ScreeningAgent`: High-throughput rule & sanctions watchlist screening.
  2. `ForensicInvestigatorAgent`: Queries historical Db2 ledgers and performs native Db2 Vector similarity search.
  3. `GraphRiskAgent`: Recursive SQL CTE cycle discovery and network topology analysis.
  4. `SARDrafterAgent`: Auto-generates structured regulatory compliance filings.
  5. `SupervisorAgent`: Human-in-the-loop review, account freeze authorization, and cryptographic audit signing.

---

### 4. IBM Db2 Connector & Intended Integration
- **Driver / Connector:** `ibm_db` (IBM Db2 native C-driver bindings) and `ibm_db_sa` (SQLAlchemy dialect).
- **Db2 Capabilities Leveraged:**
  - `VECTOR(384, FLOAT32)` column type for dense embeddings.
  - `VECTOR_DISTANCE(EMBEDDING, ?, 'COSINE')` for in-database vector cosine distance queries.
  - `WITH RECURSIVE` Common Table Expressions (CTEs) for multi-hop graph cycle detection.
  - Analytical window functions (`AVG(...) OVER (PARTITION BY ... ORDER BY ...)`).
  - Transactional ACID locking and rollback protection during account freezing.
  - Temporal immutable logging in `AUDIT_TRAIL`.

---

### 5. Proposed System Architecture & Workflow

```text
Inbound Wire Interception ──> [ScreeningAgent] (Db2 Watchlist & Threshold Check)
                                      │
                                      ▼
                        [ForensicInvestigatorAgent] (Db2 Vector Typology Matching)
                                      │
                                      ▼
                          [GraphRiskAgent] (Db2 Recursive CTE Loop Detection)
                                      │
                                      ▼
                         [SARDrafterAgent] (FinCEN / RBI Regulatory Narrative)
                                      │
                                      ▼
                         [SupervisorAgent] (Human Gatekeeper & Db2 Freeze)
                                      │
                                      ▼
                         [IBM Db2 12.1+ Ledger] (Checkpoints, Audit & SAR Storage)
```

---

### 6. Expected Impact & Enterprise Value
- **82% Reduction in False Positives**: Vector-grounded typology matching distinguishes routine commercial transfers from genuine structuring.
- **90% Faster SAR Turnaround**: Generates complete, evidence-backed regulatory dossiers in under 30 seconds versus 4–6 hours of manual drafting.
- **Zero Data Leakage**: Sensitive financial transactions and vectors remain inside IBM Db2's enterprise security boundary.
- **Courtroom-Grade Auditability**: Every reasoning step and enforcement decision is immutably timestamped and cryptographically signed in Db2.

---
*Submitted for IBM Db2Hack 2026 | Ideation & Architecture Round*
