# Multilingual Voice RAG: Cross-Lingual Audio Vector Search in IBM Db2

## Problem Statement
Accessing speech recordings across multiple languages (e.g., Hindi and English) traditionally requires separate language-specific indexing or text translation pipelines, introducing latency and cross-lingual translation errors. 

**Db2 Multilingual Voice RAG** enables direct cross-lingual semantic search over transcribed audio chunks. Transcripts generated via OpenAI Whisper are indexed into IBM Db2 with multilingual vector embeddings (`paraphrase-multilingual-mpnet-base-v2`). Users can query in Hindi or English, and Db2 performs vector similarity search (`VECTOR_DISTANCE`) alongside metadata filtering (language, timestamp, audio file source) natively in SQL.

---

## How Db2 is Used
- **Native Vector Support**: `VECTOR(768, FLOAT32)` column storing cross-lingual audio transcript embeddings.
- **In-Database Vector Distance**: `VECTOR_DISTANCE(..., COSINE)` native function calculates audio chunk similarity.
- **Metadata Filtering**: Language tags (`hi`, `en`), audio source references, start times, and end times stored in Db2 JSON metadata columns and filtered inside native queries.
- **Connector**: Integrated via `ibm-db-haystack` (`IBMDb2DocumentStore`, `IBMDb2EmbeddingRetriever`).

---

## Prerequisites
- Python 3.10+
- IBM Db2 12.1.2 or later with vector extensions.
- ffmpeg (if running local audio transcription pipelines with Whisper).

---

## Setup Instructions

1. **Clone & Navigate:**
   ```bash
   git clone https://github.com/Pavan3030-pr/IBM_Db2_TechX_Project_Submission.git
   cd IBM_Db2_TechX_Project_Submission/submissions/db2-multilingual-voice-rag
   ```

2. **Create Virtual Environment & Install Dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r src/requirements.txt
   ```

3. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   # Populate DB2_HOST, DB2_PORT, DB2_DB, DB2_USERNAME, DB2_PASSWORD in .env
   ```

4. **Index Audio Transcripts into Db2:**
   ```bash
   python src/index.py
   ```

5. **Run CLI Search:**
   ```bash
   python src/query.py "Db2 vector search capabilities"
   python src/query.py --lang hi "Db2 vector search kaise kaam karta hai?"
   ```

---

## How to Run with Streamlit

A unified interactive web interface is provided in `submissions/streamlit_app`.

1. **Install Streamlit dependencies:**
   ```bash
   pip install -r submissions/streamlit_app/requirements.txt
   ```

2. **Launch Streamlit Application:**
   ```bash
   streamlit run submissions/streamlit_app/app.py
   ```

3. **Select Mode:**
   - Choose **"Db2 Multilingual Voice RAG"** in the sidebar navigation.
   - Filter results by language (Hindi/English).
   - View retrieved audio transcript chunks complete with similarity scores, timestamp ranges, and original audio source metadata.
