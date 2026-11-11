# Cloud-Loop

> AI-Powered Student Opportunity Discovery Platform with IBM Db2 and Haystack AI.  
> IBM Db2 TechX Summit 2026 Submission.

---

## Problem

Undergraduate students and fresh graduates in technology face an overwhelming and fragmented opportunity landscape. High-impact tech opportunities—such as campus ambassador programs, specialized student developer programs, internships, fresher jobs, and open cloud certifications—are scattered across Discord servers, LinkedIn feeds, and disparate hiring portals.

Key pain points:
1. **Keyword Blindness**: Traditional keyword search misses conceptual matches (e.g. searching "cloud infrastructure" misses "AWS Student Developer Fellow").
2. **Hidden Eligibility Constraints**: Students waste hours applying for listings only to be disqualified by undisclosed graduation batch or degree filters.
3. **Black-Box Recommendations**: Existing job aggregators lack transparent explanations of why a student matches a given listing.

---

## Solution

**Cloud-Loop** centralizes student discovery by pairing **IBM Db2** as the unified transactional and vector data tier with **Haystack AI**:
- **Semantic Vector Discovery**: Uses `IBMDb2DocumentStore` and 384-dimensional dense vectors to match queries and student profiles by true semantic intent.
- **Explainable Match Engine**: Computes candidate match percentages and generates clear rationale lines based on exact overlapping competencies.
- **Application Pipeline Tracking**: Real-time status tracking (`Applied`, `Interviewing`, `Accepted`, etc.) with atomic `MERGE` upserts into IBM Db2.
- **Curated Dataset**: Pre-seeded with 106 verified student opportunities across jobs, internships, events, programs, and certifications.
- **Instant Demo Evaluation**: Supports `AUTH_MODE=demo` so evaluators can test the complete personalized platform instantly without third-party accounts.

---

## IBM Db2 Integration

### Edition & Driver
- **Edition**: IBM Db2 Community Edition (Docker `icr.io/db2_community/db2:12.1.2.0`) / IBM Db2 on Cloud.
- **Drivers / Connectors**:
  - `ibm-db-haystack (1.0.0)` for Haystack 2.x vector document storage and retriever pipelines.
  - `ibm_db (3.3.0)` for native relational operations and parameterized prepared statements.

### Schema & Tables (Schema: `CLOUDLOOP`)
- `CLOUDLOOP.OPPORTUNITY_KB`: Vector table initialized via `IBMDb2DocumentStore`, storing `VECTOR(384, FLOAT32)` embeddings with `COSINE` distance metric.
- `CLOUDLOOP.OPPORTUNITIES`: Relational catalog with columns for `ID`, `KIND`, `SLUG`, `TITLE`, `ORG`, `LOCATION`, `MODE`, `DEADLINE`, `POSTED`, `APPLY_URL`, `SOURCE`, `SKILLS`, `DESCRIPTION`, and `UPDATED_AT`.
- `CLOUDLOOP.TRACKED_OPPORTUNITIES`: Student application status and bookmark tracking (`USER_ID`, `OPPORTUNITY_ID`, `STATUS`, `BOOKMARKED`, `UPDATED_AT`).
- `CLOUDLOOP.NEWSLETTER_SUBSCRIBERS`: Email subscription list (`EMAIL`, `CREATED_AT`).
- `CLOUDLOOP.V_ACTIVE_OPPORTUNITIES`: View filtering opportunities where `DEADLINE IS NULL OR DEADLINE >= CURRENT DATE`.
- `IX_OPP_KIND_DEADLINE`: Compound B-Tree index on `(KIND, DEADLINE)`.

### Key Db2 Queries

**1. Application Tracking MERGE Upsert**
```sql
MERGE INTO CLOUDLOOP.TRACKED_OPPORTUNITIES AS target
USING (VALUES (?, ?, ?, ?)) AS source (USER_ID, OPPORTUNITY_ID, STATUS, BOOKMARKED)
ON (target.USER_ID = source.USER_ID AND target.OPPORTUNITY_ID = source.OPPORTUNITY_ID)
WHEN MATCHED THEN
  UPDATE SET STATUS = source.STATUS, BOOKMARKED = source.BOOKMARKED, UPDATED_AT = CURRENT TIMESTAMP
WHEN NOT MATCHED THEN
  INSERT (USER_ID, OPPORTUNITY_ID, STATUS, BOOKMARKED, UPDATED_AT)
  VALUES (source.USER_ID, source.OPPORTUNITY_ID, source.STATUS, source.BOOKMARKED, CURRENT TIMESTAMP);
```

**2. Newsletter Duplicate-Safe MERGE**
```sql
MERGE INTO CLOUDLOOP.NEWSLETTER_SUBSCRIBERS AS target
USING (VALUES (?)) AS source (EMAIL)
ON (target.EMAIL = source.EMAIL)
WHEN NOT MATCHED THEN
  INSERT (EMAIL, CREATED_AT) VALUES (source.EMAIL, CURRENT TIMESTAMP);
```

**3. Parameterized Pagination via FETCH FIRST and OFFSET**
```sql
SELECT * FROM CLOUDLOOP.OPPORTUNITIES
WHERE SOURCE != 'synthetic-demo' AND (? IS NULL OR LOWER(KIND) = LOWER(?))
ORDER BY UPDATED_AT DESC
OFFSET ? ROWS FETCH FIRST ? ROWS ONLY;
```

**4. Dashboard Aggregates on Active View**
```sql
SELECT KIND, COUNT(*) as CNT 
FROM CLOUDLOOP.V_ACTIVE_OPPORTUNITIES 
WHERE SOURCE != 'synthetic-demo' 
GROUP BY KIND;
```

---

## AI/LLM Architecture

- **Vector Framework**: Haystack AI 3.4.1 (`haystack-ai`, `ibm-db-haystack`).
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` generating 384-dimensional unit-normalized dense vectors.
- **Retrieval**: `IBMDb2EmbeddingRetriever` executing cosine similarity queries directly inside Db2.
- **Match Service**: Blends vector affinity (55%) with skill coverage (45%).
- **LLM Rationale**: Queries optional local Ollama (`llama3.2`) with a 1.5-second timeout; if unavailable, falls back gracefully to deterministic skill-overlap explanation with transparent provenance (`explanation_mode='deterministic'`).

---

## Tech Stack

- **Database**: IBM Db2 LUW 12.1.2.0, `ibm_db`, `ibm-db-haystack`.
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, Pydantic-Settings, Uvicorn, Pytest.
- **AI / Embeddings**: Haystack AI, Sentence-Transformers, PyTorch.
- **Frontend**: Next.js 16 (App Router), React 19, Tailwind CSS v4, Lucide Icons.
- **Authentication**: Dual-mode (Fixed demo user or Clerk).

---

## Prerequisites

- Docker and Docker Compose (recommended) OR
- Python 3.10+ and Node.js 20+ for local installation.

---

## Setup

```bash
# 1. Clone repository
git clone https://github.com/Ayushh-Sharmaa/Cloud-Loop.git
cd Cloud-Loop

# 2. Copy environment template
cp .env.example .env
```

---

## Configuration

Key variables in `.env`:
- `AUTH_MODE=demo` (enables zero-credential evaluation).
- `DB2_HOST=localhost`, `DB2_PORT=50000`, `DB2_DB=BLUDB`, `DB2_SCHEMA=CLOUDLOOP`.
- `INTERNAL_API_KEY=your_internal_api_key_here` (secures server-to-server calls).

---

## Run

### Using Docker Compose (All-in-one)
```bash
docker compose up -d
python src/ai-service/scripts/seed_db2.py
# Web app: http://localhost:3000
# AI Service OpenAPI docs: http://localhost:8000/docs
```

### Running Locally
```bash
# Terminal 1: AI Service
cd src/ai-service
python scripts/seed_db2.py
uvicorn main:app --port 8000 --reload

# Terminal 2: Web App
cd src/web
npm run dev
```

---

## Testing

```bash
# 1. Run AI Service pytest suite
cd src/ai-service
python -m pytest tests/ -v

# 2. Run Web static analysis
cd src/web
npx tsc --noEmit
npm run lint
```

---

## Screenshots

Visual documentation and walk-throughs are archived in [`docs/screenshots/`](docs/screenshots/):
- **Homepage & Search**: Semantic natural language search with kind filtering.
- **Dashboard**: Real-time status pipeline and one-click tracking updates.
- **Candidate Matcher**: Multi-factor scoring with explainable reasons.

---

## Honest Limitations

- **Host App Control Policy on Windows**: During local development on Windows 11, host Application Control policies blocked unsigned `.dll` C-extensions (`ibm_db` and `torch.dll`). Local unit testing ran against the verified fallback adapter; full live Db2 integration executes natively inside the Linux-based Docker container.
- **Live Scraper Removal**: Synthetic scraped generators that fabricated freshness metrics were intentionally decommissioned. The catalog exclusively serves 106 human-curated records.
- **Local LLM Dependency**: Ollama is optional; when not running locally, the system uses deterministic rationale generation without quality degradation.

---

## Credits

- **Author**: Ayush Sharma ([@Ayushh-Sharmaa](https://github.com/Ayushh-Sharmaa))
- **Event**: IBM Db2 TechX Summit 2026 Hackathon
- **Built with**: IBM Db2, Haystack AI (deepset), FastAPI, Next.js, and React.
