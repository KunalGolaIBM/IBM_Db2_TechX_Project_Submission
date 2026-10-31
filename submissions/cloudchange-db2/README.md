# CloudChange — IBM Db2 Integration

> **One-Line Pitch:** An enterprise cloud infrastructure change impact and empirical verification engine that analyzes Terraform plans, predicts cost and operational risks, verifies post-deployment outcomes using AWS evidence, and uses IBM Db2 as an ACID-compliant System of Record for compliance auditing and governance analytics.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [Core Architecture & Workflow](#core-architecture--workflow)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Screenshots & Visuals](#screenshots--visuals)
- [Governance & Analytics Endpoints](#governance--analytics-endpoints)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement

Modern cloud and DevOps teams face two critical blind spots when managing cloud infrastructure with Terraform:

1. **The Semantic & Impact Gap (Pre-Apply):**
   `terraform plan` outputs syntactic diffs (attribute changes, resource recreations), but does not evaluate operational blast radius, unexpected cost spikes, sensitive port exposures (e.g. SSH 22, RDP 3389 opened to `0.0.0.0/0`), or availability risks such as destructive database re-creations.
2. **The Verification & Evidence Gap (Post-Apply):**
   A successful exit code from `terraform apply` only confirms that AWS APIs accepted the API request, not that the intended architecture, operational health, or security posture was achieved in reality.
3. **The Persistence & Compliance Gap (System of Record):**
   Typical CI/CD tools treat change assessment as ephemeral terminal output. Regulated enterprises (finance, healthcare, defense) need a durable, queryable, ACID-compliant audit trail that records every planned change, predicted risk, applied state, and empirical post-apply observation. Without persistent enterprise storage, cross-deployment drift analytics and compliance tracking are impossible.

---

## Solution Overview

**CloudChange** bridges these gaps by providing an automated intelligence and validation layer around standard Terraform workflows:

- **Pre-Apply Impact Prediction:** Ingests `plan.json`, normalizes resource changes into canonical structures, and runs deterministic impact rules detecting cost spikes, sensitive port exposure, and destructive resource recreations.
- **Empirical Post-Apply Verification:** Ingests `state.json`, resolves physical cloud resource IDs (e.g., `i-08a1b2c3d4e`), queries AWS read-only APIs for empirical evidence, and compares expected configuration against real-world observations.
- **IBM Db2 Enterprise Persistence:** Integrates IBM Db2 via the official Python `ibm_db` driver as the enterprise System of Record. Every run, canonical change, impact finding, verifiable prediction, verification outcome, and compliance event is stored with full relational integrity and transactional ACID safety.

```
Terraform Plan (plan.json)
      ↓
CloudChange Impact Predictor
      ↓
[IBM Db2: Atomic Transaction (cc_runs, cc_canonical_changes, cc_impact_findings, cc_predictions)]
      ↓
Terraform Apply (state.json)
      ↓
AWS Read-Only Empirical Observation
      ↓
Verification Orchestrator
      ↓
[IBM Db2: Update Status, cc_verification_results, cc_audit_events]
      ↓
Governance & Compliance Audit Reports
```

---

## IBM Db2 Integration

The IBM Db2 integration is a core architectural pillar of CloudChange, engineered for enterprise durability, data integrity, and compliance:

### 1. Driver and Connector
- **Driver:** Official IBM Python driver (`ibm_db`), utilizing native C-extension connectivity for maximum throughput.
- **Connection Management:** `Db2ConnectionManager` manages connection lifecycles, connection pooling, and connection health probes (`SELECT 1 FROM SYSIBM.SYSDUMMY1`).
- **Security:** Full support for TLS/SSL encrypted connections (`DB2_SECURITY=SSL`) and custom server certificates (`DB2_SSL_SERVER_CERT`).

### 2. ACID Transaction Boundaries
- All multi-table write operations (such as saving a run, its canonical changes, rule findings, verifiable predictions, and audit log entries) run inside explicit transactional boundaries:
  ```python
  ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
  try:
      # Execute inserts / updates
      ibm_db.commit(conn)
  except Exception:
      ibm_db.rollback(conn)
      raise
  ```
- Partial state is never written to Db2. If any statement fails, the entire transaction is atomically rolled back.

### 3. Parameterized SQL Queries
- All SQL operations strictly use parameter markers (`?`) via `ibm_db.prepare()` and `ibm_db.execute()`, preventing SQL injection vulnerabilities.

### 4. Database Schema Design (Schema: `CLOUDCHANGE`)
CloudChange creates 6 relational tables with foreign keys (`ON DELETE CASCADE`) and secondary B-Tree indexes:

| Table Name | Description | Key Columns / Constraints |
|---|---|---|
| `cc_runs` | Master table storing assessment run metadata, summary counts, status, and raw JSON | `run_id` (PK), `status`, `created_at`, `total_changes`, `findings_count`, `summary_json`, `raw_run_json` |
| `cc_canonical_changes` | Normalized resource changes extracted from Terraform plan | `change_id` (PK), `run_id` (FK CASCADE), `resource_address`, `resource_type`, `action`, `requires_replacement`, `diffs_json` |
| `cc_impact_findings` | Rule-generated impact findings explaining operational/financial risks | `finding_id` (PK), `run_id` (FK CASCADE), `rule_id`, `category`, `severity`, `title`, `explanation` |
| `cc_predictions` | Verifiable post-deployment state predictions | `prediction_id` (PK), `run_id` (FK CASCADE), `resource_address`, `metric`, `verification_approach`, `expected_value_json` |
| `cc_verification_results` | Empirical verification outcomes matching predictions against AWS evidence | `result_id` (PK), `run_id` (FK CASCADE), `prediction_id`, `status`, `expected_value_json`, `observed_value_json`, `explanation` |
| `cc_audit_events` | Immutable chronological compliance audit log tracking lifecycle events | `event_id` (PK), `run_id` (FK CASCADE), `event_type`, `actor`, `recorded_at`, `payload_json` |

### 5. Idempotent Schema Initialization
- The schema initialization module (`backend.app.db2.schema`) can be safely run at any time (during deployment, CI, or application startup).
- It handles Db2 error codes `SQL0601N` (SQLCODE `-601`, table already exists) and `SQL0605N` (SQLCODE `-605`, index already exists) cleanly and idempotently.

---

## Core Architecture & Workflow

1. **Pre-Apply Ingestion (`POST /api/v1/runs`):**
   - Developer or CI/CD pipeline uploads a Terraform plan artifact (`plan.json`).
   - Normalizer extracts canonical changes, filtering no-ops and reading data sources.
   - Deterministic rules engine identifies risks (e.g. EC2 instance resize cost spikes, Security Group open CIDRs, RDS replacements).
   - `Db2PersistenceAdapter` persists the run, changes, findings, predictions, and an initial `RUN_CREATED` audit event in a single atomic Db2 transaction.
2. **Post-Apply Verification (`POST /api/v1/runs/{id}/verification`):**
   - Following `terraform apply`, the pipeline uploads Terraform state (`state.json`).
   - Physical resource identities are resolved.
   - Collectors retrieve read-only configuration evidence from live AWS APIs.
   - Predictions are verified (`VERIFIED`, `MISMATCH`, or `NOT_OBSERVABLE`).
   - Updated run status, verification records, and a `RUN_UPDATED_VERIFIED` event are committed to IBM Db2.
3. **Governance & Compliance Inquiries (`GET /api/v1/runs/{id}/audit`):**
   - Regulators and security leads query the immutable audit log directly from Db2.

---

## Tech Stack

- **Persistence Layer:** IBM Db2 (Community Edition in Docker / Enterprise / IBM Cloud)
- **Database Driver:** `ibm_db` (official Python driver)
- **Backend Framework:** Python 3.10+ / FastAPI / Uvicorn
- **Data Validation & Schemas:** Pydantic v2 / Pydantic-Settings
- **Cloud Evidence Collection:** AWS SDK for Python (`boto3`, read-only client adapters)
- **Testing Suite:** `pytest`, `pytest-asyncio`, `httpx`

---

## Prerequisites

- **Python:** Version 3.10, 3.11, 3.12, 3.13, or 3.14.
- **IBM Db2:** Running instance of IBM Db2 (Docker container, local installation, or IBM Cloud Db2).
  - *Note: Offline/mocked tests run completely without a running Db2 instance.*
- **AWS Credentials (Optional):** Read-only AWS credentials if running live post-deployment AWS verification.

---

## Setup & Installation

### 1. Clone & Navigate to Submission
```bash
cd submissions/cloudchange-db2
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Configuration

Copy the example configuration file:
```bash
cp .env.example .env
```

Edit `.env` to configure your Db2 connection parameters:
```env
# Persistence Backend: 'db2' for IBM Db2, 'memory' for in-memory fallback
DATABASE_BACKEND=db2

# IBM Db2 Connectivity
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=BLUDB
DB2_USER=db2inst1
DB2_PASSWORD=your_db2_password_here
DB2_SCHEMA=CLOUDCHANGE
DB2_SECURITY=
```

> **Security Note:** `.env.example` contains only placeholder values. Never commit actual database passwords or credentials to source control.

---

## Running the Project

### 1. Initialize the IBM Db2 Schema
To create the necessary tables and indexes in your Db2 instance:
```bash
python src/init_db2.py
```

### 2. Start the CloudChange Application Server
```bash
python src/main.py
```
The server will start at `http://0.0.0.0:8000`.

### 3. Verify Health Checks
- **Application Health:**
  ```bash
  curl http://localhost:8000/health
  # {"status":"healthy","service":"cloudchange-api","version":"0.1.0"}
  ```
- **IBM Db2 Connection Health:**
  ```bash
  curl http://localhost:8000/health/db2
  # {"service":"cloudchange-api","backend":"ibm_db2","connected":true,"configured":true,"database":"BLUDB","host":"localhost","port":50000}
  ```

---

## Testing & Verification

CloudChange provides comprehensive automated tests with a clear distinction between **mocked offline tests** and **live Db2 integration tests**:

### Running the Standard Test Suite (Mocked & Offline)
The standard test suite uses mocked database connections to verify SQL statement generation, parameterized binding, transaction commit/rollback, schema idempotency, and repository routing without requiring a live Db2 database:

```bash
pytest
```
*Result: **219 passed, 1 skipped** in ~5 seconds.*

### Running Live IBM Db2 Tests
To execute tests against a live IBM Db2 database instance:
1. Ensure your Db2 instance is running and credentials are set in environment variables (`DB2_HOST`, `DB2_PASSWORD`, etc.).
2. Execute pytest targeting the `live_db2` marker:
```bash
pytest -m live_db2
```
*Note: If Db2 is unreachable or credentials are not provided, live tests cleanly skip without failing.*

---

## Screenshots & Visuals

The submission includes detailed architectural and schema visual diagrams in `docs/screenshots/`:

1. **System & Persistence Architecture:**
   See `docs/screenshots/db2_architecture.svg` for the complete end-to-end component flow and transaction boundary diagram.

2. **Relational Schema & Index Design:**
   See `docs/screenshots/db2_schema_diagram.svg` for the entity-relationship mapping, foreign key cascades, and B-Tree indexes.

---

## Governance & Analytics Endpoints

The IBM Db2 integration adds enterprise-grade governance query capabilities:

### 1. Fetch Immutable Audit Trail
```http
GET /api/v1/runs/{run_id}/audit
```
Returns the chronological audit log for a specific infrastructure deployment, including timestamped status changes and action counts recorded in `cc_audit_events`.

### 2. Cross-Deployment Governance Summary
```http
GET /api/v1/runs/governance/summary
```
Queries IBM Db2 across all historical runs to aggregate:
- Resources requiring destructive replacement (`requires_replacement = 1`)
- Verification success rates (counts of `VERIFIED`, `MISMATCH`, and `NOT_OBSERVABLE`)

---

## Known Limitations & Future Roadmap

- **Current Scope:** Phase 1 focuses on AWS foundational resources (`aws_instance`, `aws_security_group`, `aws_db_instance`).
- **Future Roadmap:**
  - **Db2 Native Vector Embeddings:** Leverage IBM Db2 12.1+ native `VECTOR` data type to store high-dimensional embeddings of Terraform infrastructure changes and enable semantic similarity search across historical incidents.
  - **Multi-Cloud Extensions:** Extend empirical collectors to Azure and Google Cloud resources stored in the unified Db2 catalog.
  - **Automated Remediation Workflows:** Generate compensatory Terraform PRs stored directly in Db2 when a `MISMATCH` verification status is detected.

---

## Team Members & Credits

| Name | GitHub Handle | Role |
|---|---|---|
| **Prathamesh Patil** | [@prathamesh-lang](https://github.com/prathamesh-lang) | Cloud Systems & Backend Engineer |

