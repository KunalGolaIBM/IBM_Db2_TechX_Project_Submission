# Cloud Loop: AI-Powered Student Opportunity Intelligence Platform ⚡

> **Official Hackathon Submission for IBM Db2 TechX Summit 2026**  
> *Track: AI / RAG / Data Engineering / Career Tech*  
> *Hosted at GL Bajaj Group of Institutions, Mathura, in association with IBM, IIC, and NexaSphere.*

---

## 📌 Executive Summary

Every year, students miss life-changing programs, internships, and hackathons (such as Google Summer of Code, Microsoft Learn Student Ambassadors, and high-stipend internships) because opportunities are scattered across hundreds of portals and lack eligibility awareness.

**Cloud Loop** transforms opportunity discovery into an **AI-powered opportunity intelligence platform** anchored on **IBM Db2**:
1. **IBM Db2 Enterprise Schemas**: Complete relational tables (`OPPORTUNITIES`, `STUDENT_PROFILES`, `USER_OPPORTUNITY_TRACKING`, `INGESTION_RUNS`) with parameterized querying, foreign keys, and idempotent migrations.
2. **Dedicated FastAPI Backend**: Separate high-performance Python microservice handling data ingestion, Db2 transactions, 384-dimensional vector embeddings, and multi-factor student matching.
3. **Multi-Factor Student Recommendation Engine**: Academic eligibility verification (degree, study year, batch) combined with cosine similarity matching and skills overlap scoring.
4. **Transparent Match Rationales**: Grounded, verifiable explanations for why every opportunity matches the student.
5. **Next.js 16 + Tailwind CSS v4 UI**: Minimalist, futuristic editorial aesthetic in **Midnight Black (`#0B0B0C`)**, **Pure White (`#FFFFFF`)**, and **Lime Green (`#C6F432`)** with 0 horizontal scroll.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([Student / Developer]) -->|Next.js 16 App Router UI| Frontend[Cloud Loop Web Client]
    
    subgraph "Frontend Layer (Next.js 16)"
        Frontend --> Hero[Homepage & Natural Language Search]
        Frontend --> Dashboard[Student Career Dashboard & Profile]
        Frontend --> Feed[Opportunity Explorer (Jobs, Internships, Events, Programs)]
        Frontend --> NextAPI[Secure Next.js API Proxy (/api/v1/*)]
    end

    subgraph "Backend Services Layer (FastAPI Python)"
        NextAPI -->|REST API v1| FastAPI[FastAPI Backend :8000]
        FastAPI --> OppService[Opportunity Service]
        FastAPI --> RecService[Recommendation Service]
        FastAPI --> IngestService[Data Ingestion Pipeline]
        FastAPI --> VectorEngine[384-dim SentenceTransformers Engine]
    end

    subgraph "Data & Persistence Layer"
        OppService --> Repo[Repository Layer]
        RecService --> Repo
        IngestService --> Repo
        
        Repo -->|Parameterized SQL| Db2[(IBM Db2 Enterprise Database)]
        Repo -.->|High-Availability Fallback| LocalDB[(Local Unified Database)]
    end
```

---

## 🚀 Key Features

### 1. IBM Db2 Dual-Layer Relational Schemas
- **OPPORTUNITIES**: Complete metadata (organization, type, category, skills, eligibility, deadline, URL, source provenance).
- **STUDENT_PROFILES**: Verified student academic credentials, year of study, target batch, and technical skills.
- **USER_OPPORTUNITY_TRACKING**: Personal pipeline tracking (saved, applied, under review) with deadline alerts.
- **INGESTION_RUNS**: Comprehensive metrics tracking inserted, updated, and rejected records.

### 2. Multi-Factor Recommendation Engine
- **Academic Eligibility Pass/Fail**: Enforces degree and graduation batch prerequisites.
- **Technical Skills Overlap**: Up to 35 points based on direct matches with user profile.
- **384-Dimensional Semantic Similarity**: `sentence-transformers/all-MiniLM-L6-v2` vector representation of student aspirations against opportunity specifications.
- **Transparent Match Explanations**: Plain-English rationale detailing exact skills and academic eligibility criteria matched.

### 3. Asynchronous Data Ingestion Pipeline
- Processes over **3,770+ real opportunities** from curated scrapers across Google, LinkedIn, Unstop, and developer programs.
- URL validation, normalization, and deduplication.

---

## ⚡ Quick Start Guide

### 1. Start the FastAPI Python Backend
```bash
cd cloud-loop-app
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Ingest Opportunities into Db2
```bash
python backend/scripts/run_ingestion.py
```

### 3. Run Backend Test Suite
```bash
python -m pytest backend/tests -v
```

### 4. Start the Next.js Frontend
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000).

---

## 🏆 Evaluation Alignment

| Rubric Criteria | Cloud Loop Implementation |
|---|---|
| **IBM Db2 Integration** | Parameterized queries, multi-table relational schema, connection lifecycle, and transaction isolation. |
| **Architectural Quality** | Decoupled 3-tier architecture: FastAPI Python backend + Next.js 16 frontend + IBM Db2 data layer. |
| **Real-World Impact** | Indexes 3,770+ live verified student opportunities solving the discovery gap. |
| **AI Innovation** | 384-dim vector embeddings + deterministic eligibility verification + transparent match explainer. |
| **Design & Accessibility** | Midnight/Lime high-contrast palette, zero horizontal scroll, mobile responsive, WCAG compliant. |

