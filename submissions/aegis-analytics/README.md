# Aegis Analytics AI

> **One-Line Pitch:** An enterprise quantitative market intelligence, calibrated machine learning forecasting, and Web3 cryptographic verification platform powered by a comprehensive IBM Db2 AI Toolkit.

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)

---

## Problem Statement
In financial markets, quantitative machine learning models frequently suffer from three critical shortcomings:
1. **Uncalibrated Confidence**: Raw classification probabilities produced by tree ensembles or deep networks do not reflect true statistical likelihoods, leading to overconfident trades during volatile regimes.
2. **Lack of Downside Risk Guarantees**: Point estimates of return fail to capture distributional tail risk ($P(\text{Return} < -1\%)$ or $P(\text{Return} < -2\%)$), exposing portfolios to sudden market shocks.
3. **Database Silos & Lack of AI Ecosystem Interoperability**: Enterprise relational databases like IBM Db2 contain mission-critical financial records, yet modern AI agent frameworks (LangChain, CrewAI, LlamaIndex, Haystack) and dialect differences make seamless integration challenging.

**Target Audience:** Quantitative hedge funds, enterprise risk analysts, institutional traders, and database administrators seeking calibrated, verifiable AI forecasting.

---

## Solution Overview
**Aegis Analytics AI** solves these challenges by combining:
- **Dual-Head LightGBM Forecasting**: Simultaneous continuous return regression ($\hat{y}$) and direction classification ($y_{\text{up}}$) across multi-time horizons (`5m`, `15m`, `60m`, `1d`).
- **Mathematical Confidence & Risk Bounds**: Isotonic probability calibration guaranteeing accurate $p_{\text{up}}$, and distribution-free conformal prediction intervals guaranteeing $(1 - \alpha)$ statistical coverage (default 90%).
- **Full-Spectrum IBM Db2 AI Toolkit**: A comprehensive suite connecting IBM Db2 LUW to modern AI frameworks, providing Text-to-SQL agents, dbt in-database transformations, SQLGlot cross-dialect transpilation, semantic vector search, and a zero-Docker mock sandbox.
- **Web3 Cryptographic Verification**: EVM smart contracts (`PriceAnchor.sol` and `PredictionAudit.sol`) that anchor SHA-256 hashes of forecasts on-chain for tamper-proof audit trails.
- **Institutional AI Analyst**: Powered by Google Gemini 3.5 Flash for natural language quantitative briefings grounded in live telemetry.

---

## IBM Db2 Integration

Aegis Analytics AI features a dedicated, production-tested **IBM Db2 AI & Analytics Toolkit** (`db2_toolkit/`) delivering:

1. **Db2 Connection Manager (`connection.py`)**:
   - Unified connection handling supporting both native `ibm_db` and SQLAlchemy `ibm_db_sa`.
   - Automatic connection pooling, SSL certificate validation, and parameter sanitization.
   - **Zero-Docker Mock Fallback**: When a live Db2 server is unreachable, the system automatically routes to `mock_db2_sandbox.py`, allowing evaluators to run every test without spinning up a heavy container.

2. **SQLGlot Dialect Transpiler (`dialect_transpiler.py`)**:
   - Automatic cross-dialect transpilation translating PostgreSQL, MySQL, and SQLite queries into native IBM Db2 LUW syntax (`FETCH FIRST n ROWS ONLY`, `VARCHAR_FORMAT`, `CURRENT TIMESTAMP`).

3. **In-Database dbt Transformations (`dbt/`)**:
   - In-database ELT models executing directly on IBM Db2 to stage raw market bars (`stg_market_bars`) and compute downside tail-risk metrics (`fct_risk_metrics`).

4. **LangChain & CrewAI Text-to-SQL Agents**:
   - **LangChain SQL Agent (`langchain_agent.py`)**: Inspects Db2 table catalogs, autonomously formulates valid Db2 queries, and returns synthesized answers.
   - **CrewAI Suite (`crewai_agents.py`)**: Multi-agent team with dedicated Quantitative Analyst, Risk Officer, and Compliance Auditor collaborating over Db2 telemetry.

5. **Vector Search & RAG Frameworks**:
   - **LlamaIndex (`llamaindex_store.py`)**: Text node indexing and cosine vector retrieval against Db2 tables.
   - **Deepset Haystack 2.x (`haystack_pipeline.py`)**: DocumentStore implementation and extractive question-answering pipeline.

6. **Developer & IDE Tooling**:
   - Curated VS Code extension recommendations (`IBM.db2-for-luw`) and pre-configured connection profiles for local Docker and remote IBM Cloud Db2.
   - Langflow visual component export (`lfx-ibm`).

---

## AI / LLM Architecture

- **Primary Analytical Engine**: LightGBM gradient boosting dual-head model for real-time tabular price telemetry and cyclical time encodings (sine/cosine of hour and day).
- **Copilot LLM**: Google Gemini 3.5 Flash (`gemini-3.5-flash`), providing quantitative financial explanations, risk interval interpretation, and strategic checkups.
- **Agentic Workflow**:
  ```
  User Query ──> FastAPI (/ai/analyst) ──> Fetch Db2 Telemetry / Preds
                                                 │
                                                 ▼
  Markdown Briefing <── Gemini 3.5 Flash <── Enriched System Context
  ```
- **Fallback Architecture**: If external LLM access is unavailable, the system transparently falls back to an internal deterministic quantitative heuristic engine.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Database & Analytics** | IBM Db2 LUW (Docker / Cloud / Mock Sandbox), SQLAlchemy (`ibm_db_sa`), dbt |
| **AI Agents & RAG** | LangChain, CrewAI, LlamaIndex, Deepset Haystack 2.x, Langflow, SQLGlot |
| **Forecasting & ML** | LightGBM, Scikit-Learn (`IsotonicRegression`), Pandas, NumPy, Conformal Prediction |
| **Generative AI** | Google Gemini 3.5 Flash |
| **Backend REST API** | FastAPI, Uvicorn, Pydantic v2, HTTPX, Tenacity |
| **Frontend Applications** | React 19, TypeScript, Vite 8, Tailwind CSS v4, Recharts, Streamlit, Plotly |
| **Web3 & Blockchain** | Solidity 0.8.20, Hardhat, Web3.py, Sepolia / Polygon networks |

---

## Prerequisites
- Python 3.10+ (tested on Python 3.11 / 3.12 / 3.14)
- Node.js 18+ (for React frontend)
- Docker (optional — only required if running a live local IBM Db2 container)

---

## Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Uditrajput09/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission/submissions/aegis-analytics
```

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Install Python Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r src/requirements.txt
```

---

## Configuration

Edit `.env` to customize your environment:
```ini
# IBM Db2 Configuration
DB2_DATABASE=BLUDB
DB2_HOSTNAME=localhost
DB2_PORT=50000
DB2_PROTOCOL=TCPIP
DB2_UID=db2inst1
DB2_PWD=your_password
DB2_MOCK_FALLBACK=true    # Enables local mock sandbox when server is offline

# AI Copilot Key (Optional)
GEMINI_API_KEY=your_gemini_api_key
```

---

## Running the Project

### Option A: Run Full Automated Db2 Toolkit Suite
You can verify the entire 10-suite IBM Db2 AI Toolkit integration in seconds:
```bash
python tests/test_db2_toolkit.py
```
*Output: `✨ ALL 10 TEST SUITES PASSED CLEANLY (100% COVERAGE)`*

### Option B: Start FastAPI Backend
```bash
uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at `http://localhost:8000/docs`.

### Option C: Run Streamlit Executive Dashboard
```bash
streamlit run src/dashboard/app.py
```

---

## Testing & Verification

Aegis Analytics AI includes comprehensive unit and integration tests:

| Test Suite | Description | Status |
|---|---|---|
| **Test 1** | Connection Manager & Mock Sandbox Fallback | ✅ PASSED |
| **Test 2** | VS Code Extension Configuration & Connection Profiles | ✅ PASSED |
| **Test 3** | SQLGlot Cross-Dialect Transpiler | ✅ PASSED |
| **Test 4** | dbt Project, Profiles & In-Database Financial Models | ✅ PASSED |
| **Test 5** | LangChain Text-to-SQL Agent & Db2VectorStore | ✅ PASSED |
| **Test 6** | LlamaIndex Vector Store Integration | ✅ PASSED |
| **Test 7** | Deepset Haystack 2.x RAG Pipeline | ✅ PASSED |
| **Test 8** | CrewAI Multi-Agent Suite | ✅ PASSED |
| **Test 9** | Langflow Visual Flow Builder | ✅ PASSED |
| **Test 10** | FastAPI REST Endpoints (`/api/v1/db2/*`, `/ai/analyst`) | ✅ PASSED |

Run the test suite with:
```bash
python tests/test_db2_toolkit.py
```

---

## Screenshots & Demo
- **Live Repository**: [https://github.com/Uditrajput09/aegis-analytics-ai-system](https://github.com/Uditrajput09/aegis-analytics-ai-system)
- **Interactive Cybernetic Knowledge Graph**: Included in `docs/screenshots/` showcasing live directional synapses and pipeline isolation.

---

## Known Limitations & Future Roadmap
- **Live watsonx.data Integration**: Connect directly to watsonx.data Presto/Trino engines alongside standard Db2 OLTP.
- **Streaming Live WebSocket Oracles**: Stream continuous high-frequency tick data from decentralized price feeds directly into Db2 columnar tables.
- **Db2 Native Spatial & Graph Visualizer**: Leverage IBM Db2 Graph capabilities to visualize token flows and counterparty exposure matrices.

---

## Team Members & Credits
- **Udit Rajput** ([@Uditrajput09](https://github.com/Uditrajput09)) — Lead Quantitative Developer / Full Stack AI Engineer (Email: `uditrajput609@gmail.com`)

*Submitted for the **IBM Db2 TechX Summit 2026** Hackathon.*
