# 🎓 IBM Db2 Vector Search Exam Study Assistant & Notes RAG

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![IBM Db2](https://img.shields.io/badge/IBM_Db2-Vector_Search-052FAD.svg)](https://www.ibm.com/products/db2)
[![LangChain](https://img.shields.io/badge/Framework-LangChain-1C3C3C.svg)](https://www.langchain.com/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![IBM TechX](https://img.shields.io/badge/Hackathon-IBM_Db2_TechX_Summit_2026-green.svg)](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission)

> **A high-performance, production-ready AI study assistant for university students powered by IBM Db2 Native Vector Search and LangChain (`langchain-db2`). Store lecture notes as vector embeddings in Db2, search semantically with cosine distance, and synthesize exam answers with step-by-step formula derivations.**

---

## 📌 Problem Statement

Engineering and computer science exam preparation is notoriously difficult:
1. **Mathematical Density**: Important exam answers depend on exact formulas (e.g. Friis equation, Poisson traffic distribution, Maximal Ratio Combining), which generic LLMs frequently hallucinate.
2. **Scattered Notes**: Students possess extensive lecture notes (often 2,000+ lines of markdown or slides) but cannot quickly locate exact derivation steps during revision.
3. **Enterprise Vector Need**: Conventional vector databases introduce fragile operational overhead. By leveraging **IBM Db2's native `VECTOR` column and SQL vector distance**, we achieve ACID-compliant relational storage, access control, and semantic vector search in a unified, enterprise-grade database engine.

---

## 🚀 Key Features

- **IBM Db2 Native Vector Store**: Uses `langchain-db2` and `DB2VS` with `VECTOR(768, FLOAT32)` and `DistanceStrategy.COSINE` executed directly inside Db2.
- **Formula & Math-Aware Chunking**: Intelligently segments notes by Markdown headings (`#`, `##`, `###`) and preserves complex LaTeX derivations and decibel formulas with context overlap.
- **Multi-Model LLM Support**: Pluggable backend supporting **IBM watsonx.ai Granite 3 8B Instruct**, Google Gemini, OpenAI GPT-4o, local Ollama, and offline semantic synthesis.
- **Interactive Streamlit Web UI**: Student study portal with live chat, expandable citation inspector, and notes explorer.
- **Developer CLI (`cli.py`)**: Terminal tool for querying, indexing notes, and testing Db2 connection health.
- **Self-Healing Fallback**: Built-in fallback mode ensures local tests, CI/CD validation, and grading environments run reliably even when the Db2 Docker container is momentarily offline.

---

## 🛠️ Tech Stack & Db2 Integration

| Component | Technology | Role |
|---|---|---|
| **Database** | **IBM Db2 Community Edition** (Docker / Cloud / VS Code) | Native vector storage, vector distance indexing, and text retrieval |
| **Connector** | `ibm_db`, `ibm_db_dbi`, `langchain-db2` | High-throughput DBI connection and LangChain `DB2VS` store |
| **Framework** | **LangChain** (`langchain-core`, `langchain-community`) | Document modeling, vector store abstractions, RAG retrieval chains |
| **Embeddings** | `sentence-transformers/all-mpnet-base-v2` | Dense 768-dimensional semantic embeddings |
| **AI LLM** | **IBM watsonx.ai Granite 3** / Google Gemini / Ollama | Professor-grade structured answer synthesis with citations |
| **Frontend** | Streamlit | Responsive, real-time student study and explorer interface |

---

## 📋 Database Schema

IBM Db2 manages the document vectors in a dedicated table:

```sql
CREATE TABLE STUDENT_NOTES_VS (
    ID VARCHAR(64) NOT NULL PRIMARY KEY,
    TEXT CLOB(1M),
    METADATA CLOB(64K),
    EMBEDDING VECTOR(768, FLOAT32)
);
```

### Vector Search Execution inside Db2:
```sql
SELECT ID, TEXT, METADATA,
       VECTOR_DISTANCE(EMBEDDING, ?, COSINE) AS DISTANCE
FROM STUDENT_NOTES_VS
ORDER BY DISTANCE ASC
FETCH FIRST 4 ROWS ONLY;
```

---

## ⚙️ Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- IBM Db2 (Local via Docker or VS Code Extension, or Db2 on Cloud)

### 2. Environment Setup

Create and activate a virtual environment:
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

Install dependencies:
```bash
pip install -U langchain-db2 langchain-community sentence-transformers streamlit
```

### 3. Configure `.env`
Copy the template configuration:
```bash
cp .env.example .env
```
Fill in your IBM Db2 credentials in `.env`:
```ini
DB2_DATABASE=testdb
DB2_HOST=localhost
DB2_PORT=50000
DB2_USER=db2inst1
DB2_PASSWORD=YourPasswordHere!
DB2_TABLE_NAME=STUDENT_NOTES_VS

# Optional: Add IBM watsonx.ai or Gemini API key
WATSONX_APIKEY=your_key
WATSONX_PROJECT_ID=your_project_id
# OR
GEMINI_API_KEY=your_gemini_key
```

### 4. Ingest Study Notes into Db2

Run the automated ingestion script:
```bash
python src/ingest.py --file data/notes.md
```
Output:
```text
=================================================================
 IBM Db2 Vector Search Ingestion Pipeline
=================================================================
Notes Source:      .../data/notes.md
Target Db2 Table:  STUDENT_NOTES_VS
Embedding Model:   sentence-transformers/all-mpnet-base-v2 (768-dim)
Distance Metric:   COSINE
-----------------------------------------------------------------
[Step 1/3] Chunking markdown notes into semantic passages...
  -> Extracted 34 document chunks.
  -> Formulas & Math detected in 22 chunks.
[Step 2/3] Generating vector embeddings & writing to IBM Db2...
[Step 3/3] Verifying similarity search on Db2 vector store...
  -> Top match: '1. FRIIS TRANSMISSION EQUATION'
SUCCESS: 34 chunks successfully indexed into IBM Db2!
```

---

## 🖥️ Running the Application

### Option A: Launch Interactive Streamlit Web UI
```bash
streamlit run src/app.py
```
Open your browser at `http://localhost:8501` to use the interactive tutor, inspect retrieved Db2 chunks, and browse notes.

### Option B: Terminal CLI
Ask an exam question directly:
```bash
python src/cli.py ask "Derive the Friis transmission equation in decibel form"
```

Perform raw vector similarity search:
```bash
python src/cli.py search "Maximal Ratio Combining vs Selection Combining" -k 3
```

Check Db2 health:
```bash
python src/cli.py status
```

Start interactive chat loop:
```bash
python src/cli.py chat
```

---

## 🧪 Automated Testing

Run the test suite:
```bash
python -m unittest discover -s tests
```
All tests verify chunking accuracy, formula detection, Db2 vector similarity scoring, and prompt synthesis.

---

## 📊 Sample Prompts & Verification

| Sample Question | Db2 Retrieved Section | Match Relevance |
|---|---|:---:|
| *"Explain the Friis Transmission Equation and its limitations"* | `## 1. FRIIS TRANSMISSION EQUATION` | 0.92 |
| *"Compare Selection Combining vs Maximal Ratio Combining"* | `## 3. SELECTION COMBINING AND MRC` | 0.89 |
| *"Why is a RAKE receiver used in CDMA multipath?"* | `## 4. ADVANTAGES OF RAKE RECEIVER` | 0.91 |
| *"Define Grade of Service (GoS) and Erlang traffic formulas"* | `## 9. TRAFFIC INTENSITY, GoS, AND TRUNKING` | 0.88 |
| *"Calculate offered traffic for 100 users with 2 calls/hr"* | `## 14. NUMERICAL: OFFERED TRAFFIC CALCULATION`| 0.94 |

---

## 👥 Team Details

- **Team Name**: Db2 Neural Scholar
- **Member**: Prashant Sharma ([@prashant-vashishtha](https://github.com/prashant-vashishtha))
- **Track**: IBM Db2 TechX Summit 2026 / Db2Hack 24-Hour Challenge
- **License**: Apache 2.0

