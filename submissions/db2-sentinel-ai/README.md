# Db2 Sentinel AI: Autonomous Financial Crime Surveillance & Regulatory SAR Intelligence Platform

> **One-Line Pitch:** An enterprise-grade, multi-agent financial intelligence and anti-money laundering (AML) platform powered by IBM Db2 12.1+ native vector search, transactional state checkpointers, recursive CTE circular routing analytics, and automated FinCEN/RBI Suspicious Activity Report (SAR) generation.

[![Validate Submission](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/actions/workflows/validate-submission.yml/badge.svg)](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/actions)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![IBM Db2](https://img.shields.io/badge/IBM%20Db2-12.1%2B%20Native%20Vector-0F62FE.svg)](https://www.ibm.com/products/db2)
[![LangGraph](https://img.shields.io/badge/Agentic%20AI-LangGraph%20%7C%20LangChain-FF4B4B.svg)](https://langchain-ai.github.io/langgraph/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## Table of Contents
- [Executive Summary](#executive-summary)
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration & Technical Depth](#ibm-db2-integration--technical-depth)
- [Multi-Agent AI Architecture (LangGraph)](#multi-agent-ai-architecture-langgraph)
- [Preloaded Landmark Crime Scenarios](#preloaded-landmark-crime-scenarios)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Interactive Web Dashboard Walkthrough](#interactive-web-dashboard-walkthrough)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Executive Summary
Global financial institutions face an estimated **\$3.1 Trillion** in illicit money laundering and financial crime flows annually. While enterprise banking depends almost universally on **IBM Db2** for mission-critical core ledgers and high-throughput transaction processing, existing AML compliance tooling relies on brittle keyword rules and isolated point-solutions. This results in:
1. An alarming **95% false-positive rate** inundating compliance teams.
2. An average of **4 to 6 hours of manual forensic investigation** per flagged alert.
3. Strict regulatory deadlines (FinCEN 30-day mandate, RBI STR guidelines) where non-compliance incurs billions in fines.

**Db2 Sentinel AI** transforms IBM Db2 into an active, autonomous regulatory intelligence hub. By uniting **IBM Db2 12.1+ Native Vector Similarity Search**, **Recursive CTE graph analytics**, **ACID-compliant Agent State Checkpointing**, and **LangGraph cyclical multi-agent workflows**, Db2 Sentinel autonomously screens wires, discovers complex structuring and circular layering rings, and generates legally compliant Suspicious Activity Reports (SARs) with complete cryptographic auditability in **under 30 seconds**.

---

## Problem Statement

### 1. The Challenge
Traditional Anti-Money Laundering (AML) and Counter-Terrorist Financing (CTF) architectures are siloed from core transactional databases. Compliance analysts manually extract transaction ledgers, cross-reference static watchlists on external systems, and assemble narrative dossiers in word processors.

### 2. Target Audience
- **Tier-1 Bank Compliance Officers & MLROs (Money Laundering Reporting Officers)**: Requiring defensible, auditable alert triage.
- **Financial Intelligence Units (FIUs & Regulators)**: Demanding standardized, evidence-backed SAR/STR filings.
- **Enterprise Database Architects**: Seeking to leverage IBM Db2's modern vector and analytical capabilities without duplicating data into third-party vector databases.

### 3. Why Existing Tooling Is Insufficient
- **Keyword Blindness**: Bad actors disguise wire memos using deceptive descriptions ("consultancy tranche split", "overseas software licensing fee") that evade simple string filters.
- **Disconnected Vector Databases**: Moving sensitive banking data out of IBM Db2 into external vector stores introduces severe security vulnerabilities, compliance breaches (GDPR, PCI-DSS, SOC 2), and data duplication overhead.
- **Lack of Decision Replayability**: LLMs alone hallucinate and cannot provide deterministic audit trails needed for courtroom evidence.

---

## Solution Overview

Db2 Sentinel AI delivers an end-to-end autonomous surveillance pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Db2 Sentinel AI Pipeline                           │
│                                                                             │
│  [ Transaction Stream ]                                                     │
│            │                                                                │
│            ▼                                                                │
│  [ Node 1: ScreeningAgent ] ──────> Watchlist & Threshold Screening         │
│            │                                                                │
│            ▼                                                                │
│  [ Node 2: ForensicInvestigatorAgent ] ──> Db2 Native Vector Typology Search│
│            │                               Db2 Window Velocity Aggregation  │
│            ▼                                                                │
│  [ Node 3: GraphRiskAgent ] ──────> Db2 Recursive CTE Circular Flow Audit  │
│            │                                                                │
│            ▼                                                                │
│  [ Node 4: SARDrafterAgent ] ─────> Auto-Drafts FinCEN/RBI SAR Filing       │
│            │                                                                │
│            ▼                                                                │
│  [ Node 5: SupervisorAgent ] ─────> Human-in-the-Loop Freeze & SHA-256 Sign │
│            │                                                                │
│            ▼                                                                │
│  [ IBM Db2 12.1+ Ledger ] <─────── Checkpoints, Audit Trails & SAR Storage │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Dual-Mode Enterprise Architecture**: Seamlessly connects to live **IBM Db2 12.1+** (Docker or Cloud) using `ibm_db` and SQLAlchemy `ibm_db_sa`. Includes an automated zero-setup local high-fidelity emulation engine so evaluators can run the entire system instantly in 5 seconds.
2. **In-Database Semantic Vector Search**: Embeds FATF money laundering typologies and queries them using native Db2 `VECTOR(384, FLOAT32)` and `VECTOR_DISTANCE(..., 'COSINE')` inside atomic SQL transactions.
3. **Graph Topology Analysis via Recursive SQL**: Traces multi-hop circular fund routing (A &rarr; B &rarr; C &rarr; A) directly within IBM Db2 via Common Table Expressions (`WITH RECURSIVE`).
4. **LangGraph State Checkpointer in Db2**: Every agent step, tool call, and reasoning trace is checkpointed into Db2 `AGENT_CHECKPOINTS` for fault tolerance, replayability, and regulatory audits.
5. **Automated Regulatory Filings**: Synthesizes forensic findings into standardized FinCEN/RBI Suspicious Activity Reports (SAR) with exact Db2 line-item citations.
6. **Immutable Cryptographic Audit Trail**: Every decision is sealed with SHA-256 cryptographic signatures stored in the `AUDIT_TRAIL` table.

---

## IBM Db2 Integration & Technical Depth

Db2 Sentinel AI showcases non-trivial, multi-modal IBM Db2 features across 8 specialized tables:

| Db2 Table | Core Role | Advanced IBM Db2 Capability Utilized |
|---|---|---|
| `ACCOUNTS` | Core entity ledger & KYC profile | Relational integrity, foreign keys, CHECK constraints, status locking |
| `TRANSACTIONS` | High-throughput financial wire stream | `DECIMAL(18,2)` precision, TIMESTAMP indexes, transactional ACID commits |
| `SANCTIONS_WATCHLIST` | OFAC SDN, UN & PEP designations | SQL substring indexing & fuzzy entity name matching |
| `AML_TYPOLOGIES` | International crime patterns catalog | Native `VECTOR(384, FLOAT32)` column, `VECTOR_DISTANCE(..., 'COSINE')` |
| `INVESTIGATION_ALERTS` | Autonomous surveillance queue | Dynamic risk scoring, state transition tracking |
| `AGENT_CHECKPOINTS` | LangGraph agent persistence | ACID serialization of multi-agent state into Db2 CLOB storage |
| `AUDIT_TRAIL` | Regulatory compliance ledger | Temporal immutable logging, SHA-256 cryptographic hash verification |
| `SAR_FILINGS` | Formal statutory submissions | Legal dossier storage, structured relational metadata + narrative CLOB |

### Advanced Db2 Queries Highlights

#### 1. Native Db2 Vector Similarity Search
```sql
SELECT TYPOLOGY_ID, CODE, TITLE, CATEGORY, RED_FLAGS,
       VECTOR_DISTANCE(EMBEDDING, ?, 'COSINE') AS DISTANCE
FROM AML_TYPOLOGIES
ORDER BY DISTANCE ASC
FETCH FIRST 3 ROWS ONLY;
```

#### 2. Recursive CTE Multi-Hop Circular Fund Routing Detection
```sql
WITH RECURSIVE TransferPaths(origin, current_node, path, depth, total_amount) AS (
    SELECT SENDER_ID, RECEIVER_ID, SENDER_ID || ' -> ' || RECEIVER_ID, 1, AMOUNT
    FROM TRANSACTIONS
    WHERE SENDER_ID = ?
    
    UNION ALL
    
    SELECT tp.origin, t.RECEIVER_ID, tp.path || ' -> ' || t.RECEIVER_ID, tp.depth + 1, t.AMOUNT
    FROM TRANSACTIONS t
    JOIN TransferPaths tp ON t.SENDER_ID = tp.current_node
    WHERE tp.depth < 4 AND tp.path NOT LIKE '%' || t.RECEIVER_ID || '%'
)
SELECT tp.origin, tp.current_node, tp.path, tp.depth, tp.total_amount
FROM TransferPaths tp
JOIN TRANSACTIONS back_tx ON tp.current_node = back_tx.SENDER_ID AND back_tx.RECEIVER_ID = tp.origin
WHERE tp.depth >= 2;
```

#### 3. Rolling Window Aggregation for Sub-Threshold Structuring
```sql
SELECT TX_ID, SENDER_ID, RECEIVER_ID, AMOUNT, TX_TIMESTAMP,
       AVG(AMOUNT) OVER (PARTITION BY RECEIVER_ID ORDER BY TX_TIMESTAMP 
                         ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS ROLLING_AVG
FROM TRANSACTIONS
WHERE AMOUNT BETWEEN 9000.00 AND 9999.00;
```

---

## Multi-Agent AI Architecture (LangGraph)

Db2 Sentinel AI coordinates five specialized agents via **LangGraph**:

1. **`ScreeningAgent`**:
   - Performs rapid rule evaluation against statutory thresholds ($10,000 CTR rule).
   - Screens counterparties and memo text against the Db2 `SANCTIONS_WATCHLIST`.
2. **`ForensicInvestigatorAgent`**:
   - Dispatches hybrid queries into Db2 account histories.
   - Computes dense vector embeddings and matches transaction memos against FATF typologies in Db2.
   - Detects burst structuring and velocity anomalies.
3. **`GraphRiskAgent`**:
   - Executes recursive SQL graph traversals to identify circular laundering loops and money mule aggregation.
4. **`SARDrafterAgent`**:
   - Compiles a complete 5-part regulatory Suspicious Activity Report (Part I: Subjects, Part II: Transaction Details, Part III: Typology Citations, Part IV: Narrative, Part V: Disposition).
5. **`SupervisorAgent` (Human-in-the-Loop)**:
   - Evaluates recommended enforcement actions (`FREEZE_AND_FILE_SAR`).
   - Executes transactional account freezing in Db2.
   - Commits the signed SAR report and generates a SHA-256 cryptographic audit record.

---

## Preloaded Landmark Crime Scenarios

The system includes pre-seeded realistic enterprise test cases:

- **Case 1: Structuring / Smurfing Ring (`TX-STRUCT-01`, `02`, `03`)**:
  Three accounts route \$9,850, \$9,900, and \$9,750 to offshore entity `Pan-Asia Invoicing FZE` within a 45-minute window with deceptive split consultancy memos.
- **Case 2: Circular Routing & Layering (`TX-LOOP-01`, `02`, `03`)**:
  A \$250,000 wire originates at `Starlight BVI`, hops through Cyprus and Seychelles shell accounts, and returns to the originator within 36 hours.
- **Case 3: Sanctions Front Evasion (`TX-SANCT-01`)**:
  A \$185,000 transfer referencing disguised maritime bunkering for `Titan Petrochemical Trading LLC` (an OFAC SDN designated entity).
- **Case 4: Legitimate Baseline Contrast (`TX-NORM-01`)**:
  Routine corporate IT software license payment (\$42,000) between verified counterparties.

---

## Tech Stack
- **Languages**: Python 3.10+
- **Database**: IBM Db2 12.1+ (Native Vector Engine) / Dual-Mode Local High-Fidelity Engine
- **Connectors**: `ibm_db`, `ibm_db_sa`, `SQLAlchemy`
- **Agentic AI Framework**: LangGraph, LangChain
- **Embeddings & Analytics**: Sentence-Transformers / IBM Granite Embeddings, Scikit-Learn, NetworkX, NumPy, Pandas
- **User Interface**: Streamlit (Enterprise Dark Dashboard), PyVis (Graph Visualizer), ReportLab (PDF Exporter)
- **Quality & Testing**: PyTest, Rich Console

---

## Prerequisites
- **Python**: `>= 3.10`
- **Operating System**: Windows, Linux, or macOS
- **Optional**: Docker (if running local IBM Db2 Community Edition container)

---

## Setup & Installation

### 1. Clone Repository and Navigate to Submission Directory
```bash
git clone https://github.com/soham-092510/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission/submissions/db2-sentinel-ai
```

### 2. Set Up Python Virtual Environment
```bash
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

The application defaults to `DB2_MODE=auto`, which attempts to connect to your configured IBM Db2 instance, and automatically enables the embedded high-fidelity local engine if an active Db2 instance is not found.

### Optional: Running Live IBM Db2 via Docker
To spin up a local IBM Db2 Community Edition container:
```bash
docker-compose up -d
# Wait for container initialization (~2-3 minutes)
```

---

## Running the Project

### Option A: Interactive Enterprise Web Dashboard (Recommended)
Launch the full-featured Streamlit UI:
```bash
streamlit run src/app.py
```
Open your browser at `http://localhost:8501`.

### Option B: Autonomous CLI Pipeline
Execute the end-to-end multi-agent investigation runner in your terminal:
```bash
python src/main.py
```

---

## Testing & Verification

Db2 Sentinel AI includes a comprehensive, automated PyTest suite covering database operations, native vector search, multi-agent workflows, and SAR report exports.

Run all tests:
```bash
pytest tests/ -v
```

Expected output:
```text
tests/test_db_operations.py::test_schema_and_accounts_seeded PASSED      [  6%]
tests/test_db_operations.py::test_transactions_seeded PASSED             [ 13%]
tests/test_db_operations.py::test_get_transaction_by_id PASSED           [ 20%]
tests/test_db_operations.py::test_structuring_detection PASSED           [ 26%]
tests/test_db_operations.py::test_circular_routing_detection PASSED      [ 33%]
tests/test_db_operations.py::test_audit_trail_integrity PASSED           [ 40%]
tests/test_multi_agent.py::test_workflow_structuring_case PASSED         [ 46%]
tests/test_multi_agent.py::test_workflow_circular_routing_case PASSED    [ 53%]
tests/test_multi_agent.py::test_workflow_normal_transaction_case PASSED  [ 60%]
tests/test_multi_agent.py::test_db2_checkpoint_persistence PASSED        [ 66%]
tests/test_sar_generation.py::test_sar_narrative_contents PASSED         [ 73%]
tests/test_sar_generation.py::test_export_sar PASSED                     [ 80%]
tests/test_vector_search.py::test_embedding_generation PASSED            [ 86%]
tests/test_vector_search.py::test_cosine_similarity PASSED               [ 93%]
tests/test_vector_search.py::test_vector_search_typologies PASSED        [100%]

============================= 15 passed in 4.18s ==============================
```

### Validate Hackathon Structure
Ensure compliance with official hackathon submission rules:
```bash
python ../../scripts/validate_submission.py submissions/db2-sentinel-ai
```

---

## Interactive Web Dashboard Walkthrough

The web dashboard features 5 specialized views:

1. **Transaction Feed & Alerts**: Live view of all transactions, active account statuses, and pending alert queues with risk heatmaps.
2. **Multi-Agent Investigation Canvas**: Real-time visualization of LangGraph state transitions, agent thoughts, Db2 SQL queries, and calculated risk scores.
3. **Transaction Network Topology**: Interactive network graph highlighting circular routing loops, shell companies, and money mule hubs.
4. **Regulatory SAR Studio & Audit Log**: Official FinCEN / RBI Suspicious Activity Report viewer with one-click Markdown/PDF downloads and immutable SHA-256 signed audit trails.
5. **Text-to-SQL & Hybrid Vector Explorer**: Interactive SQL and vector querying studio for real-time Db2 database inspection.

---

## Known Limitations & Future Roadmap
- **Current Limitations**: Pre-seeded dataset contains synthetic banking transactions; production deployment requires integration with core banking SWIFT/Fedwire feeds.
- **Future Roadmap**:
  - Integration with IBM watsonx.governance for automated model risk management.
  - Multi-tenant Db2 schema partitioning for global cross-border correspondent banking.
  - Federated graph analytics across distributed Db2 pureScale clusters.

---

## Team Members & Credits

| Name | Role | GitHub | Contact |
|---|---|---|---|
| **Soham** | AI Engineer & Full-Stack Developer | [@soham-092510](https://github.com/soham-092510) | `soham092510@gmail.com` |

*Developed for IBM Db2Hack 2026 organized by IBM Db2 TechX, Institution's Innovation Council (IIC), and GL Bajaj Group of Institutions, Mathura.*
