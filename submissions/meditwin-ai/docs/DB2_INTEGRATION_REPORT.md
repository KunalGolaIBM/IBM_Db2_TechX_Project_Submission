# MediTwin AI — IBM Db2 Integration Report (Phase 2)

**Audit Timestamp:** 2026-11-10 00:50:00 IST  
**Auditor:** Senior Database & Systems Engineer  
**Database Technology:** IBM Db2 Community Edition (Target v12.1.x)  
**Client Driver:** `ibm_db` 3.3.0 with official IBM Data Server Driver for ODBC and CLI (Release `SQL12014`, DB2 v12.1.4)  

---

## 1. Executive Summary & Verification Verdict

| Verification Item | Result | Evidence / Details |
|---|---|---|
| **IBM Db2 Python Driver** | ✅ **VERIFIED** | `ibm_db` v3.3.0 pre-compiled for `cp311-win_amd64` loaded successfully. |
| **IBM CLI Driver (`clidriver`)** | ✅ **VERIFIED** | `db2level.exe` executed. Version: `DB2 v12.1.4000.3294`, Code release `SQL12014`, Level `02050110`. |
| **Server Connection (`localhost:50000`)** | ❌ **BLOCKED / FAILED** | Port 50000 closed. Connection attempt threw `SQL30082N` (SQLSTATE `08001`, SQLCODE `-30082`). |
| **Root Cause** | ⚠️ **MISSING SERVER** | Neither Docker Desktop, WSL2, nor Native Windows Db2 Server daemon is installed on the host OS. |
| **Overall Integration Status** | **BLOCKED ON HOST SERVER INSTALLATION** | Driver & repository prepared; requires active Db2 instance to run live transactions. |

---

## 2. Driver & System Verification Evidence

### 2.1 IBM Data Server Driver Identification
Executed embedded driver utility:
```powershell
C:\Users\Vipul Mishra\AppData\Local\Programs\Python\Python311\Lib\site-packages\clidriver\bin\db2level.exe
```
Output:
```text
DB21085I  This instance or install (instance name, where applicable: "*") uses 
"64" bits and DB2 code release "SQL12014" with level identifier "02050110".
Informational tokens are "DB2 v12.1.4000.3294", "special_87349", 
"DYN2606270632WIN64_87349", and Fix Pack "0".
Product is installed at 
"C:\Users\Vipul Mishra\AppData\Local\Programs\Python\Python311\Lib\site-packages\clidriver" 
with DB2 Copy Name "IBM Data Server Driver For ODBC and CLI".
```

### 2.2 Host Listener & Connection Attempt
Executed TCP and socket probe:
```powershell
Test-NetConnection -ComputerName localhost -Port 50000
```
Output:
```text
WARNING: TCP connect to (::1 : 50000) failed
WARNING: TCP connect to (127.0.0.1 : 50000) failed
TcpTestSucceeded : False
```

Executing `test_connection()` from Python:
```python
from db.connection import test_connection
res = test_connection()
# Result:
# {'status': 'failed', 'message': 'Could not connect to IBM Db2. Check credentials and server status.'}
# Db2 error: [IBM][CLI Driver] SQL30082N Security processing failed with reason "17" ("UNSUPPORTED FUNCTION"). SQLSTATE=08001 SQLCODE=-30082
```

---

## 3. Host Prerequisites Status

| Host Prerequisite | Status | Details |
|---|---|---|
| **Docker Desktop** | ❌ Not Installed | `docker` command not recognized in PowerShell. |
| **WSL2** | ❌ Not Installed | `wsl.exe -l -v` returned: `The Windows Subsystem for Linux is not installed.` |
| **Podman** | ❌ Not Installed | `podman` command not found. |
| **Windows Db2 Service**| ❌ Not Installed | No Windows service matching `*db2*` or `*IBM*` found in service registry. |

---

## 4. Required Resolution Steps to Enable Live Server

To bring up the actual IBM Db2 Community Edition server, one of the following two standard deployment paths must be completed:

### Option A: Via Docker Desktop (Recommended for IBM Db2Hack)
1. **Download and Install Docker Desktop for Windows:**  
   Download from: `https://www.docker.com/products/docker-desktop/`  
   *(Select WSL2 or Hyper-V backend during installation and restart laptop if prompted).*
2. **Start Docker Desktop.**
3. **Pull and Run the Official IBM Db2 Community Edition Container:**
   ```bash
   docker run -d --name db2 -p 50000:50000 --privileged=true \
     -e DB2INST1_PASSWORD=your_secure_password \
     -e LICENSE=accept \
     icr.io/db2_community/db2
   ```
4. **Update `.env`:**
   ```ini
   DB2_HOST=localhost
   DB2_PORT=50000
   DB2_DATABASE=MEDITWIN
   DB2_USER=db2inst1
   DB2_PASSWORD=your_secure_password
   DB2_SCHEMA=MEDITWIN
   ```

### Option B: Via Remote IBM Cloud or Hackathon-Provided Db2 Instance
If the hackathon committee provides a remote hosted Db2 instance, update `.env` with the remote host and credentials:
```ini
DB2_HOST=db2-hackathon.cloud.ibm.com
DB2_PORT=50000
DB2_DATABASE=BLUDB
DB2_USER=your_assigned_username
DB2_PASSWORD=your_assigned_password
DB2_SCHEMA=MEDITWIN
```

---

## 5. Live Database Integration Test Suite

The integration test `tests/integration/test_db2_live.py` is configured to execute against a live Db2 database to verify:
1. `test_live_db2_connection()`: Validates genuine `ibm_db.connect()` handshake.
2. `test_live_schema_ddl()`: Runs `db/schema.sql` and verifies tables `PATIENT`, `DOCUMENT`, `OBSERVATION`, `TIMELINE_EVENT`, `AUDIT_LOG`.
3. `test_live_patient_crud()`: Creates and reads `DEMO-001`.
4. `test_live_duplicate_document_prevention()`: Verifies `(patient_id, source_hash)` unique constraint rejects duplicate files.
5. `test_live_cross_patient_integrity()`: Confirms foreign key rejection when inserting an observation for a document belonging to another patient.
6. `test_live_atomic_review_transaction()`: Confirms observation review and audit log commit atomically.
7. `test_live_transaction_rollback()`: Confirms error triggers immediate rollback without partial commits.
8. `test_live_sql_injection_defense()`: Confirms malicious SQL payloads remain harmless literal parameters.

**Current Test Status:** Fails honestly with connection error until the local container or remote instance is started.

