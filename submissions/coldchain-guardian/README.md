# ColdChain Guardian

**Agentic AI Platform for Predictive Cold-Chain Risk Management**

An IBM Db2-powered system that uses LangGraph workflows and CrewAI collaborative agents to monitor cold-chain shipments, detect temperature violations, assess risk, and generate human-approved corrective recommendations.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Database | IBM Db2 (Community Edition / Docker) |
| Backend | Python 3.11 · FastAPI · uvicorn |
| AI Workflow | LangGraph (deterministic orchestration) |
| AI Reasoning | CrewAI · Google Gemini (collaborative analysis) |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Recharts |
| DB Driver | ibm_db |

---

## Project Structure

```
submissions/coldchain-guardian/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app + CORS + router registration
│   │   ├── agents/                  # LangGraph node agents + CrewAI
│   │   │   ├── monitoring.py
│   │   │   ├── incident.py
│   │   │   ├── risk_assessment.py
│   │   │   ├── recommendation.py
│   │   │   └── crew_analysis.py     # CrewAI 3-agent crew + graceful fallback
│   │   ├── database/
│   │   │   ├── db.py                # IBM Db2 connection + query helpers
│   │   │   ├── audit.py             # Audit log helper
│   │   │   ├── seed_data.py
│   │   │   └── run_schema.py
│   │   ├── models/
│   │   │   └── recommendation.py    # Pydantic models
│   │   ├── routes/
│   │   │   ├── dashboard.py         # GET /api/dashboard/
│   │   │   ├── products.py          # GET /api/products/
│   │   │   ├── shipments.py         # GET /api/shipments/
│   │   │   ├── incidents.py         # GET/POST /api/incidents/
│   │   │   ├── recommendations.py   # GET/POST/PATCH /api/recommendations/
│   │   │   ├── readings.py          # POST /api/readings/
│   │   │   ├── workflow.py          # POST /api/workflow/run/{reading_id}
│   │   │   └── crew.py              # POST /api/crew/analyse/{incident_id}
│   │   └── workflow/
│   │       ├── graph.py             # LangGraph StateGraph
│   │       └── state.py             # WorkflowState TypedDict
│   ├── requirements.txt
│   ├── .env                         # Actual credentials (not committed)
│   └── .env.example                 # Template
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ShipmentsPage.tsx
│   │   │   ├── IncidentsPage.tsx
│   │   │   ├── RiskAnalysisPage.tsx
│   │   │   ├── RecommendationsPage.tsx
│   │   │   └── WorkflowPage.tsx
│   │   ├── components/
│   │   │   ├── StatCard.tsx
│   │   │   ├── SeverityBadge.tsx
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── ErrorMessage.tsx
│   │   │   └── CrewAnalysisPanel.tsx # Shared CrewAI findings panel
│   │   ├── api.ts                   # Typed API client
│   │   ├── App.tsx                  # Router + sidebar layout
│   │   ├── vite-env.d.ts            # Vite client types (import.meta.env)
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── database/
    ├── schema.sql
    └── audit.py
```

---

## Setup Instructions

### Prerequisites
- IBM Db2 running (Docker or Community Edition)
- Python 3.11+
- Node.js 18+

### 1. Configure Backend Environment

```bash
cd submissions/coldchain-guardian/backend
cp .env.example .env
# Edit .env — set DB2_HOST, DB2_DATABASE, DB2_USER, DB2_PASSWORD
# Optional AI credentials (any one): GEMINI_API_KEY / GOOGLE_API_KEY,
# OPENAI_API_KEY, or CREWAI_API_KEY (+ CREWAI_MODEL). Without them the
# system runs in deterministic fallback mode.
```

### 2. Install Backend Dependencies

```bash
cd submissions/coldchain-guardian/backend
pip install -r requirements.txt
```

### 3. Run Database Schema (first time only)

```bash
python -m app.database.run_schema
python -m app.database.seed_data
```

### 4. Start Backend

```bash
cd submissions/coldchain-guardian/backend
uvicorn app.main:app --reload --port 8000
```

The API is now available at: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

### 5. Install Frontend Dependencies

```bash
cd submissions/coldchain-guardian/frontend
npm install
```

### 6. Start Frontend

```bash
npm run dev
```

Frontend runs at: `http://localhost:5173`

The frontend reads `VITE_API_URL` (defaults to `http://localhost:8000`). To point it at
another backend host/port, set it before starting:

```bash
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

---

## Environment Variables

Backend (`backend/.env`, template in `.env.example`):

| Variable | Required | Purpose |
|---|---|---|
| `DB2_HOST` / `DB2_DATABASE` / `DB2_USER` / `DB2_PASSWORD` | yes | IBM Db2 connection |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | no | Native Gemini provider for CrewAI |
| `GEMINI_MODEL` | no | Gemini model id (default `gemini/gemini-2.0-flash`) |
| `OPENAI_API_KEY` | no | Native OpenAI provider for CrewAI |
| `CREWAI_API_KEY` / `CREWAI_MODEL` | no | Generic CrewAI override (native provider model id) |

Frontend:

| Variable | Required | Purpose |
|---|---|---|
| `VITE_API_URL` | no | Backend base URL (default `http://localhost:8000`) |

No credentials are embedded in frontend code; the API key lives only in the backend environment.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/` | Dashboard statistics |
| GET | `/api/products/` | All products |
| GET | `/api/shipments/` | All shipments |
| GET | `/api/shipments/{id}/readings` | Sensor readings for a shipment |
| GET | `/api/incidents/` | All incidents |
| POST | `/api/incidents/detect` | Detect temperature anomalies |
| GET | `/api/recommendations/` | All recommendations |
| POST | `/api/recommendations/generate/{incident_id}` | Generate recommendations |
| PATCH | `/api/recommendations/{rec_id}/approval` | Approve/reject recommendation |
| POST | `/api/readings/` | Insert sensor reading + run workflow |
| POST | `/api/workflow/run/{reading_id}` | Run LangGraph workflow |
| POST | `/api/crew/analyse/{incident_id}` | Run CrewAI analysis |

---

## AI Architecture

```
Sensor Reading
     │
     ▼
 LangGraph Workflow
     │
     ├─ Monitoring Agent    → Temperature status, deviation
     │
     ├─ Incident Agent      → Create/reuse incident (duplicate-safe)
     │
     ├─ Risk Assessment     → Deterministic score (0–100), reuse existing
     │
     ├─ CrewAI (optional)   → Collaborative AI reasoning (fallback-safe)
     │    ├─ Risk Analyst
     │    ├─ Domain Expert
     │    └─ Recommendation Specialist
     │
     └─ Recommendation      → Rule-based actions (duplicate-safe)
               │
               ▼
         Human Approval Required
```

### CrewAI Agents

| Agent | Role |
|---|---|
| **Cold Chain Risk Analyst** | Analyses temperature deviation, product damage risk, urgency |
| **Cold Chain Domain Expert** | Diagnoses root causes, containment measures, compliance |
| **Recommendation Specialist** | Prioritises corrective actions with justifications |

> **Note:** CrewAI uses a native LLM provider (Gemini by default via the `crewai[google-genai]` extra; OpenAI also supported). Set any of `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `OPENAI_API_KEY`, or `CREWAI_API_KEY`. Without credentials — or if the provider client cannot be constructed — the crew node returns a deterministic fallback built only from stored Db2 facts and the workflow still completes successfully. CrewAI never changes the authoritative deterministic risk score and never auto-approves recommendations.

---

## Frontend Pages

| Page | Path | Description |
|---|---|---|
| Dashboard | `/` | Stats, risk chart, recent incidents |
| Shipments | `/shipments` | All shipments + sensor reading charts |
| Incidents | `/incidents` | Incident table + anomaly detection |
| AI Risk Analysis | `/risk` | CrewAI incident analysis |
| Recommendations | `/recommendations` | Approve/reject recommendations |
| Workflow | `/workflow` | Trigger full LangGraph workflow |

---

## IBM Db2 Features Used

- **Relational tables** with IDENTITY columns and foreign keys
- **Parameterised queries** via ibm_db driver
- **IDENTITY_VAL_LOCAL()** for generated key retrieval
- **CURRENT TIMESTAMP** for audit trails
- **Indexes** on shipment_id, incident_id foreign keys
- **SYSIBM.SYSDUMMY1** for conditional inserts

---

## Dependencies

Backend (`backend/requirements.txt`): `fastapi`, `uvicorn[standard]`, `ibm_db`,
`python-dotenv`, `langgraph`, `pydantic`, and `crewai[google-genai]==1.15.39`.
The `google-genai` extra supplies CrewAI's native Gemini provider; `litellm` is not
required for native providers.

Frontend (`frontend/package.json`): React 18, react-dom, react-router-dom v6,
recharts, lucide-react; dev tooling Vite 5, TypeScript 5, Tailwind CSS 3.

---

## Reliability & Data-Safety Guarantees

- Re-running a workflow reuses the existing incident and risk assessment
  (`risk_reused=true`); a persisted assessment never reports `risk_assessment_id=0`.
- Repeated runs create no duplicate incidents, assessments, or recommendations.
- Workflow failures surface as `FAILED` with an `error`; a CrewAI fallback is not a
  workflow failure.
- Dashboard pending-recommendation count uses `APPROVAL_STATUS = 'PENDING'`.
- Recommendation timestamps are serialized to ISO-8601; approval/rejection state is
  preserved across runs.
- No tables dropped, truncated, or recreated; seeded records preserved; all SQL
  parameterised through the shared Db2 helpers.

---

## Verified Flows

Executed against a live IBM Db2 instance and the running frontend:

- Backend `/health` and Db2 connection OK; frontend builds (`tsc && vite build`) and serves.
- `POST /api/workflow/run/283` → SUCCESS; incident reused; assessment reused (id 1,
  score 57.5); no duplicate recommendations.
- `POST /api/incidents/detect` → 7 violations, 0 new incidents, 7 duplicates skipped.
- `POST /api/crew/analyse/1` → fallback findings (no credentials configured); 404 for
  an unknown incident.
- `PATCH /api/recommendations/{id}/approval` → APPROVED/REJECTED persisted and list
  refreshed; invalid status → 400; test mutations reverted to the seeded state.
- All six frontend pages exercised in a browser against real Db2 data; no console errors.

---

## Hackathon Notes

- All data persisted in IBM Db2 — single source of truth
- No data fabricated — API serves only real Db2 records
- Human approval required for all recommendations
- Duplicate prevention at incident, risk assessment, and recommendation level
- CrewAI is additive — deterministic logic is authoritative
