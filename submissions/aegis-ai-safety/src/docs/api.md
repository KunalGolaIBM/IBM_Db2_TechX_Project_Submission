# AEGIS API

Base URL: `http://localhost:8000`

Interactive OpenAPI: `http://localhost:8000/docs`

All errors use one envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request payload is invalid.",
    "detail": "submitted_text: String should have at least 10 characters"
  }
}
```

`detail` is optional and never contains database internals or secrets.

## GET /health

Liveness plus non-secret configuration.

```bash
curl -s http://localhost:8000/health
```

```json
{
  "status": "ok",
  "service": "aegis-api",
  "version": "0.2.0",
  "environment": "development",
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "database": "TESTDB"
}
```

## GET /api/db/health

Tests the Db2 connection and reports schema readiness. Returns `503` when Db2 is
unreachable.

```bash
curl -s http://localhost:8000/api/db/health
```

```json
{
  "connected": true,
  "database": "TESTDB",
  "host": "localhost",
  "schema": "AEGIS",
  "server": "TESTDB",
  "server_time": "2026-11-05T12:00:00",
  "tables": ["DOCUMENTS", "PASSAGES", "VERIFICATION_SESSIONS", "CLAIMS", "VERIFICATION_RESULTS", "EVIDENCE_LINKS"],
  "missing_tables": []
}
```

## GET /api/documents

Lists evidence documents with passage counts.

```json
{
  "documents": [
    {
      "document_id": 1,
      "title": "Synthetic demo — SolarCell-X Controlled Efficiency Trial (fictional)",
      "filename": "synthetic_solarcell_study.txt",
      "source_type": "text",
      "passage_count": 4,
      "created_at": "2026-11-05T12:00:00"
    }
  ]
}
```

## POST /api/documents

Multipart upload. Fields:

- `file` (required): `.pdf`, `.txt`, or `.md`; max 10 MB.
- `title` (optional form field): display title.

```bash
curl -s -X POST http://localhost:8000/api/documents \
  -F "file=@paper.pdf" \
  -F "title=Paper title"
```

Response `201`:

```json
{
  "document_id": 2,
  "title": "Paper title",
  "filename": "paper.pdf",
  "content_hash": "…64 hex characters…",
  "source_type": "pdf",
  "passage_count": 18,
  "created_at": "2026-11-05T12:01:00",
  "already_existed": false
}
```

Duplicates are detected by SHA-256 and return the existing document with
`already_existed: true`.

Errors: `400 invalid_upload`, `422 document_processing_failed`.

## GET /api/documents/{document_id}

Returns document metadata plus every extracted passage, including page, sequence, and
character offsets.

```json
{
  "document_id": 2,
  "title": "Paper title",
  "filename": "paper.pdf",
  "content_hash": "…",
  "source_type": "pdf",
  "processing_status": "READY",
  "passage_count": 18,
  "created_at": "2026-11-05T12:01:00",
  "passages": [
    {
      "passage_id": 41,
      "document_id": 2,
      "passage_text": "…",
      "page_number": 1,
      "passage_index": 0,
      "char_start": 0,
      "char_end": 1200
    }
  ]
}
```

`404 not_found` when the document does not exist.

## POST /api/verify

Runs the full pipeline synchronously.

Request:

```json
{
  "submitted_text": "SolarCell-X achieved 92% conversion efficiency under standard test conditions.",
  "document_ids": [1],
  "evidence_text": "Optional pasted evidence. Stored and reused by content hash.",
  "evidence_title": "Optional title"
}
```

- `submitted_text`: 10–30,000 characters (≤32,000 UTF-8 bytes).
- `document_ids`: up to 25 positive IDs; unknown IDs return `404`.
- `evidence_text`: optional, ≤30,000 characters. Use either library documents, pasted
  evidence, or both.
- A request with no evidence still runs; claims become `INSUFFICIENT_EVIDENCE`, never
  contradiction.

Response `200` (abbreviated):

```json
{
  "session_id": 4,
  "submitted_text": "…",
  "model_provider": "openai/gpt-4o-mini",
  "status": "COMPLETED",
  "error_message": null,
  "created_at": "2026-11-05T12:02:00",
  "completed_at": "2026-11-05T12:02:04",
  "duration_ms": 4120,
  "counts": {
    "total": 2,
    "supported": 1,
    "contradicted": 1,
    "insufficient_evidence": 0,
    "verification_error": 0
  },
  "claims": [
    {
      "claim_id": 9,
      "original_claim": "SolarCell-X achieved 92% conversion efficiency under standard test conditions.",
      "normalized_claim": "SolarCell-X achieved 92% conversion efficiency.",
      "claim_type": "NUMERICAL",
      "position_start": 0,
      "position_end": 79,
      "classification": "SUPPORTED",
      "explanation": "Passage 11 explicitly states 92% under standard test conditions.",
      "limitations": "Synthetic evidence; indoor measurement only.",
      "numerical_analysis": "Deterministic numeric check: 92% matches passage 11.",
      "human_review_status": "PENDING",
      "verification_method": "langchain_llm+db2_lexical_retrieval",
      "result_created_at": "2026-11-05T12:02:04",
      "evidence": [
        {
          "passage_id": 11,
          "passage_text": "…",
          "page_number": 1,
          "passage_index": 0,
          "document_id": 1,
          "document_title": "Synthetic demo — SolarCell-X Controlled Efficiency Trial (fictional)",
          "filename": "synthetic_solarcell_study.txt",
          "evidence_relationship": "SUPPORTS",
          "relevance_score": 8.731
        }
      ]
    }
  ]
}
```

Errors:

- `422 validation_error`
- `404 not_found`
- `503 database_unavailable`
- `503 llm_unavailable`
- `502 verification_pipeline_failed`
- `504 request_timeout`

## GET /api/verifications

Returns recent sessions, newest first (default 25, max 100).

```json
{
  "verifications": [
    {
      "session_id": 4,
      "status": "COMPLETED",
      "model_provider": "openai/gpt-4o-mini",
      "created_at": "2026-11-05T12:02:00",
      "preview": "SolarCell-X achieved 92%…",
      "total_claims": 3,
      "counts": { "total": 3, "supported": 1, "contradicted": 1, "insufficient_evidence": 1, "verification_error": 0 }
    }
  ]
}
```

## GET /api/verifications/{session_id}

Returns the full persisted session, claims, explanations, numeric checks, and evidence
links. `404` when the session does not exist.

## GET /api/verifications/{session_id}/export

Download a report:

```bash
curl -OJ "http://localhost:8000/api/verifications/4/export?format=json"
curl -OJ "http://localhost:8000/api/verifications/4/export?format=markdown"
```

- `format=json` → `application/json` attachment.
- `format=markdown` (or `md`) → `text/markdown` attachment.

The report includes session status, model/provider, timestamps, duration, counts,
submitted text, claims, classifications, explanations, limitations, numeric checks,
human-review status, evidence passages, and unresolved questions.

## GET /api/evaluation

Returns measured SciFact metrics only if a real result file exists at
`experiments/results/scifact_test_metrics.json`:

```json
{
  "status": "not_run",
  "dataset": "SciFact",
  "license": "CC BY-NC 2.0",
  "message": "No SciFact benchmark has been executed…",
  "results": null
}
```

The endpoint reads a real metrics file if present, preferring
`experiments/results/scifact_test_metrics.json`, then
`experiments/results/scifact_dev_metrics.json`; otherwise it returns an explicit
`not_run` state. It never generates placeholder accuracy.

## Limits and security

- Upload: 10 MB, text-based PDFs only (no OCR).
- Submitted/pasted text: 30,000 characters.
- Request timeout: 600 seconds by default (`AEGIS_REQUEST_TIMEOUT_SECONDS`).
- CORS: `AEGIS_CORS_ORIGINS` only.
- Parameterized SQL; no client-supplied SQL fragments.
- Raw Db2 errors are logged server-side and never returned.
