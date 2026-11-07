# AEGIS Architecture

## Shape

AEGIS is a modular monolith with three deployable pieces:

1. **Next.js dashboard** — research input, evidence selection, overview, claim inspector,
   evidence viewer, verification history.
2. **FastAPI application** — validated HTTP boundary, orchestration, and persistence.
3. **IBM Db2 Community Edition 12.1.5** — the mandatory primary store for documents,
   passages, sessions, claims, results, and evidence links.

There is no vector database, message queue, or orchestration platform in the initial
implementation.

```text
Browser
  │  JSON / multipart
  ▼
Next.js (app router, client dashboard)
  │  NEXT_PUBLIC_API_BASE_URL
  ▼
FastAPI
  ├── /health
  ├── /api/db/health
  ├── /api/documents      → DocumentService → PyMuPDF / chunker
  ├── /api/verify         → VerificationPipeline
  └── /api/verifications  → Db2Repository
                              │
                              ▼
                        LangChain ChatOpenAI
                              │
                        Claim extraction
                              │
                        Lexical retrieval (Db2 SQL + BM25)
                              │
                        Claim verification + evidence validation
                              │
                              ▼
                        IBM Db2 (schema AEGIS)
```

## Backend modules

| Module | Responsibility |
| --- | --- |
| `app/main.py` | App factory, CORS, timeout middleware, error envelopes |
| `app/core/config.py` | Environment-only settings; DSN assembly |
| `app/core/errors.py` | Typed errors mapped to safe HTTP responses |
| `app/db/connection.py` | Db2 connect, transaction, prepared statements, cleanup |
| `app/db/repository.py` | All SQL: documents, retrieval candidates, sessions, claims, links |
| `app/services/document_processing.py` | Upload validation, PDF text extraction, passage chunking |
| `app/services/documents.py` | Content-hash deduplicated document ingestion |
| `app/services/claim_extraction.py` | LangChain JSON prompt → validated `ExtractedClaim` list |
| `app/services/evidence_retrieval.py` | Db2 lexical candidates + BM25 ranking behind a backend interface |
| `app/services/claim_verification.py` | LangChain assessment + passage-ID validation guardrails |
| `app/services/numerical_verifier.py` | Deterministic comparison of simple numeric expressions |
| `app/services/report_generator.py` | JSON and Markdown report generation |
| `app/services/pipeline.py` | End-to-end orchestration, duration, and failure-state handling |
| `app/services/llm.py` | Provider-agnostic LangChain client + tolerant JSON parsing |

## Request lifecycle

`POST /api/verify`:

1. Pydantic validates lengths, byte limits, and document IDs.
2. Optional pasted evidence is hashed, chunked, and stored as a `DOCUMENTS` +
   `PASSAGES` record (deduplicated by content hash).
3. Selected document IDs are confirmed to exist; unknown IDs return 404.
4. A `VERIFICATION_SESSIONS` row is inserted with status `PROCESSING`.
5. LangChain extracts atomic claims from the research text.
6. For each claim, Db2 is queried for lexically matching passages in the selected
   documents; BM25 ranks candidates in Python.
7. LangChain receives only those candidate passages and returns structured JSON.
8. AEGIS validates the classification and every cited passage ID:
   - Unknown IDs are discarded.
   - `SUPPORTED` / `CONTRADICTED` without a valid citation is downgraded to
     `INSUFFICIENT_EVIDENCE`.
   - A parse/provider failure becomes `VERIFICATION_ERROR` for that claim.
9. A deterministic numeric check compares simple literal quantities in the claim with
   the cited passages. A clear value conflict can override an inconsistent model
   judgment and is recorded separately.
10. Claims, results, evidence links, relationship labels, numeric analysis, duration,
    and final status are written in one transaction. A failure marks the session
    `FAILED` and returns a sanitized error.

## Data model

Schema: `AEGIS`.

### DOCUMENTS
`DOCUMENT_ID` identity PK, `TITLE`, `FILENAME`, `CONTENT_HASH` unique, `SOURCE_TYPE`,
`PROCESSING_STATUS`, `CREATED_AT`.

### PASSAGES
`PASSAGE_ID` identity PK, `DOCUMENT_ID` FK → DOCUMENTS (cascade), `PASSAGE_TEXT`
varchar(4000), `PAGE_NUMBER`, `PASSAGE_INDEX`, `CHAR_START`, `CHAR_END`.

### VERIFICATION_SESSIONS
`SESSION_ID` identity PK, `SUBMITTED_TEXT` varchar(32672), `MODEL_PROVIDER`, `STATUS`,
`ERROR_MESSAGE`, `CREATED_AT`, `COMPLETED_AT`, `DURATION_MS`.

### CLAIMS
`CLAIM_ID` identity PK, `SESSION_ID` FK → sessions (cascade), `ORIGINAL_CLAIM`,
`NORMALIZED_CLAIM`, `CLAIM_TYPE`, `POSITION_START`, `POSITION_END`.

### VERIFICATION_RESULTS
`RESULT_ID` identity PK, `CLAIM_ID` FK unique, `CLASSIFICATION` check-constrained,
`EXPLANATION`, `LIMITATIONS`, `NUMERICAL_ANALYSIS`, `VERIFICATION_METHOD`,
`HUMAN_REVIEW_STATUS`, `CREATED_AT`.

### EVIDENCE_LINKS
`EVIDENCE_LINK_ID` identity PK, `RESULT_ID` FK → results (cascade), `PASSAGE_ID` FK →
passages (cascade), `EVIDENCE_RELATIONSHIP`, `RELEVANCE_SCORE`, unique
`(RESULT_ID, PASSAGE_ID)`.

Indexes cover passage lookup by document, claim lookup by session, evidence lookup by
result/passage, status filtering, and recent-session/document ordering. Indexes live in
`database/indexes.sql`; `database/init_db.py` applies schema, migrations, and indexes
idempotently.

## Reports and evaluation

- `GET /api/verifications/{session_id}/export?format=json|markdown` generates a
  downloadable report with session metadata, claims, evidence, explanations,
  limitations, numeric checks, and unresolved questions.
- `GET /api/evaluation` returns a real SciFact metrics file if one exists; otherwise it
  returns an explicit `not_run` state. The UI never invents benchmark scores.
- The deterministic numeric verifier is intentionally narrow and explainable; it does
  not replace the LLM judgment except for unambiguous literal value conflicts.

## Retrieval design

The initial retriever is deliberately simple and auditable:

1. Tokenize the claim (lowercase, stopwords removed, numbers/percentages preserved).
2. Fetch up to 500 candidate passages from Db2 with parameterized `LIKE` predicates
   and a document filter.
3. Score candidates with BM25 in Python.
4. Return the top K (default 6) with a retrieval score persisted in `EVIDENCE_LINKS`.

The `RetrievalBackend` protocol isolates this choice. A native Db2 vector retrieval
implementation can be added later without changing the API or verification service.
Embedding similarity alone must not be treated as proof of factual support.

## LLM contract

- Provider/model/base URL/key are environment settings.
- LangChain `ChatPromptTemplate | ChatOpenAI | StrOutputParser` performs each call.
- Prompts require strict JSON and delimit untrusted text.
- The parser tolerates code fences and prose around JSON but never invents content.
- Timeouts and retries are configured at the client.
- Tests inject a scripted `LLMClient`; production never uses it.

## Failure handling

- Db2 unavailable → 503 with a generic message; no DSN or credentials leak.
- LLM unavailable → session marked `FAILED`, 503 `llm_unavailable`.
- Malformed model JSON → per-claim `VERIFICATION_ERROR`, not a false support claim.
- Unreadable/encrypted/scanned PDF → 422 with a clear message.
- Invalid input → 422 validation envelope.
- Unexpected error → sanitized 500, full traceback only in server logs.

## Local platform note

On macOS Apple Silicon, `ibm_db` 3.3.0 segfaults when
`ibm_db.exec_immediate(conn, sql, params)` receives parameter markers. AEGIS therefore
uses `ibm_db.prepare` + `bind_param` + `execute` and frees every statement. This is
still fully parameterized SQL. The issue is documented in `docs/limitations.md`.

## Deployment posture

- Frontend: Vercel-ready (`NEXT_PUBLIC_API_BASE_URL`).
- Backend: any Python host with outbound access to the LLM and Db2.
- Db2: keep private. A hosted backend cannot reach a Db2 instance listening only on
  a developer machine; a hosted Db2 deployment and network allow-list are required for
  a public demo. No hosted Db2 is configured in this repository.
