# MediTwin AI — Project Audit

**Date:** 2026-11-10
**Deadline:** 2026-11-10 17:00 IST (Db2Hack 2026)

---

## 1. Workspace State

| Item | Status |
|------|--------|
| Existing source code | ❌ None — greenfield project |
| Proposal PDF | ✅ `MediTwin_AI_Final_Proposal.pdf` (15 pages) |
| Git repository | ✅ Initialized fresh |
| `.env` / config files | ❌ None — must create |

---

## 2. Python Environment

| Item | Value |
|------|-------|
| Python version | 3.11.9 |
| pip version | 26.2.1 |
| Virtual env | Global (system Python) |

### Already Installed (relevant)

| Package | Version | Purpose |
|---------|---------|---------|
| streamlit | 1.66.1 | Frontend UI |
| plotly | 6.9.0 | Charts and visualizations |
| pymupdf | 1.28.2 | PDF extraction |
| pydantic | 2.13.4 | Data validation |
| pydantic-settings | 2.15.0 | Settings management |
| pytest | 9.1.1 | Testing |
| python-dotenv | 1.2.2 | Environment config |
| google-genai | 2.14.0 | Gemini API client |
| pandas | 3.0.3 | Data manipulation |
| numpy | 2.4.6 | Numerics |

### Missing — Must Install

| Package | Purpose | Available |
|---------|---------|-----------|
| ibm_db | IBM Db2 Python driver | ✅ Wheel for cp311-win_amd64 |
| langchain | AI framework (hackathon required) | ✅ PyPI |
| langchain-core | LangChain core | ✅ PyPI |
| langchain-google-genai | Gemini integration | ✅ PyPI |
| langgraph | Workflow orchestration | ✅ PyPI |

---

## 3. IBM Db2 Status

| Item | Status |
|------|--------|
| Db2 installed locally | ❌ Not found |
| Db2 service running | ❌ No service detected |
| Docker Desktop | ❌ Not installed |
| WSL2 | ❌ Not installed |
| Podman | ❌ Not installed |
| VirtualBox | ❌ Not on PATH (adapter detected in network config) |
| Hyper-V | ⚠️ Hypervisor detected — likely available |

**Critical path:** Docker Desktop must be installed to run Db2 Community Edition.
Alternatively, IBM Db2 Community Edition can be installed natively on Windows.

### Recommended Path
1. Install Docker Desktop (uses Hyper-V backend)
2. Pull `icr.io/db2_community/db2` image
3. Run Db2 container with mapped port 50000

### Fallback Path
1. Download IBM Db2 Community Edition Windows installer
2. Install natively

---

## 4. API Keys

| Key | Status |
|-----|--------|
| GEMINI_API_KEY | ❌ Not set |
| GOOGLE_API_KEY | ❌ Not set |

**Action:** User must provide a valid Gemini API key.

---

## 5. System Resources

| Resource | Value |
|----------|-------|
| CPU | Intel Core i5 12th Gen HX |
| GPU | NVIDIA RTX 3050 |
| RAM | 15.78 GB |
| Free disk | ~150 GB |
| OS | Windows |

Sufficient for Db2 Community Docker container + application.

---

## 6. Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| No Db2 instance available | **HIGH** | Install Docker Desktop + Db2 container |
| No Gemini API key | **HIGH** | User must provide key in `.env` |
| Deadline is today | **HIGH** | Prioritize MVP: ingest → review → timeline → Q&A |
| `ibm_db` installation issues on Windows | MEDIUM | Pre-built wheel confirmed available |
| Docker Desktop may require restart | MEDIUM | Plan around potential restart |
| OneDrive path may cause issues | LOW | Use short path aliases if needed |

---

## 7. Submission Requirements (Verified)

From official Db2Hack repository and submission page:

1. Fork `KunalGolaIBM/IBM_Db2_TechX_Project_Submission`
2. Create folder `submissions/meditwin-ai/`
3. Branch: `submission/meditwin-ai`
4. Required files: `README.md`, `architecture.md`, `submission.json`, `.env.example`
5. Include screenshots and demo
6. Open PR to upstream repository
7. Submit PR URL via Google Form
8. Post on LinkedIn tagging organizers

