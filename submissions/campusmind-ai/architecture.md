# CampusMind AI - System Architecture

## 1. Overview

CampusMind AI is a PDF-based student knowledge assistant. It uses FastAPI for API handling, PyPDF for text extraction and Haystack BM25 for retrieving relevant passages.

## 2. Current Architecture Flow

Student
  |
  v
FastAPI Backend
  |
  +---- POST /upload
  |       |
  |       v
  |     PDF Validation
  |       |
  |       v
  |     PyPDF Text Extraction
  |       |
  |       v
  |     Text Chunking + Page Metadata
  |       |
  |       v
  |     Haystack InMemoryDocumentStore
  |
  +---- POST /ask
          |
          v
        BM25 Retriever
          |
          v
        Top 3 Relevant Documents
          |
          v
        API Response with Source Details

## 3. Component Responsibilities

| Component | Responsibility |
|---|---|
| FastAPI | Handles upload and question APIs |
| PyPDF | Extracts text from PDF pages |
| PDF Processor | Creates text chunks and page metadata |
| Haystack | Manages document storage and retrieval |
| BM25 | Ranks relevant passages |
| Swagger UI | Enables API testing |

## 4. Data Flow

1. The user uploads a PDF.
2. FastAPI validates the file type and size.
3. PyPDF extracts text from each page.
4. The processor splits text into chunks.
5. Each chunk stores its filename and page number.
6. Haystack stores the chunks in memory.
7. The user submits a question.
8. BM25 retrieves up to three relevant passages.
9. The API returns the passages, source pages and relevance scores.

## 5. IBM Db2 Integration - Planned

IBM Db2 is not connected in the current prototype.

Planned architecture:
- Store document and chunk metadata persistently in IBM Db2.
- Use a compatible Db2 Python connector.
- Retrieve stored information from Db2.

These components are future work and are not implemented in the current version.

## 6. Future AI Workflow - Planned

Future improvements may include:
- Question-intent classification.
- Retrieval orchestration.
- LLM-based grounded answer generation.
- Automatic study summaries and quizzes.

The current implementation does not include an autonomous agent or LLM.

## 7. Current Limitations

- In-memory storage is cleared when the application restarts.
- BM25 uses keyword-based retrieval.
- Scanned PDFs without extractable text are unsupported.
- IBM Db2 integration is pending.
