# DB2 MedAudit — AI Clinical Test Verification & Lab Kickback Detection

An intelligent medical prescription audit platform powered by **IBM DB2** and **LangChain / Gemini**. It detects unnecessary medical tests recommended by doctors seeking diagnostic lab kickbacks, protecting patients from financial exploitation and medical overtreatment.

---

## Quick Start (Web Application)

### 1. Install & Run
```bash
# Install dependencies
npm install

# Run the full-stack development server (Express + React Vite)
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

The web app works immediately with 5 real-world pre-loaded clinical case studies and mock IBM DB2 data — no database setup required for the demo.

---

## Python LangChain & IBM DB2 Agent Setup

For full AI-powered auditing connected to a real IBM DB2 instance:

### 1. Install Python Packages
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r scripts/requirements.txt
```

### 2. Configure IBM DB2 Native Driver (`clidriver`)
`pip install ibm-db` downloads the native IBM CLI driver (`clidriver`). Set the library path:

**Linux / Docker:**
```bash
export IBM_DB_HOME=/usr/local/lib/python3.10/site-packages/clidriver
export LD_LIBRARY_PATH=$IBM_DB_HOME/lib:$LD_LIBRARY_PATH
```

**macOS:**
```bash
export IBM_DB_HOME=$(python3 -c "import site; print(site.getsitepackages()[0])")/clidriver
export DYLD_LIBRARY_PATH=$IBM_DB_HOME/lib:$DYLD_LIBRARY_PATH
```

**Windows PowerShell:**
```powershell
$env:IBM_DB_HOME = "C:\Python310\Lib\site-packages\clidriver"
$env:PATH += ";$env:IBM_DB_HOME\bin"
```

### 3. Run IBM DB2 with Docker (Local Database)
```bash
docker run -itd --name db2server \
  --restart=always \
  -e LICENSE=accept \
  -e DB2INST1_PASSWORD=db2password123 \
  -e DBNAME=MEDAUDIT \
  -p 50000:50000 \
  -p 50001:50001 \
  --privileged=true \
  ibmcom/db2:11.5.8.0
```
Then load the schema:
```bash
docker exec -i db2server su - db2inst1 -c "db2 connect to MEDAUDIT && db2 -tvf -" < scripts/schema_ibm_db2.sql
```

### 4. Run the LangChain Clinical Audit Agent
```bash
export GEMINI_API_KEY="your-gemini-api-key"
export DB2_HOST="localhost"
export DB2_PORT="50000"
export DB2_USER="db2inst1"
export DB2_PASS="db2password123"
export DB2_DB="MEDAUDIT"

python scripts/medaudit_langchain_agent.py
```

---

## Database Schema (IBM DB2)

Schema: `CLINICAL_INTELLIGENCE` | Tablespace: `TS_MEDAUDIT` (8K custom buffer pool)

| Table | Purpose |
|---|---|
| `CLINICAL_GUIDELINES` | NICE, WHO, ICMR evidence-based indicated and unwarranted tests per condition (7 conditions) |
| `DOCTORS` | Physician profiles with suspicion scores and unnecessary order rates (7 doctors) |
| `DIAGNOSTIC_LABS` | Lab registry with accreditation status, city, and markup % (6 labs) |
| `LAB_COMMISSION_CONTRACTS` | Documented doctor–lab kickback agreements with commission % (7 contracts) |
| `TEST_CATALOG` | Benchmark and fair-market pricing for 17 standard diagnostic tests |
| `AUDIT_LOGS` | Per-encounter audit trails with savings computed and kickback alert flag |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript + Vite + TailwindCSS 4 + Lucide React |
| Backend | Node.js 18 + Express + TypeScript |
| AI Agent | Python 3.10+ + LangChain + Google Gemini 1.5 Pro |
| Database | IBM DB2 Community Edition 11.5.8 (Docker) |
| DB Driver | `ibm_db` + `ibm_db_sa` + LangChain `SQLDatabaseToolkit` |
