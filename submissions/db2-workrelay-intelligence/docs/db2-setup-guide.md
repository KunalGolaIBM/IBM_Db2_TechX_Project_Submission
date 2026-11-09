# IBM Db2 Community Edition Deployment & Operations Guide
## Db2 WorkRelay Intelligence — Dell Latitude 5400 Reference Implementation

This guide documents the verified, end-to-end local deployment of **IBM Db2 Community Edition 12.1.5.0** alongside **Db2 WorkRelay Intelligence**. It details the exact resource allocation, headless container architecture, initialization milestones, schema management, and troubleshooting solutions developed and tested on resource-constrained enterprise hardware.

---

## 1. Verified Hardware & Host Environment

The implementation and integration tests were conducted on the following host configuration:

- **Host Machine:** Dell Latitude 5400
- **Processor:** Intel Core i7-8665U (4 physical cores / 8 threads @ 1.90 GHz base, up to 4.80 GHz turbo)
- **Host Memory:** 8 GB DDR4 RAM
- **Host Storage:** 512 GB NVMe SSD (Windows C: partition with ~97 GB free, historical measurement recorded at initial deployment)
- **Operating System:** Windows 11 Enterprise 24H2
- **Subsystem:** Windows Subsystem for Linux (WSL2), running **Ubuntu 22.04.5 LTS**
- **Init System:** Ubuntu systemd enabled natively (`/etc/wsl.conf` configured with `[boot] systemd=true`)
- **Container Engine:** Headless Docker Engine 29.9.3 (running directly as a native Linux service inside WSL2, without Docker Desktop)
- **Compose Tooling:** Docker Compose v5.7.0
- **Python Environment:** Python 3.10.12 in a dedicated virtual environment with native `ibm_db 3.3.0` and `langchain-core 1.7.6`

> [!NOTE]
> **Why Headless Docker Engine on WSL2?**
> Standard Docker Desktop introduces substantial virtualization and Electron GUI memory overhead (often 1.5–2.5 GB RAM). By deploying native Docker Engine directly inside Ubuntu WSL2 with systemd, all memory is reserved for the Linux kernel, the Db2 engine, and the application runtime. Docker Desktop is **not required**.

---

## 2. Tested WSL2 Resource Configuration (`.wslconfig`)

Running IBM Db2 Community Edition (which allocates dedicated buffer pools, instance shared memory, lock lists, and transaction log buffers) on an 8 GB physical host requires balanced resource limits so Windows and WSL2 do not exhaust available memory.

### Configuration

Create or modify `%USERPROFILE%\.wslconfig` in Windows:

```ini
[wsl2]
memory=5GB
processors=4
swap=6GB
```

### Rationale
- **`memory=5GB`:** Grants the WSL2 VM sufficient physical RAM headroom for the Linux OS (~400 MB), the Db2 container (~1.5–3.5 GB peak during database creation), and the FastAPI application (~200 MB), leaving ~3 GB for Windows 11 system tasks.
- **`processors=4`:** Exposes all 4 physical cores to the container engine, optimizing concurrent compilation, table creation, and index builds.
- **`swap=6GB`:** During first-time database provisioning (`CREATE DATABASE testdb`), Db2 briefly experiences peak memory demand. The 6 GB swap space absorbs transient memory spikes without triggering Linux OOM (Out-Of-Memory) killer crashes. Once initialized, steady-state Db2 container memory usage settles down to ~1.5 GB.

> [!IMPORTANT]
> This `.wslconfig` configuration is the **tested development configuration** for an 8 GB Dell Latitude 5400 laptop. It is not intended as a universal production recommendation. Always back up your existing Windows `.wslconfig` (e.g. to `%USERPROFILE%\.wslconfig.bak`) and run `wsl --shutdown` from PowerShell to restart WSL2 cleanly before proceeding.

---

## 3. Container Specification & Deployment

### Image Details
- **Registry / Image:** `icr.io/db2_community/db2:latest`
- **Db2 Version:** IBM Db2 Community Edition 12.1.5.0 (Linux x86_64)
- **Container Name:** `db2server`
- **Default Service Port:** `50000`

### Step 1: Prepare Environment File (`.env.db2`)

Create a local, git-ignored environment file `submissions/db2-workrelay-intelligence/.env.db2`:

```ini
LICENSE=accept
DB2INSTANCE=db2inst1
DB2INST1_PASSWORD=your_strong_unique_password
DBNAME=testdb
BLU=false
ENABLE_ORACLE_COMPATIBILITY=false
```

> [!WARNING]
> Keep `.env.db2` strictly out of version control. The repository's root `.gitignore` ignores all `.env*` files by default (except `.env.example`). Set file permissions to `chmod 600 .env.db2`.
>
> **Password Synchronization:** The password specified in `DB2INST1_PASSWORD` here must match the `DB2_PASSWORD` configured in the application runtime environment file (`.env`).

### Step 2: Create Persistent Docker Volume

```bash
docker volume create db2_data
```

The named volume `db2_data` is mounted to `/database` inside the container, preserving database tablespaces, catalogs, logs, and instance configuration across container restarts.

### Step 3: Launch the Db2 Container

Execute the verified container startup command from Ubuntu WSL2 (run from the **repository root** so the path `--env-file submissions/db2-workrelay-intelligence/.env.db2` resolves correctly):

```bash
docker run -d \
  --name db2server \
  --privileged=true \
  -p 127.0.0.1:50000:50000 \
  --env-file submissions/db2-workrelay-intelligence/.env.db2 \
  -v db2_data:/database \
  icr.io/db2_community/db2:latest
```
*(Note: If executing directly from within the `submissions/db2-workrelay-intelligence` subdirectory, use `--env-file .env.db2`).*

#### Launch Parameter Explanation:
- `--privileged=true`: Used in this tested Ubuntu WSL2 deployment to grant the container access to required Linux IPC shared memory segments (`shmget`, `shmat`), semaphores, and asynchronous I/O settings. While running in privileged mode was the verified approach on this local WSL2 development environment, this is not presented as a universal requirement; production deployments or locked-down enterprise platforms (such as Red Hat OpenShift or Kubernetes) typically evaluate platform-specific security context constraints (SCCs), specialized container capabilities, or custom security profiles determined by infrastructure and security teams according to their platform policies, rather than full `--privileged` access.
- `-p 127.0.0.1:50000:50000`: Recommended for fresh deployments to bind the standard Db2 TCP/IP communications port exclusively to the host loopback interface (`127.0.0.1`), ensuring database access for local development tools while preventing unintended exposure across external network interfaces.
  *Note on the current deployment:* The existing, verified `db2server` container on this Dell machine was initially launched with `-p 50000:50000` (verified via `docker port db2server` as `50000/tcp -> 0.0.0.0:50000`) and has been preserved without container recreation. Fresh deployments should use the loopback binding above whenever network isolation is desired.
- `-v db2_data:/database`: Ensures stateful database persistence on the Docker storage volume.
- `--restart`: Intentionally omitted during initial testing to prevent container restart loops if configuration parameters need adjustment.

---

## 4. Monitoring Initialization & Health Verification

First-time startup provisions the instance directory, configures the database manager (`db2inst1`), builds the `TESTDB` database catalogs, and configures default buffer pools. On the Dell Latitude 5400 NVMe SSD, this process takes approximately 5–8 minutes.

### Step 1: Follow Container Logs

```bash
docker logs -f db2server
```

Wait until you see the definitive IBM setup completion banner:

```text
################################################################################
(*) Setup has completed.
################################################################################
```

### Step 2: Verify Db2 Instance Health via CLI

Run a direct probe inside the container to confirm the database is active and accepting connections:

```bash
docker exec -it db2server su - db2inst1 -c "db2 connect to testdb && db2 list tables for schema db2inst1"
```

Expected output:
```text
   Database Connection Information

 Database server        = DB2/LINUXX8664 12.1.5.0
 SQL authorization ID   = DB2INST1
 Local database alias   = TESTDB
```

---

## 5. Schema Initialization

Db2 WorkRelay Intelligence organizes incident triage, chronological audit trails, remediation actions, and runbook knowledge documents into four relational tables with seven indexes.

### Relational Schema (`src/app/db/schema_db2.sql`)

```sql
-- 1. Incidents Table
CREATE TABLE incidents (
    id VARCHAR(32) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description CLOB(1M) NOT NULL,
    service VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    current_step VARCHAR(100) NOT NULL,
    workflow VARCHAR(100),
    resolution CLOB(1M),
    escalation_reason CLOB(1M),
    retry_count INT DEFAULT 0 NOT NULL,
    metadata CLOB(1M),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 2. Chronological Event Audit Log
CREATE TABLE incident_events (
    event_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id VARCHAR(32) NOT NULL,
    event VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL,
    step VARCHAR(100) NOT NULL,
    details CLOB(1M),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_event_incident FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

-- 3. Diagnostic & Remediation Actions Log
CREATE TABLE incident_actions (
    action_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    status VARCHAR(30) NOT NULL,
    result CLOB(1M),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT fk_action_incident FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

-- 4. Operational Runbook Knowledge Documents
CREATE TABLE incident_knowledge_docs (
    doc_id VARCHAR(64) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    service VARCHAR(100) NOT NULL,
    content CLOB(1M) NOT NULL,
    resolution_steps CLOB(1M) NOT NULL,
    metadata CLOB(1M),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- B-Tree Performance Indexes
CREATE INDEX idx_incidents_status ON incidents (status);
CREATE INDEX idx_incidents_service ON incidents (service);
CREATE INDEX idx_incidents_severity ON incidents (severity);
CREATE INDEX idx_incidents_created ON incidents (created_at DESC);
CREATE INDEX idx_events_incident ON incident_events (incident_id, timestamp);
CREATE INDEX idx_actions_incident ON incident_actions (incident_id);
CREATE INDEX idx_docs_service ON incident_knowledge_docs (service);
```

### Running the Schema Initializer

From the `submissions/db2-workrelay-intelligence` directory:

```bash
# 1. Activate virtual environment (from submissions/db2-workrelay-intelligence)
source .venv/bin/activate
# (Note: if using a workspace-root virtual environment instead, activate via: source ../../.venv/bin/activate)

# 2. Source database credentials safely
set -a
source .env
set +a

# 3. Execute database initializer
PYTHONPATH=src python src/app/db/init_db.py
```

Expected output:
```text
Initializing database... Mode: ibm_db
Executing native IBM Db2 schema (schema_db2.sql)...
Database initialized and baseline incident created.
```

The initializer verifies connection to Db2, executes the DDL script to generate tables and indexes, and persists an initial synthetic baseline record (`INC-BASELINE-01`) with an audit event (`INCIDENT_REGISTERED`).

---

## 6. Live Integration Testing

Db2 WorkRelay Intelligence features two dedicated integration tests in `tests/test_db2_live.py` that validate live database connectivity and complete CRUD/audit operations against IBM Db2.

Execute the full test suite with live credentials loaded:

```bash
cd submissions/db2-workrelay-intelligence
set -a && source .env && set +a
PYTHONPATH=src pytest tests/ -v
```

### Verified Test Results:
```text
============================== test session starts ==============================
platform linux -- Python 3.10.12, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/yemisi/projects/IBM_Db2_TechX_Project_Submission/submissions/db2-workrelay-intelligence
collected 33 items

tests/test_ai_retrieval.py::test_knowledge_retriever_seeded_runbooks PASSED [  3%]
tests/test_ai_retrieval.py::test_runbooks_converted_to_langchain_documents PASSED [  6%]
tests/test_ai_retrieval.py::test_langchain_retriever_direct_invocation PASSED [  9%]
tests/test_ai_retrieval.py::test_knowledge_retriever_query_matching PASSED [ 12%]
tests/test_ai_retrieval.py::test_knowledge_retriever_irrelevant_query_handling PASSED [ 15%]
tests/test_ai_retrieval.py::test_knowledge_retriever_custom_ingest PASSED [ 18%]
tests/test_ai_retrieval.py::test_coordinator_workflow_uses_langchain_retriever PASSED [ 21%]
tests/test_api.py::test_health_endpoint PASSED                           [ 24%]
tests/test_api.py::test_create_and_retrieve_incident PASSED              [ 27%]
tests/test_api.py::test_auto_classification_on_creation PASSED           [ 30%]
tests/test_api.py::test_list_incidents PASSED                            [ 33%]
tests/test_api.py::test_patch_incident_status PASSED                     [ 36%]
tests/test_api.py::test_structured_error_handling_not_found PASSED       [ 39%]
tests/test_api.py::test_knowledge_query_endpoint PASSED                  [ 42%]
tests/test_api.py::test_knowledge_ingest_endpoint PASSED                 [ 45%]
tests/test_db2_internals.py::test_db2_row_mapping_from_tuples PASSED     [ 48%]
tests/test_db2_internals.py::test_db2_row_mapping_none_and_dict PASSED   [ 51%]
tests/test_db2_internals.py::test_db2_connection_failure_handling PASSED [ 54%]
tests/test_db2_internals.py::test_native_schema_db2_file_exists_and_parses PASSED [ 57%]
tests/test_db2_internals.py::test_audit_log_persistence_on_status_change PASSED [ 60%]
tests/test_db2_internals.py::test_db2_timestamp_formatting_utc PASSED    [ 63%]
tests/test_db2_internals.py::test_db2_timestamp_formatting_non_zero_offset PASSED [ 66%]
tests/test_db2_internals.py::test_db2_timestamp_formatting_microseconds_preserved PASSED [ 69%]
tests/test_db2_internals.py::test_db2_timestamp_none_and_native_handling PASSED [ 72%]
tests/test_db2_live.py::test_live_db2_connection_probe PASSED            [ 75%]
tests/test_db2_live.py::test_live_db2_schema_and_crud PASSED             [ 78%]
tests/test_db2_repository.py::test_create_and_get_incident PASSED        [ 81%]
tests/test_db2_repository.py::test_list_incidents_filtering PASSED       [ 84%]
tests/test_db2_repository.py::test_patch_incident PASSED                 [ 87%]
tests/test_db2_repository.py::test_parameterized_query_safety PASSED     [ 90%]
tests/test_models.py::test_incident_creation_and_defaults PASSED         [ 93%]
tests/test_models.py::test_incident_record_event PASSED                  [ 96%]
tests/test_models.py::test_incident_request_models PASSED                [100%]

======================== 33 passed in 66.13s (0:01:06) =========================
```

---

## 7. Operational Troubleshooting & Solutions

### 1. SQL0180N: Timestamp Syntax Error
- **Symptom:** Live Db2 integration tests failed during row insertion with:
  ```text
  ibm_db_dbi.DataError: SQL0180N The syntax of the string representation of a datetime value is incorrect. SQLSTATE=22007 SQLCODE=-180
  ```
- **Root Cause:** Standard Python `datetime.isoformat()` produces ISO 8601 strings containing a literal `T` separator and timezone offset (e.g., `2026-11-08T10:23:26.552234+00:00`). While SQLite and PostgreSQL accept ISO 8601 strings with timezone suffixes, IBM Db2 standard `TIMESTAMP` columns require the strict format:
  ```text
  YYYY-MM-DD HH:MM:SS.ffffff
  ```
  Db2 rejects ISO strings with `T` or `+00:00`/`Z` timezone offsets unless using specialized `TIMESTAMP WITH TIME ZONE` datatypes.
- **Solution:** Implemented the centralized normalization helper `format_db2_timestamp` in `src/app/db/repository.py`:
  ```python
  def format_db2_timestamp(dt: datetime | None) -> str | None:
      """
      Format a datetime object into a standard Db2/ANSI SQL timestamp string.
      Normalizes timezone-aware timestamps to UTC and preserves microsecond precision:
      YYYY-MM-DD HH:MM:SS.ffffff
      """
      if dt is None:
          return None
      if dt.tzinfo is not None:
          dt = dt.astimezone(timezone.utc)
      return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
  ```
  All incident timestamps (`created_at`, `updated_at`, `started_at`, `completed_at`, `timestamp`) are normalized through this helper prior to parameter binding in SQL queries. Datetime strings retrieved from storage are parsed via the companion `parse_db_timestamp` helper.

### 2. WSL2 Memory Thrashing & OOM during Container Startup
- **Symptom:** Container creation hung or terminated abruptly with exit code 137 (OOM Killer) during database generation on machines with 8 GB physical RAM.
- **Root Cause:** Default WSL2 settings allocated only 2 GB of swap memory. Initial Db2 database provisioning requires transient memory peaks to format system tablespaces and configure default buffer pools.
- **Solution:** Configured `%USERPROFILE%\.wslconfig` to allocate `swap=6GB`. The additional swap space allows the Linux kernel to swap out inactive processes during the 5-minute setup window. Once initialization finishes, steady-state Db2 container memory usage remains well within ~1.5 GB.

### 3. Starlette 1.0+ Route Discovery Incompatibility
- **Symptom:** Custom `ApiTestClient` failed with `ValueError: Route GET /health not found` when running API unit tests.
- **Root Cause:** In Starlette 1.0+ / FastAPI 0.110+, routers included via `app.include_router()` are wrapped inside `_IncludedRouter` objects rather than exposing flat `Route` objects directly in `app.routes`.
- **Solution:** Updated `ApiTestClient.__init__` in `tests/test_api.py` to recursively traverse both direct `Route` objects and nested `r.original_router.routes` or `r.routes`, preserving backwards and forwards compatibility.

---

## 8. Security & Environment Best Practices

1. **Credentials Isolation:** Never commit `.env` or `.env.db2` to version control. The repository `.gitignore` explicitly excludes all `.env` files except `.env.example`.
2. **File Permissions:** On Linux / WSL2, restrict environment file read permissions:
   ```bash
   chmod 600 submissions/db2-workrelay-intelligence/.env
   chmod 600 submissions/db2-workrelay-intelligence/.env.db2
   ```
3. **Safe Parameterized Queries:** All SQL statements in `src/app/db/repository.py` use positional parameter bindings (`?`). Dynamic user inputs are never concatenated directly into SQL strings.
4. **Offline CI Safety:** In resource-limited CI/CD environments where a 4 GB Db2 container cannot be spawned, setting `DB2_USE_MOCK=true` enables the configured in-memory SQLite compatibility mode, ensuring that unit tests, data model validation, and LangChain knowledge retrieval tests run cleanly without live database dependencies.
