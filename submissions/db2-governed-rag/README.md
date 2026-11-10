# Governed RAG: Clearance-Aware Vector Search Inside IBM Db2

## Problem Statement
In enterprise Retrieval-Augmented Generation (RAG) systems, data security and access control are critical. Standard RAG architectures retrieve context vectors indiscriminately before filtering, leading to potential confidential data leaks or authorization bypasses at the LLM prompt level. 

**Db2 Governed RAG** solves this challenge by enforcing strict role-based metadata access controls (`Public`, `Internal`, `Restricted`) **directly inside IBM Db2** during vector similarity search execution. By pairing native `VECTOR_DISTANCE` COSINE operations with metadata filtering in single SQL queries, unauthorized text is never retrieved or passed to the LLM.

---

## How Db2 is Used
- **Native Vector Type**: `VECTOR(384, FLOAT32)` column storing document chunk embeddings.
- **In-Database Filtering & Distance**: `VECTOR_DISTANCE(..., COSINE)` combined with `JSON_VALUE` clearance metadata filtering inside the `WHERE` clause of Db2 SQL queries.
- **Haystack 2.x Integration**: Utilizes `ibm-db-haystack` (`IBMDb2DocumentStore`, `IBMDb2EmbeddingRetriever`) over native `ibm_db` drivers.

---

## Prerequisites
- Python 3.10+
- IBM Db2 12.1.2 or later with vector extensions reachable over TCP/IP.
- Ollama running `qwen2.5:7b` (optional for local LLM generation; demo mode supported without LLM).

---

## Setup Instructions

1. **Clone & Navigate:**
   ```bash
   git clone https://github.com/Pavan3030-pr/IBM_Db2_TechX_Project_Submission.git
   cd IBM_Db2_TechX_Project_Submission/submissions/db2-governed-rag
   ```

2. **Set up Virtual Environment & Install Dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Environment Configuration:**
   ```bash
   cp .env.example .env
   # Edit .env with your IBM Db2 host, port, database, user, and password credentials.
   ```

4. **Index Documents into Db2:**
   ```bash
   python src/index.py
   ```

5. **Run CLI Query:**
   ```bash
   python src/query.py --role Public "What are the security guidelines?"
   python src/query.py --role Restricted "What are the security guidelines?"
   ```

---

## How to Run with Streamlit

A unified interactive web application is available in `submissions/streamlit_app`.

1. **Install Streamlit dependencies:**
   ```bash
   pip install -r submissions/streamlit_app/requirements.txt
   ```

2. **Launch Streamlit Application:**
   ```bash
   streamlit run submissions/streamlit_app/app.py
   ```

3. **Select Mode:**
   - Choose **"Db2 Governed RAG"** in the sidebar.
   - Test queries under **Public**, **Internal**, or **Restricted** roles.
   - Toggle **"Compare all roles mode"** to see side-by-side clearance level enforcement.
