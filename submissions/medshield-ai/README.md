# MEDSHIELD AI

**Agentic medication safety screening with IBM Db2**

MEDSHIELD AI is a hackathon prototype for medication-safety decision support. It screens a submitted medication list for three transparent demo rules: known interaction pairs, duplicate medication entries and medications matching a patient's recorded allergies. A LangGraph workflow normalizes inputs, runs checks and assigns a review priority. Reports are persisted in the configured database.

> **Clinical safety:** This is an educational prototype, not a medical device, diagnosis, prescription, or substitute for a licensed clinician/pharmacist. Its tiny sample rule set is incomplete and must never be used to make real treatment decisions. Use synthetic data only.

## Features
- FastAPI REST API and browser dashboard.
- LangGraph multi-step screening workflow.
- IBM Db2 persistence through the official `ibm_db` Python driver when `DB2_DSN` is configured.
- SQLite fallback for a quick local demonstration when no Db2 DSN is configured. The fallback is not a substitute for demonstrating actual Db2 integration.
- Patient, medication, allergy, interaction and safety-report table design.

## Run locally (quick demo)
Requires Python 3.10+.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env and leave DB2_DSN blank for SQLite demo
uvicorn src.backend.main:app --reload
```
Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

Try the default demo: `warfarin, ibuprofen` (the sample interaction rule should produce HIGH review priority). Try `lisinopril, potassium` for a MODERATE finding. Add `penicillin` to the allergy field and include it in medications to test allergy matching.

## Configure IBM Db2
1. Provision an IBM Db2 Community Edition / Db2 on Cloud database and create a database user.
2. Install the platform prerequisites for the `ibm_db` driver if prompted.
3. Copy `.env.example` to `.env`; set `DB2_DSN` to your connection string, for example:

```text
DATABASE=BLUDB;HOSTNAME=<host>;PORT=50000;PROTOCOL=TCPIP;UID=<user>;PWD=<password>;SECURITY=SSL;
```

4. Export environment variables before starting the API. PowerShell example:

```powershell
$env:DB2_DSN="DATABASE=BLUDB;HOSTNAME=...;PORT=50000;PROTOCOL=TCPIP;UID=...;PWD=...;SECURITY=SSL;"
uvicorn src.backend.main:app --reload
```

The API creates the prototype tables and attempts to seed a fictional patient and two sample interaction rules at startup. Verify `/api/health` reports `IBM Db2`. If it reports SQLite, the application is in demo-fallback mode and meaningful Db2 use has **not** yet been demonstrated. Review `src/backend/db.py` and adapt DDL to the exact Db2 service/version if needed.

## API
- `GET /api/health` — backend and database status.
- `GET /api/demo-patient` — fictional sample patient.
- `POST /api/analyze` — body: `{"patient_id":"DEMO-001","medications":["warfarin","ibuprofen"],"allergies":[]}`.
- `GET /api/reports` — recent persisted safety reports.

## Repository layout
```text
medshield-ai/
├── README.md
├── architecture.md
├── submission.json
├── .env.example
├── requirements.txt
├── src/
│   ├── backend/       # FastAPI, LangGraph and Db2 adapter
│   └── frontend/      # Responsive dashboard
└── docs/screenshots/  # Add genuine screenshots of your running app
```

## Limitations / next steps
- Interaction knowledge is a deliberately tiny hard-coded demo set, not a comprehensive drug database.
- No dosage, renal/hepatic function, pregnancy, age-specific dosing or clinical guideline evaluation is performed.
- Replace demo rules with a verified, licensed drug knowledge source and clinical governance before any real-world use.
- Add authentication, authorization, audit logging, encryption, robust Db2 migrations, and clinician review before production.
- The current implementation is a transparent LangGraph rules workflow; it does not call an external LLM.
