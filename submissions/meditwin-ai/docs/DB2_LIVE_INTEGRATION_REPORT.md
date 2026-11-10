# MediTwin AI — IBM Db2 Live Server Audit Report

**Audit Timestamp:** 2026-11-10 02:05:00 IST  
**Auditor:** Senior Database & Systems Engineer  
**Component:** IBM Db2 Community Edition (Server & Driver)  
**Status:** **BLOCKED (Host Environment — Administrator Action Required)**  

---

## 1. Executive Summary & Verification Verdict

| Verification Item | Tested Command / Tool | Status | Real Evidence / Findings |
| :--- | :--- | :---: | :--- |
| **IBM Db2 Python Driver** | `import ibm_db` | **VERIFIED** | `ibm_db` v3.3.0 pre-compiled for Python 3.11 Windows 64-bit loaded successfully. |
| **IBM CLI Driver (`clidriver`)** | `clidriver\bin\db2level.exe` | **VERIFIED** | `DB2 v12.1.4000.3294`, code release `SQL12014`, level identifier `02050110`, copy `IBM Data Server Driver For ODBC and CLI`. |
| **Windows Db2 Service** | `Get-Service -Name "*db2*"` | **FAILED / NOT FOUND** | No native Windows Db2 service or daemon installed in Windows Service Control Manager. |
| **Db2 Running Process** | `Get-Process *db2*` | **FAILED / NOT RUNNING**| Zero processes running matching `db2`, `db2sysc`, or `db2fmp`. |
| **Port 50000 Listener** | `Test-NetConnection -Port 50000` | **FAILED / CLOSED** | TCP connect to `::1:50000` and `127.0.0.1:50000` failed. `TcpTestSucceeded: False`. |
| **Docker Engine** | `Get-Command docker` | **NOT INSTALLED** | Docker Desktop is not installed on the host OS. |
| **WSL2 Subsystem** | `wsl.exe -l -v` | **NOT INSTALLED** | `The Windows Subsystem for Linux is not installed.` |
| **Overall Integration Verdict** | Live Db2 Connection | **BLOCKED** | Client driver is 100% verified. Server daemon is unavailable on host. |

---

## 2. Technical Evidence & Audit Logs

### 2.1 Native CLI Driver Verification
```powershell
C:\Users\Vipul Mishra\AppData\Local\Programs\Python\Python311\Lib\site-packages\clidriver\bin\db2level.exe
```
**Output:**
```text
DB21085I  This instance or install (instance name, where applicable: "*") uses 
"64" bits and DB2 code release "SQL12014" with level identifier "02050110".
Informational tokens are "DB2 v12.1.4000.3294", "special_38029", 
"DYN2606270632WIN64_38029", and Fix Pack "0".
Product is installed at 
"C:\Users\Vipul Mishra\AppData\Local\Programs\Python\Python311\Lib\site-packages\clidriver" 
with DB2 Copy Name "IBM Data Server Driver For ODBC and CLI".
```

### 2.2 Server Listener Probe on Port 50000
```powershell
Test-NetConnection -ComputerName localhost -Port 50000 -InformationLevel Detailed
```
**Output:**
```text
WARNING: TCP connect to (::1 : 50000) failed
WARNING: TCP connect to (127.0.0.1 : 50000) failed

ComputerName            : localhost
RemoteAddress           : ::1
RemotePort              : 50000
NameResolutionResults   : ::1
                          127.0.0.1
TcpTestSucceeded        : False
```

### 2.3 Python ibm_db Connection Probe
```python
from db.connection import test_connection
res = test_connection()
print(res)
```
**Output:**
```python
{'status': 'failed', 'message': 'Could not connect to IBM Db2. Check credentials and server status.'}
```

---

## 3. Strict Compliance Policy

> **NO MOCK OR SQLITE SUBSTITUTION:**  
> In strict accordance with the IBM Db2Hack requirements and project rules, **MediTwin AI does not use SQLite, in-memory dictionaries, or mock databases as production substitutes.** When the IBM Db2 server is unreachable, the system displays a transparent "Driver Ready / Server Offline" status badge and gracefully informs the user without pretending a live connection exists.

---

## 4. Manual Installation Steps (Requires Windows Administrator Privileges)

Because the Windows host lacks Docker Desktop, WSL2, and native Db2 Server, an active Db2 server requires manual setup with administrator permissions. The user must choose one of the following two paths:

### Option A: Via Docker Desktop (Recommended for IBM Db2Hack)
1. **Download Docker Desktop for Windows:**  
   Navigate to [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) and run `Docker Desktop Installer.exe` as Administrator.
2. **Enable WSL2:**  
   Open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   ```
   Reboot Windows when prompted.
3. **Launch Docker Desktop** and start the official IBM Db2 Community Edition container:
   ```powershell
   docker run -d --name db2 -p 50000:50000 --privileged=true -e DB2INST1_PASSWORD=your_password -e LICENSE=accept icr.io/db2_community/db2
   ```
4. **Create the Database & Tables:**
   ```powershell
   docker exec -ti db2 su - db2inst1 -c "db2 create database MEDITWIN"
   docker exec -ti db2 su - db2inst1 -c "db2 -tf /path/to/schema.sql"
   ```

### Option B: Via Native IBM Db2 Community Edition Windows Installer
1. **Download the IBM Db2 Community Edition for Windows (ZIP):**  
   From the official IBM Db2 trials portal.
2. **Run `setup.exe` as Administrator:**
   - Choose "Install New".
   - Select "Db2 Server Edition".
   - Provide local Windows account credentials for the `db2admin` service account.
   - Set service startup type to "Automatic" (creates Windows service `DB2-0` or `DB2COPY1`).
3. **Open the DB2 Command Window:**
   ```cmd
   db2start
   db2 create database MEDITWIN
   db2 connect to MEDITWIN
   db2 -tvf "c:\Users\Vipul Mishra\OneDrive\Desktop\HACKATHON UNSTOP\db\schema.sql"
   ```
