# CampusMind AI

**A student knowledge assistant that retrieves relevant information from study PDFs using Haystack BM25.**

## 1. Problem Statement

Students often spend significant time searching lengthy PDFs and study notes for specific definitions, explanations and concepts. Manually locating relevant information makes revision slower and less efficient.

## 2. Solution Overview

CampusMind AI allows students to upload PDF study material and ask questions about its contents. It extracts text, divides it into chunks, indexes them using Haystack BM25 and returns relevant passages with source document and page information.

### Current Features

- PDF upload through FastAPI.
- PDF text extraction using PyPDF.
- Page-wise text chunking.
- Haystack BM25 keyword retrieval.
- Relevant passages with source filename and page number.
- Relevance scores for retrieved passages.
- API documentation through Swagger UI.

## 3. Technology Stack

- Python
- FastAPI
- Haystack
- BM25
- PyPDF
- Swagger UI

## 4. Current Architecture

1. Student uploads a PDF.
2. FastAPI validates the file.
3. PyPDF extracts text page by page.
4. Text is divided into chunks with page metadata.
5. Haystack stores chunks in an in-memory document store.
6. BM25 retrieves relevant passages.
7. The API returns retrieved text and source information.

## 5. IBM Db2 Integration Status

IBM Db2 integration is planned but is not connected in the current prototype.

The intended integration will use IBM Db2 for persistent document and chunk storage.

No live Db2 queries, Db2 persistence or Db2 vector search are currently implemented or claimed.

## 6. Agentic AI Roadmap

The current prototype uses Haystack BM25 retrieval. It does not yet implement an autonomous agent or LLM.

Planned extensions:
- Question-intent classification.
- Retrieval tool orchestration.
- Grounded answer generation.
- Study summary and quiz generation.
- Source-aware responses.

## 7. Project Structure

```text
campusmind-ai/
├── README.md
├── architecture.md
├── submission.json
├── docs/
│   └── screenshots/
├── src/
│   ├── campusmind/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── pdf_processor.py
│   │   └── retrieval.py
│   └── requirements.txt
└── tests/

```

## 8. Setup and Execution

Install dependencies:

```bash
pip install -r src/requirements.txt
```

Run the application:

```bash
uvicorn campusmind.main:app --app-dir src --reload
```

Open Swagger UI: http://localhost:8000/docs

## 9. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Check application status |
| POST | `/upload` | Upload a PDF |
| POST | `/ask` | Retrieve relevant study content |

## 10. Limitations

- Documents are stored in memory and lost when the application restarts.
- Retrieval currently uses keyword-based BM25.
- Scanned PDFs are not supported.
- IBM Db2 and LLM-based answer generation are not yet implemented.

## 11. Future Improvements

- IBM Db2 persistent storage.
- Semantic retrieval.
- LLM-based grounded answers.
- Agentic study assistance.
- Automatic summaries and quizzes.

## 12. Developer

**Kabita Debnath**

GitHub: https://github.com/kabitadebnath05
