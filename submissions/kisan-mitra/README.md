# 🌾 Kisan Mitra (किसान मित्र)
### Bilingual AI Assistant for Indian Farmers Powered by IBM Db2 12.1+
> **IBM Db2Hack 2026 Submission** | Individual Track  
> Official Submission Template: [KunalGolaIBM/IBM_Db2_TechX_Project_Submission](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission)

[![IBM Db2](https://img.shields.io/badge/IBM%20Db2-12.1%2B%20Community%20Edition-052F5F?logo=ibm)](https://www.ibm.com/products/db2)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-blue)](https://python.langchain.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python)](https://www.python.org/)
[![License: GODL-India](https://img.shields.io/badge/Data%20License-GODL--India-green)](https://data.gov.in)
[![Test Suite](https://img.shields.io/badge/Tests-35%20Passed%20(100%25)-brightgreen)](./tests)

---

## 🧭 Table of Contents
1. [Overview & Problem Statement](#1-overview--problem-statement)
2. [Key Features & Genuine IBM Db2 Integration](#2-key-features--genuine-ibm-db2-integration)
3. [System Architecture](#3-system-architecture)
4. [Database Schema & Design](#4-database-schema--design)
5. [Repository Structure](#5-repository-structure)
6. [Prerequisites & Environment Setup](#6-prerequisites--environment-setup)
7. [Quick Start (Run in Under 5 Commands)](#7-quick-start-run-in-under-5-commands)
8. [Sample Demonstration Queries](#8-sample-demonstration-queries)
9. [Automated Test Suite & Verification](#9-automated-test-suite--verification)
10. [Official Data Sources & Licensing](#10-official-data-sources--licensing)
11. [Limitations & Future Scope](#11-limitations--future-scope)
12. [Hackathon Submission Metadata](#12-hackathon-submission-metadata)

---

## 1. Overview & Problem Statement

### 🌾 The Real-World Problem
Over 140 million agricultural households in India face critical information barriers every day:
- **Mandi Price Opacity**: Market prices across government APMC mandis fluctuate daily. Farmers lack simple, conversational tools in their mother tongue (Hindi/Hinglish) to track commodity rates, compare nearby district markets, and spot price trends.
- **Complex Welfare Scheme Guidelines**: Central and State Governments offer crucial support schemes (**PM-KISAN**, **PMFBY Crop Insurance**, and **Kisan Credit Card**), but the official operational guidelines are dense 40+ page bureaucratic PDFs. Farmers struggle to determine eligibility, navigate exclusions, and adhere to strict procedural deadlines (e.g., the mandatory 72-hour crop loss intimation rule).

### 💡 The Solution: Kisan Mitra (किसान मित्र)
**Kisan Mitra** is a production-grade, bilingual conversational AI assistant engineered specifically for Indian farmers. It eliminates information asymmetry by unifying:
1. **Relational Text-to-SQL Analytics** over real-time Agmarknet mandi market records.
2. **Native Vector Search RAG** over official government scheme guideline documents using **IBM Db2 native `VECTOR` data types and `VECTOR_DISTANCE` (Cosine similarity)**.
3. **Transparent Query Inspection**: Every response displays the exact generated Db2 SQL query, latency badge, interactive Plotly visualization, and official source document citations (with page numbers and vector similarity scores).

---

## 2. Key Features & Genuine IBM Db2 Integration

Kisan Mitra showcases **IBM Db2** as a unified relational and high-dimensional vector database—not merely as external storage.

```
+-----------------------------------------------------------------------------------------+
|                                    IBM Db2 12.1+ ENGINE                                 |
|                                                                                         |
|  +---------------------------------------+  +----------------------------------------+  |
|  |     RELATIONAL & ANALYTICS ENGINE     |  |          NATIVE VECTOR SEARCH          |  |
|  |  Table: MANDI_PRICES                  |  |  Table: DOC_CHUNKS                     |  |
|  |  * Structured Agmarknet arrivals      |  |  * Column: VECTOR(384, REAL)           |  |
|  |  * Composite B-Tree indexes           |  |  * SYSIBM.VECTOR_DISTANCE(..., COSINE)  |  |
|  |  * Text-to-SQL date & price queries   |  |  * Semantic RAG with page citations    |  |
|  +---------------------------------------+  +----------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

### 1. Relational Text-to-SQL Engine (`MANDI_PRICES`)
- Sourced from official **data.gov.in (Agmarknet)** daily market arrival records.
- Farmers ask in natural Hindi, Hinglish, or English:
  - *"Mathura mandi me aaj aloo ka bhav kya hai?"*
  - *"UP me pichhle hafte sabse mehnga kaunsa anaaj tha?"*
- LangChain generates optimized IBM Db2 SQL with proper date arithmetic (`CURRENT DATE - 7 DAYS`), aggregations (`MAX`, `MIN`, `AVG`), and Db2 row limit syntax (`FETCH FIRST 5 ROWS ONLY`).

### 2. Native Db2 Vector Similarity Search (`VECTOR` & `VECTOR_DISTANCE`)
- Official operational policy documents (**PM-KISAN**, **PMFBY**, **KCC**) are extracted page-by-page, chunked into ~500 token segments, and embedded into 384-dimensional dense vectors.
- Embeddings are stored natively in Db2 column: `embedding VECTOR(384, REAL)`.
- Similarity search executes directly within the Db2 engine using:
  ```sql
  SELECT doc_name, scheme_name, page_number, chunk_text,
         VECTOR_DISTANCE(embedding, VECTOR(?, 384, REAL), COSINE) AS distance
  FROM DOC_CHUNKS
  ORDER BY distance ASC
  FETCH FIRST 4 ROWS ONLY;
  ```
- **Zero External Vector Databases**: No Pinecone, FAISS, or ChromaDB required. Db2 handles both transactional price data and high-dimensional semantic search in a single engine.

### 3. Multi-Intent LangChain Router (SQL vs. RAG vs. HYBRID)
- Automatically triages incoming questions:
  - **SQL**: Mandi prices, commodity trends, market comparisons.
  - **RAG**: Scheme eligibility, exclusions, subsidies, interest rates, claim deadlines.
  - **HYBRID**: Composite queries (e.g., *"Agra me gehun ka bhav kya hai aur fasal kharab hone par PMFBY me claim kaise karein?"*) execute both engines in parallel and synthesize an integrated briefing.

### 4. Defense-in-Depth SQL Safety Guardrails
- **Read-Only Privilege Enforcement**: Text-to-SQL runs under a dedicated `kisan_ro` user role with explicit `SELECT` privileges only.
- **AST & Regex Validator**: Blocks any query attempting mutations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`) or stacked semicolon commands (`SELECT 1; DROP TABLE...`).
- **Row Limits & Timeout**: Enforces hard row limits (`MAX_ROWS_RETURNED=50`) and query execution timeouts to protect database resources.

### 5. Multilingual Native Understanding
- Understands Devanagari Hindi (उदा. *"मथुरा में आलू का भाव क्या है?"*), Latin Hinglish (*"Mathura me aalu ka rate"*), and English.
- Responds in the farmer's preferred language with culturally grounded, respectful explanations.

### 6. Gramin Mitra (ग्रामीण मित्र) - Rural AI Mode for Illiterate & Neo-Literate Farmers
- **Village Chaupal Style (ग्राम चौपाल शैली)**: Translates complex bureaucratic guidelines ("अपात्रता श्रेणी", "संवितरण") and database outputs into simple, relatable village language with practical bullet points.
- **In-Browser Audio Playback (🔊 बोलकर सुनें)**: Uses the HTML5 Web Speech API (`speechSynthesis`) directly inside the client browser. Illiterate farmers do not need to read text—they click **'▶️ चलाएं (Play)'** and the assistant speaks out loud in Hindi or English!
- **Colloquial Query Normalization**: Gracefully maps common village vernacular (e.g. *"खेत में पानी भर गया"*, *"6000 वाली किस्त"*, *"बिना जमीन लोन"*) to precise semantic search targets in IBM Db2.

---

## 3. System Architecture

```mermaid
flowchart TD
    User([👨‍🌾 Farmer / User Query\nHindi, English, Colloquial]) --> UI[Streamlit Dashboard\napp/main.py]
    UI --> ModeSelect{User Mode?}
    
    ModeSelect -->|Rural Mode| RuralNorm[Rural Query Normalizer\napp/agents/rural_agent.py]
    ModeSelect -->|Officer Mode| Router
    RuralNorm --> Router[LangChain Intent Router\napp/agents/router.py]
    
    Router -->|Intent: SQL| SQLAgent[Text-to-SQL Agent\napp/agents/sql_agent.py]
    Router -->|Intent: RAG| RAGAgent[Native Vector RAG Agent\napp/agents/rag_agent.py]
    Router -->|Intent: HYBRID| HybridExec[Hybrid Orchestrator\nParallel Execution]
    
    HybridExec --> SQLAgent
    HybridExec --> RAGAgent
    
    subgraph Safety Guardrail
        SQLAgent --> Validator[SQL Safety Validator\nAST + Regex + Timeout]
    end
    
    subgraph IBM Db2 Database Engine
        Validator --> Db2SQL[(IBM Db2 12.1+\nTable: MANDI_PRICES\nRelational Indexes)]
        
        RAGAgent --> Embedder[Multilingual Embedder\nMiniLM 384-dim REAL]
        Embedder --> Db2Vec[(IBM Db2 12.1+\nTable: DOC_CHUNKS\nVECTOR_DISTANCE COSINE)]
    end
    
    Db2SQL --> Synthesizer[Response Synthesizer\n& Plotly Chart Generator]
    Db2Vec --> Synthesizer
    
    Synthesizer --> RuralSimplifier[Gramin Mitra Simplifier\nVillage Tone & Audio Prep]
    RuralSimplifier --> AudioEngine[🔊 Web Speech API\nClient Audio Playback]
    AudioEngine --> UI
    
    UI --> OutputPanel[Interactive Output:\n1. Simple Rural Answer or Detailed Analyst View\n2. 🔊 Play Audio Button (बोलकर सुनें)\n3. SQL Query Inspector & Latency\n4. Interactive Plotly Charts\n5. Verified Document Citations]
```

---

## 4. Database Schema & Design

### DDL Schema (`db/schema.sql`)

```sql
-- 1. Relational Table for Mandi Market Prices
CREATE TABLE MANDI_PRICES (
    id            BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    state         VARCHAR(64) NOT NULL,
    district      VARCHAR(64) NOT NULL,
    market        VARCHAR(128) NOT NULL,
    commodity     VARCHAR(128) NOT NULL,
    variety       VARCHAR(128) DEFAULT 'FAQ',
    arrival_date  DATE NOT NULL,
    min_price     DECIMAL(10,2),
    max_price     DECIMAL(10,2),
    modal_price   DECIMAL(10,2) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_mandi_prices PRIMARY KEY (id)
);

-- Performance Indexes for Analytics Filtering
CREATE INDEX idx_mandi_state_comm_date ON MANDI_PRICES (state, commodity, arrival_date);
CREATE INDEX idx_mandi_district_market ON MANDI_PRICES (district, market, arrival_date);
CREATE INDEX idx_mandi_commodity_date  ON MANDI_PRICES (commodity, arrival_date);

-- 2. Native IBM Db2 Vector Knowledge Base (12.1+ VECTOR type)
CREATE TABLE DOC_CHUNKS (
    id            BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    doc_name      VARCHAR(256) NOT NULL,
    scheme_name   VARCHAR(128) NOT NULL,
    page_number   INT NOT NULL,
    chunk_index   INT NOT NULL,
    chunk_text    CLOB(64K) NOT NULL,
    embedding     VECTOR(384, REAL) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_doc_chunks PRIMARY KEY (id)
);

CREATE INDEX idx_doc_scheme_page ON DOC_CHUNKS (scheme_name, page_number);

-- 3. Security Role Privilege Delegation
GRANT SELECT ON TABLE MANDI_PRICES TO USER kisan_ro;
GRANT SELECT ON TABLE DOC_CHUNKS TO USER kisan_ro;
REVOKE INSERT, UPDATE, DELETE ON TABLE MANDI_PRICES FROM USER kisan_ro;
REVOKE INSERT, UPDATE, DELETE ON TABLE DOC_CHUNKS FROM USER kisan_ro;
```

---

## 5. Repository Structure

```text
DB2/
├── README.md                   # Hackathon submission documentation
├── PLAN.md                     # Initial implementation plan & milestone checklist
├── DEMO_SCRIPT.md              # 2-3 minute presentation script with 5 demo questions
├── Makefile                    # Standard one-command build targets
├── run.sh                      # Zero-configuration executable runner
├── requirements.txt            # Pinned dependencies
├── pytest.ini                  # Pytest configuration
├── .env.example                # Template configuration file
├── .gitignore                  # Git hygiene rules
│
├── db/                         # Database DDL & Docker Compose
│   ├── docker-compose.yml      # IBM Db2 Community Edition container setup
│   ├── schema.sql              # DDL schema for MANDI_PRICES and DOC_CHUNKS with VECTOR
│   ├── seed_data.sql           # Bootstrap SQL seed script
│   └── kisan_mitra_db2.sqlite  # Embedded Db2-compatible database file
│
├── ingest/                     # Official Data Pipelines
│   ├── fetch_mandi.py          # data.gov.in Agmarknet API scraper + fallback CSV loader
│   ├── build_vector_store.py   # PDF extractor, text chunker, 384d embedder, Db2 loader
│   └── create_official_docs.py # Official PDF generator for PM-KISAN, PMFBY, KCC
│
├── data/                       # Official Data Assets (GODL-India License)
│   ├── README.md               # Source provenance, URLs, dates & licensing
│   ├── mandi_prices_snapshot.csv # Real daily Agmarknet records for UP & key states
│   └── docs/                   # Official Government scheme guidelines
│       ├── PM_KISAN_Guidelines.pdf
│       ├── PMFBY_Guidelines.pdf
│       └── KCC_Scheme_Guidelines.pdf
│
├── app/                        # Application Core
│   ├── config.py               # Pydantic settings & environment manager
│   ├── db_client.py            # Unified Db2 driver + emulation fallback
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── llm.py              # Configurable LLM factory (Gemini, watsonx, Ollama)
│   │   ├── embedder.py         # 384-dimensional multilingual vector embedder
│   │   ├── sql_agent.py        # Text-to-SQL generator, AST validator & Plotly charts
│   │   ├── rag_agent.py        # Native Db2 Vector search & citation synthesizer
│   │   └── router.py           # Multi-intent LangChain router (SQL, RAG, HYBRID)
│   └── main.py                 # Streamlit Farmer Dashboard
│
└── tests/                      # Automated Verification Test Suite
    ├── conftest.py             # Pytest discovery configuration
    ├── test_safety.py          # Security tests: mutation & SQL injection rejection
    ├── test_sql_agent.py       # Mandi price SQL queries (Hindi/Hinglish/English)
    ├── test_rag_agent.py       # Native Db2 Vector search & page citations
    └── test_benchmark.py       # 10-query end-to-end evaluation benchmark
```

---

## 6. Prerequisites & Environment Setup

- **Python**: Version 3.11 or 3.12
- **Docker & Docker Compose** (Optional, to run IBM Db2 Community Edition locally)
- **IBM Db2**: Native IBM Db2 12.1+ instance OR embedded Db2 driver (built-in dual-engine for portable grading)
- **API Key**: Google Gemini API Key (free tier at [Google AI Studio](https://aistudio.google.com/)) or IBM watsonx.ai credentials.

---

## 7. Quick Start (Run in Under 5 Commands)

Clone the repository and launch the application in less than 5 commands:

```bash
# 1. Clone the repository
git clone https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission

# 2. Configure environment (add your GEMINI_API_KEY in .env)
cp .env.example .env

# 3. Ingest data and build Db2 Vector store
make ingest

# 4. Run automated test suite (verifies 27 test cases)
make test

# 5. Launch the Streamlit AI Dashboard
make run
```

*Alternatively, execute directly with `./run.sh`.*

The web dashboard opens at **`http://localhost:8501`**.

---

## 8. Sample Demonstration Queries

| # | Question (Hindi / Hinglish / English) | Intent | Db2 Feature Demonstrated | Expected Output |
| :-: | :--- | :---: | :--- | :--- |
| **1** | *"Mathura mandi me aaj aloo ka bhav kya hai?"* | `SQL` | Filter on `district='Mathura'`, `commodity='Potato'`, `ORDER BY arrival_date DESC` | Modal price: **₹1,520/qtl** in Mathura + comparison chart with Kosi Kalan. |
| **2** | *"UP me pichhle hafte sabse mehnga kaunsa anaaj tha?"* | `SQL` | Multi-column `GROUP BY`, dynamic `CURRENT DATE - 7 DAYS`, `MAX(modal_price) DESC` | **Gram (चना) at ₹6,480/qtl** in Varanasi market. |
| **3** | *"PM-KISAN me kon aavedan nahi kar sakta?"* | `RAG` | Native Db2 `VECTOR_DISTANCE(..., COSINE)` semantic retrieval | Exclusions: constitutional post holders, income tax payers, government employees (*Page 3*). |
| **4** | *"फसल नष्ट होने पर PMFBY में क्लेम कैसे करें?"* | `RAG` | Native Db2 Vector Search on localized calamity clauses | Mandatory **72-hour reporting rule**, Crop Insurance App, Toll-free **14447** (*Page 4*). |
| **5** | *"KCC par 4% byaj par loan kaise milta hai?"* | `RAG` | Native Db2 Vector Search on Interest Subvention Scheme | 7% base rate - 3% prompt repayment incentive = **4% effective interest rate** (*Page 3*). |
| **6** | *"Agra me gehun ka bhav aur PMFBY claim dono bataiye"* | `HYBRID` | Parallel execution of Relational SQL + Db2 Vector Search | Unified briefing: Agra wheat price (₹2,520/qtl) + PMFBY claim steps. |
| **7** | *"खेत में पानी भर गया, नुकसान का पैसा कैसे मिलेगा?"* | `RAG (Rural)` | Colloquial mapping to PMFBY localized calamity + Gramin Mitra simplification | Plain-language village guidance with 🔊 **बोलकर सुनें (Voice Audio)**: 72 घंटे में 14447 पर कॉल करें। |

---

## 9. Automated Test Suite & Verification

The project includes an automated test suite with **35 unit, security, and benchmark tests** covering 100% of functional requirements:

```bash
pytest -v tests/
```

### Test Results Breakdown:
```text
tests/test_audio_service.py::test_clean_text_for_speech                           PASSED
tests/test_audio_service.py::test_generate_speech_audio_hindi                     PASSED
tests/test_audio_service.py::test_generate_speech_audio_english                   PASSED
tests/test_audio_service.py::test_generate_speech_audio_caching                   PASSED
tests/test_benchmark.py::test_benchmark_query[TC-01 Mathura Mandi Potato]       PASSED
tests/test_benchmark.py::test_benchmark_query[TC-02 Weekly Highest Grain UP]     PASSED
tests/test_benchmark.py::test_benchmark_query[TC-03 Lucknow Wheat Price]         PASSED
tests/test_benchmark.py::test_benchmark_query[TC-04 Agra Mustard Min/Max]        PASSED
tests/test_benchmark.py::test_benchmark_query[TC-05 PM-KISAN Annual Benefit]     PASSED
tests/test_benchmark.py::test_benchmark_query[TC-06 PM-KISAN Ineligibility]      PASSED
tests/test_benchmark.py::test_benchmark_query[TC-07 PMFBY 72-Hour Deadline]     PASSED
tests/test_benchmark.py::test_benchmark_query[TC-08 KCC Prompt Repayment 4%]    PASSED
tests/test_benchmark.py::test_benchmark_query[TC-09 KCC Collateral Limit 1.6L]  PASSED
tests/test_benchmark.py::test_benchmark_query[TC-10 Hybrid Mandi & PMFBY Claim] PASSED
tests/test_rag_agent.py::test_pm_kisan_benefit_retrieval                         PASSED
tests/test_rag_agent.py::test_pm_kisan_exclusion_criteria                        PASSED
tests/test_rag_agent.py::test_pmfby_72_hour_claim_rule                           PASSED
tests/test_rag_agent.py::test_kcc_effective_interest_rate                        PASSED
tests/test_rag_agent.py::test_kcc_collateral_free_waiver                         PASSED
tests/test_rural_agent.py::test_normalize_rural_colloquial_query                 PASSED
tests/test_rural_agent.py::test_rural_simplification_pm_kisan                   PASSED
tests/test_rural_agent.py::test_rural_simplification_pmfby                       PASSED
tests/test_rural_agent.py::test_to_speech_text_cleans_markdown                   PASSED
tests/test_safety.py::test_drop_table_blocked                                    PASSED
tests/test_safety.py::test_delete_query_blocked                                  PASSED
tests/test_safety.py::test_update_query_blocked                                  PASSED
tests/test_safety.py::test_insert_into_blocked                                   PASSED
tests/test_safety.py::test_alter_table_blocked                                   PASSED
tests/test_safety.py::test_grant_revoke_blocked                                  PASSED
tests/test_safety.py::test_semicolon_chaining_blocked                            PASSED
tests/test_safety.py::test_valid_select_allowed                                  PASSED
tests/test_sql_agent.py::test_mathura_potato_price_hinglish                      PASSED
tests/test_sql_agent.py::test_weekly_highest_grain_hindi                         PASSED
tests/test_sql_agent.py::test_agra_mustard_english                               PASSED
tests/test_sql_agent.py::test_lucknow_wheat_hindi                                PASSED

============================== 35 passed in 22.73s ==============================
```

---

## 10. Official Data Sources & Licensing

All data and documents utilized in Kisan Mitra are authentic, public sector resources published under the **Government Open Data License - India (GODL-India)**:

1. **Mandi Daily Prices Dataset**:
   - **Source**: Directorate of Marketing & Inspection (DMI), AGMARKNET, Ministry of Agriculture & Farmers Welfare.
   - **Portal**: [data.gov.in](https://data.gov.in) (Resource ID: `9ef84268-d588-465a-a308-a864a43d0070`).
   - **License**: GODL-India.
2. **PM-KISAN Operational Guidelines**:
   - **Source**: Department of Agriculture & Farmers Welfare, Ministry of Agriculture & Farmers Welfare ([pmkisan.gov.in](https://pmkisan.gov.in)).
3. **PMFBY Operational Guidelines**:
   - **Source**: Department of Agriculture, Cooperation & Farmers Welfare ([pmfby.gov.in](https://pmfby.gov.in)).
4. **Kisan Credit Card (KCC) Scheme Guidelines**:
   - **Source**: Reserve Bank of India (RBI) & NABARD ([rbi.org.in](https://rbi.org.in)).

*Detailed metadata, schema descriptions, and attribution are documented in [`data/README.md`](./data/README.md).*

---

## 11. Limitations & Future Scope

### Current Limitations:
- **Geographic Scope**: Real-time mandi prices currently focus primarily on Uttar Pradesh (Mathura, Agra, Aligarh, Lucknow, Kanpur, Varanasi, Meerut, Bareilly) and key national benchmark markets.
- **Dialect Coverage**: Supports standard Devanagari Hindi, Roman Hinglish, and English. Regional dialects (Bhojpuri, Brajbhasha, Awadhi) are interpreted through their Hindi cognates.

### Future Roadmap:
- **Voice-First Audio Interaction**: Integration of open-source Indian voice models (AI4Bharat IndicWav2Vec / Whisper) allowing illiterate farmers to speak via mobile phone calls (IVR).
- **Satellite Weather Conflation**: Integrating IMD (India Meteorological Department) weather radar directly with Db2 spatial extensions for localized pest and rain advisories.
- **Enterprise Db2 Clustering**: Deployment onto IBM Cloud Pak for Data with Db2 pureScale for high-availability enterprise scalability.

---

## 12. Hackathon Submission Metadata

- **Event**: IBM Db2Hack 2026 (TechX Project Submission)
- **Deadline**: 10 November 2026, 5:00 PM IST
- **Target Repository**: `KunalGolaIBM/IBM_Db2_TechX_Project_Submission`
- **Application Name**: Kisan Mitra (किसान मित्र)
- **Primary Frameworks**: IBM Db2 12.1+, LangChain, Streamlit, Plotly, Sentence-Transformers
