# MEDSHIELD AI — Architecture

## Goal
Provide an explainable prototype workflow for flagging a small set of medication safety patterns and persisting review results. It is decision support for demonstration only, not clinical advice.

## Components
1. **Browser dashboard** (`src/frontend/index.html`): collects a fictional patient identifier, medication names and known allergies; displays the API result and saved reports.
2. **FastAPI service** (`src/backend/main.py`): validates requests, exposes health, analysis and report endpoints, and coordinates persistence.
3. **LangGraph workflow** (`src/backend/agent.py`): `normalize → screen → assess`. The screening node checks exact sample interaction pairs, duplicate entries and allergy matches. The assessment node assigns HIGH / MODERATE / LOW review priority.
4. **Database adapter** (`src/backend/db.py`): uses `ibm_db` when `DB2_DSN` is configured; otherwise uses SQLite for local demonstration. Db2 mode must be verified through `/api/health`.
5. **Persistence model**: PATIENTS, MEDICATIONS, PATIENT_MEDICATIONS, ALLERGIES, DRUG_INTERACTIONS and SAFETY_REPORTS.

## Data flow
```text
User enters synthetic patient + medication list
                  |
                  v
        FastAPI POST /api/analyze
                  |
                  v
       LangGraph normalize node
                  |
                  v
        LangGraph screening node <--- demo rules / allergy list
                  |
                  v
        LangGraph risk assessment
                  |
                  v
     Persist report through database adapter
                  |
                  v
         JSON result to dashboard
```

## Db2 integration
The `DB2_DSN` environment variable selects the IBM Db2 driver path. The application creates the six tables and writes a safety report after each analysis. The SQLite path exists only to make the user interface runnable without cloud credentials. A successful local SQLite run does not prove Db2 integration; a judge-ready Db2 demonstration must show `/api/health` returning `IBM Db2` and successful persisted reports.

## Safety, privacy and limitations
Only fictional demonstration records are included. No real patient data should be entered. The rule set is intentionally incomplete and cannot establish that a medication regimen is safe. All findings require qualified clinical review. The prototype has no authentication or production security controls.
