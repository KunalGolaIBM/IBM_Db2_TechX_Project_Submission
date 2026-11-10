# MediTwin AI — Implementation Plan

## Execution Sequence

### PHASE 0: Audit ✅
- [x] Inspect workspace
- [x] Check Python environment
- [x] Check Db2 availability
- [x] Check Docker/WSL2
- [x] Check API keys
- [x] Create audit documents

### PHASE 1: Environment Setup
- [ ] Install `ibm_db`, `langchain`, `langgraph`, `langchain-google-genai`
- [ ] Create `.env.example` and `.env` template
- [ ] Create `config/settings.py`
- [ ] Create `.gitignore`
- [ ] Create `requirements.txt`

### PHASE 2: Database Foundation
- [ ] Set up IBM Db2 (Docker or native)
- [ ] Create `db/schema.sql`
- [ ] Create `db/connection.py` with connection pooling
- [ ] Test real Db2 connection
- [ ] Execute schema creation

### PHASE 3: Data Layer
- [ ] Create `db/repository.py` — all CRUD operations
- [ ] Create `db/seed_demo_data.py` — synthetic patients and documents
- [ ] Seed demo patients
- [ ] Verify data in Db2

### PHASE 4: Document Processing
- [ ] Create `ingestion/pdf_parser.py`
- [ ] Create `ingestion/text_parser.py`
- [ ] Create `ingestion/validation.py` — Pydantic models
- [ ] Create sample synthetic PDF reports
- [ ] Test extraction

### PHASE 5: AI Extraction
- [ ] Create `ingestion/extraction.py` — LangChain structured extraction
- [ ] Create Pydantic output schemas
- [ ] Test with Gemini API
- [ ] Validate extraction accuracy

### PHASE 6: Human Review
- [ ] Create review UI page
- [ ] Implement approve/reject/edit workflow
- [ ] Wire to Db2 repository
- [ ] Add audit logging

### PHASE 7: LangGraph Workflow
- [ ] Create `graph/state.py` — typed state
- [ ] Create `graph/nodes.py` — workflow nodes
- [ ] Create `graph/workflow.py` — graph definition
- [ ] Implement ingestion pipeline
- [ ] Implement query pipeline

### PHASE 8: Timeline & Visualization
- [ ] Create `services/timeline_service.py`
- [ ] Build Plotly trend charts
- [ ] Patient workspace UI
- [ ] Metric filtering and comparison

### PHASE 9: Q&A Engine
- [ ] Create `services/retrieval_service.py`
- [ ] Create `services/answer_service.py`
- [ ] Parameterized query templates
- [ ] Evidence card display
- [ ] Safety checks

### PHASE 10: Security & Audit
- [ ] Create `services/audit_service.py`
- [ ] Implement all safety rules
- [ ] Add disclaimers
- [ ] Verify no SQL injection paths
- [ ] Verify no credential exposure

### PHASE 11: UI Polish
- [ ] Dashboard page
- [ ] Professional styling
- [ ] Navigation
- [ ] Responsive layout

### PHASE 12: Testing
- [ ] Write and run all 18 test categories
- [ ] Fix failures
- [ ] Generate test report

### PHASE 13: Documentation & Submission
- [ ] README.md
- [ ] architecture.md
- [ ] submission.json
- [ ] Screenshots
- [ ] Final verification

## Priority Order (Deadline Constraint)

Given the deadline is today, the implementation prioritizes a working end-to-end flow:

1. **Environment + Dependencies** (15 min)
2. **Database schema + connection** (30 min)
3. **Repository layer + seed data** (30 min)
4. **PDF extraction + Pydantic validation** (30 min)
5. **LangChain extraction** (30 min)
6. **LangGraph workflow** (45 min)
7. **Streamlit UI (all pages)** (60 min)
8. **Q&A engine** (30 min)
9. **Tests** (30 min)
10. **Documentation + submission files** (30 min)

