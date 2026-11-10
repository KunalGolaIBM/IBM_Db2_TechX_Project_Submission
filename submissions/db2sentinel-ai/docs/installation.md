# Db2Sentinel AI — Installation & Setup Guide

This guide walks through configuring and running **Db2Sentinel AI** on your development workstation or server.

---

## 1. System Requirements

- **Operating System:** Windows 10/11, macOS (x86/ARM), or Ubuntu 22.04+
- **Python:** Python 3.11 or higher
- **Node.js:** Node.js 18.x or 20.x LTS with npm
- **Database (Optional for local test mode, required for live testing):** IBM Db2 Community Edition 11.5+ (Docker or bare-metal)

---

## 2. Repository & Working Directory

From the root of the hackathon repository:
```bash
cd submissions/db2sentinel-ai
```

---

## 3. Python Environment Setup

Create and activate a dedicated virtual environment:

### Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Key Python Packages Installed:
- `ibm_db` (3.3.0) — Official IBM Db2 native driver
- `langchain` (1.4.9) — Mandatory submission framework
- `langgraph` (1.2.20) — Multi-agent state orchestration
- `fastapi` & `uvicorn` — Enterprise REST API
- `pydantic` & `pydantic-settings` — Data validation

---

## 4. Environment Configuration

Copy the example environment configuration:
```bash
cp .env.example .env
```

Edit `.env` to configure your settings:
```env
# Db2 Connection Parameters
DB2_HOST=localhost
DB2_PORT=50000
DB2_DATABASE=SENTINELDB
DB2_USER=db2inst1
DB2_PASSWORD=YourSecurePassword
DB2_SECURITY=SSL

# AI Provider Keys (Optional: deterministic fallback works without keys)
GEMINI_API_KEY=your_gemini_api_key_here
# or OPENAI_API_KEY=your_openai_key_here
```

---

## 5. IBM Db2 Database Setup

### Option A: Running via Docker (Recommended)
You can start IBM Db2 Community Edition using the provided `docker-compose.yml`:
```bash
docker-compose up -d
```

Wait ~2 minutes for the database engine to finish initialization, then verify the container:
```bash
docker ps
# Logs should show: (*) All databases are now active.
docker logs -f db2-sentinel
```

### Option B: Local Relational Emulation (Offline / Fast Demo Mode)
If Docker or a live Db2 instance is not available during presentation or evaluation, Db2Sentinel AI automatically switches to its high-fidelity local relational store. No configuration changes are required!

### Initializing the Db2 Schema:
Run the initialization script to create the 6 enterprise security tables:
```bash
python scripts/initialize_db.py
```
Or execute the DDL directly via Db2 Command Line Processor (CLP):
```bash
db2 -tvf database/schema.sql
db2 -tvf database/indexes.sql
```

Verify database connectivity:
```bash
python scripts/check_db_connection.py
```

---

## 6. Starting the Backend API

Start the FastAPI application with Uvicorn:
```bash
# From submissions/db2sentinel-ai:
python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Swagger UI Documentation:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/api/health`

---

## 7. Starting the React Security Command Centre

In a new terminal window, navigate to the frontend directory:
```bash
cd src/frontend
npm install
npm run dev
```

Open your browser to:
`http://localhost:5173`

The dashboard will automatically connect to the FastAPI backend at `http://localhost:8000`.

---

## 8. Seeding Demo Telemetry & Running Live Simulation

To seed baseline data and verify the end-to-end multi-agent workflow from the CLI:
```bash
# Seed initial telemetry
python scripts/seed_demo_data.py

# Run complete end-to-end incident investigation test
python scripts/run_demo.py
```
