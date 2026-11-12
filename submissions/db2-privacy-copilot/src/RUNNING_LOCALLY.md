# Running Locally (Without Docker)

## 🎉 Your App is Running!

Since Docker/Db2 are not available (Application Control policy blocking ibm_db DLL), the app is running in **MOCK MODE** with in-memory demo data.

---

## 📱 Access the Applications

### Streamlit UI (Dashboard)
**URL**: http://localhost:8501

Features available:
- 📊 Dashboard with metrics
- 🔍 Schema Discovery (mock 4-table clinic DB)
- 🏷️ PII Classification (demo data)
- ✅ Consent Management
- 🗑️ Rights Requests (dry-run planning)
- 📝 Audit Log with chain verification
- ❓ Help & Guide page

### FastAPI Backend  
**URL**: http://localhost:8000/docs

Interactive API documentation with all endpoints:
- `/health` - Component health check
- `/discovery/{schema}` - Schema discovery
- `/classification/{schema}` - PII classification
- `/consent/*` - Consent management
- `/requests/*` - Rights requests
- `/audit/*` - Audit log

**Test Tokens** (use in "Authorize" button):
- `VIEWER_TOKEN` from `.env` - Read-only access
- `ANALYST_TOKEN` from `.env` - Can create requests
- `DPO_TOKEN` from `.env` - Can approve and execute

---

## 🗂️ Mock Data

The in-memory database contains:

**Tables**:
- `PATIENT` (3 records) - Aryan, Priya, Rahul
- `APPOINTMENT` (3 records)
- `PRESCRIPTION` (2 records)
- `LAB_REPORT` (2 records)

**Classification**: Columns are classified on-demand using regex patterns and name heuristics.

**Consent**: 2 pre-loaded consent records (TREATMENT, RESEARCH).

**Retention Rules**: 4 rules (ANONYMISE/RETAIN for each table).

All data resets when you restart the servers.

---

## 🔄 Restarting the Services

If you need to restart:

### Stop:
```bash
# Press Ctrl+C in each terminal, or:
# Find process IDs
netstat -ano | findstr ":8000"
netstat -ano | findstr ":8501"
# Kill by PID
taskkill /PID <PID> /F
```

### Start:
```bash
cd c:\Users\ranea\Downloads\db2-privacy-copilot

# Terminal 1 - API
.venv\Scripts\activate
.venv\Scripts\python.exe -m uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - UI
.venv\Scripts\activate
.venv\Scripts\python.exe -m streamlit run ui/app.py --server.port 8501
```

---

## 🐳 Running with Real Db2 (Docker)

When Docker is available:

1. Set `DB_MOCK=0` in `.env`
2. Start Db2:
   ```bash
   docker compose up -d
   docker compose logs -f db2  # wait 5-10 min for initialization
   ```
3. Bootstrap:
   ```bash
   python app/bootstrap.py
   python eval/seed.py
   ```
4. Restart API/UI (they'll auto-detect Db2 is available)

---

## ✨ Demo Workflows

### 1. Discovery
1. Go to http://localhost:8501
2. Click "🔍 Discovery"
3. Click "🔄 Scan Schema"
4. See 4 tables, 18 columns, 3 foreign keys

### 2. Classification
1. Click "🏷️ Classification"
2. Click "🔍 Run Classification"
3. See EMAIL, PHONE, NAME, DOB detection
4. Check confidence scores

### 3. Erasure Planning
1. Click "🗑️ Rights Requests"
2. Enter subject ID: `1`
3. Click "📋 Generate Plan"
4. See 4-step plan (RETAIN appointments/prescriptions/labs, ANONYMISE patient)
5. Note: No actual deletion (dry-run only)

### 4. Consent Management
1. Click "✅ Consent Management"
2. Grant consent: Patient 1, MARKETING, dates
3. View consents for Patient 1
4. Withdraw consent

### 5. Audit Log
1. Click "📝 Audit Log"
2. Click "🔍 Verify Chain"
3. See "✓ Chain is INTACT"
4. Browse recent activity

### 6. API Testing
1. Go to http://localhost:8000/docs
2. Click "Authorize", enter the value of `ANALYST_TOKEN` from `.env`
3. Try `GET /discovery/DB2INST1`
4. Try `POST /requests` with `{"subject_id": 1}`

---

## 📦 What's Installed

Dependencies in `.venv`:
- ✅ FastAPI + Uvicorn (API server)
- ✅ Streamlit (UI)
- ✅ Pydantic (validation)
- ✅ NetworkX (FK graph)
- ✅ Faker (synthetic data)
- ✅ sentence-transformers (PII classification)
- ❌ crewai (skipped — optional agent orchestration)
- ⚠️ ibm_db (installed but DLL blocked by Application Control)

---

## 🚀 Next Steps

### For Demo/Development:
- ✅ Mock mode works perfectly for UI/UX testing
- ✅ All core functionality is exercisable
- ✅ No Docker/IBM client needed

### For Production:
1. Install Docker Desktop
2. Allow IBM Db2 DLL in Application Control policy
3. Follow QUICKSTART.md or DEPLOYMENT.md
4. Set `DB_MOCK=0` in `.env`

---

## 🐛 Troubleshooting

### Port already in use:
```bash
# Find what's using the port
netstat -ano | findstr ":8000"
netstat -ano | findstr ":8501"

# Kill the process
taskkill /PID <PID> /F
```

### Import errors:
```bash
# Reinstall in venv
.venv\Scripts\activate
pip install -e .
```

### UI not loading:
- Check http://localhost:8501 is accessible
- Clear browser cache
- Try incognito/private window

### API 422 errors:
- Check request body matches schema in `/docs`
- Pydantic validation is strict

---

## 📚 Documentation

- **README.md** - Project overview
- **QUICKSTART.md** - Full setup with Docker
- **CODE_QUALITY.md** - Code audit and improvements
- **DEPLOYMENT.md** - Production CI/CD setup
- **Help in UI** - Click "❓ Help & Guide" in the sidebar

---

**Status**: ✅ Both servers running in MOCK mode  
**API**: http://localhost:8000  
**UI**: http://localhost:8501  
**GitHub**: https://github.com/dreameterftw/db2-privacy-copilot
