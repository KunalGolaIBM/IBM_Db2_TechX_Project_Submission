# API Contract — v1

Base URL: `/api/v1` · Content type: `application/json` ·
Response models are **strict** (`extra=forbid`) — contract drift fails tests.

> **Verification note:** every route below is exercised offline against mock
> adapters (`mock: true` responses). Behavior against live Db2/Ollama services
> in `ADAPTER_MODE=real` is **unverified** — the integration stack has never
> been installed/run on this machine.

## Error envelope (all non-2xx)

```json
{ "error": { "code": "NOT_FOUND", "message": "…", "request_id": "…", "detail": null } }
```

| Code | HTTP | Source |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Pydantic request validation (`detail` = list) |
| `PROMPT_INJECTION_BLOCKED` | 400 | Chat message matched rules (`detail.matched_rules`) |
| `NOT_FOUND` / `METHOD_NOT_ALLOWED` / … | 404/405/… | Routing |
| `APPROVAL_EXPIRED` | 410 | Approval TTL elapsed before the decision |
| `APPROVAL_STATE_CONFLICT` | 409 | Approval is already decided or terminal |
| `APPROVAL_INVALID_DECISION` | 422 | Decision is not exactly `approve` or `reject` |
| `AGENT_TOOL_LIMIT` | 422 | Proposal batch exceeds `AGENT_MAX_TOOL_CALLS` |
| `KB_INGESTION_UNVERIFIED` | 503 | Knowledge ingestion requested outside mock mode |
| `ADAPTER_UNAVAILABLE` | 503 | Real adapter cannot reach its service |
| `INTERNAL_ERROR` | 500 | Unhandled exception (logged with stack) |

Every response (success or error) carries `x-request-id`; an incoming
`X-Request-ID` header is echoed, otherwise one is generated and logged.

## GET /api/v1/health

Liveness + dependency probes. **Always 200** when the app itself runs — an
unreachable service is reported inside the payload, not as a failed request.

```json
{
  "status": "ok",                 // "ok" | "degraded"
  "version": "0.1.0", "api_version": "v1", "mode": "mock",
  "uptime_seconds": 12.5, "timestamp": "2026-10-31T…",
  "checks": [ { "name": "database", "status": "ok", "mode": "mock",
                "latency_ms": 0.0, "detail": "…" } ]
}
```
Checks: `database`, `vector_store`, `llm`, `embeddings`, `orchestrator`, `audit`.

## GET /api/v1/status

```json
{
  "timestamp": "…", "adapter_mode": "mock",
  "database":   { "provider", "connected", "host", "port", "database", "detail" },
  "vector_store": { "provider", "document_count", "detail" },
  "llm":        { "provider", "model", "available", "detail" },
  "embeddings": { "provider", "model", "available", "detail", "dimensions" }
}
```
**No passwords/tokens/credentials ever appear in this payload.**

## GET /api/v1/config

Effective non-secret configuration:

```json
{ "environment", "debug", "adapter_mode", "api_base", "cors_origins", "serve_frontend",
  "database": { "host", "port", "name", "read_only_user" },
  "models": { "llm", "embeddings", "ollama_base_url" },
  "sql_policy": { "allowed_statements", "max_sql_length", "max_ast_nodes",
                  "max_rows", "query_timeout_ms", "denied_schemas",
                  "enforce_row_limit" },
  "security": { "injection_mode", "max_message_length" } }
```

## POST /api/v1/chat

Request:
```json
{ "message": "…(1–4000 chars)", "mode": "auto|rag|sql", "session_id": null }
```
Response:
```json
{ "reply": "…", "intent": "docs|data|general",
  "citations": [ { "source", "title", "snippet", "score" } ],
  "sql": "SELECT …" | null,
  "mock": true, "request_id": "…",
  "timings": { "total_ms", "retrieval_ms", "generation_ms" },
  "warnings": ["missing_row_limit: …"] }
```
- `sql` is `null` unless it **passed the independent validation gate**.
- Injection matches with `INJECTION_MODE=block` → 400 `PROMPT_INJECTION_BLOCKED`.
- In `ADAPTER_MODE=mock` (default) responses carry `mock: true` with
  deterministic content. In `ADAPTER_MODE=real` the route requires the
  integration stack (`requirements-integration.txt`) and live services —
  otherwise it **fails closed with 503** and never falls back to mock data.

## POST /api/v1/sql/validate

Request `{ "sql": "…" }` → **200 for every well-formed request** (invalid SQL
is a successful *validation outcome*, not an API error):

```json
{ "valid": false, "statement_type": "Delete", "dialect": "db2",
  "normalized_sql": null,
  "violations": [ { "code", "message", "severity" } ],
  "warnings": [],
  "policy": { "max_rows", "timeout_ms", "enforce_row_limit" } }
```
Key violation codes: `parse_error`, `multiple_statements`,
`statement_not_allowed`, `forbidden_construct`, `select_into`, `catalog_access`,
`denied_function`, `ast_too_large`, `too_many_joins`, `too_many_subqueries`,
`in_list_too_large`, `max_length_exceeded`, `empty_statement`, `null_byte`,
`control_characters`.

## GET /api/v1/audit?limit=50

`limit` ∈ [1, 500] (else 422).

```json
{ "entries": [ { "id", "timestamp", "intent", "question", "status",
                 "latency_ms", "detail", "request_id" } ],
  "total": 3, "mock": true }
```
`status` values: `OK`, `BLOCKED`, `ERROR`, `TIMEOUT`, `REJECTED`, `REJECTED_BY_GATE`,
`UNAVAILABLE`, `FAILED`. Each entry also carries `operation`
(`chat` · `sql_execute` · `sql_explain` · `dba_tool`).

## M3 deterministic proposals and approvals

These routes use the in-memory `ApprovalStore`; pending approvals are lost when
the process restarts. Every state transition is written through the configured
audit adapter. Approval responses contain action metadata and the reviewed
statement, never admin credentials.

### POST /api/v1/agent/propose

Creates pending approvals from an explicitly supplied batch of allow-listed
actions. This is a deterministic proposal API, **not** an autonomous LLM/agent
runner. The entire batch is validated before any approval is created. There is
no execution from this route.

```json
{
  "actions": [{
    "action_type": "runstats",
    "params": {"schema": "APP", "table": "DEMO_SERVERS"},
    "rationale": "Refresh stale optimizer statistics."
  }],
  "session_id": null
}
```

`action_type` is `runstats` or `create_index`; each requires exactly the
identifier parameters enforced by the action allow-list. A batch may not
exceed `AGENT_MAX_TOOL_CALLS` (default 8). Invalid actions return 422 and no
partial batch is stored.

Response: `{ "approvals": [Approval], "tool_calls": 1,
"max_tool_calls": 8, "mock": true }`. Each approval includes its ID, state,
rationale, expiry, and exact statement preview.

### GET /api/v1/approvals?limit=50

Lists pending, non-expired approvals only. `limit` is 1–500. Also reports
`execution_mode`: `mock_simulated`, `disabled`, `admin_not_configured`, or
`enabled_unverified`; no credential values are returned.

### GET /api/v1/approvals/{approval_id}

Returns an approval in any state. IDs must match `apr_` plus 12 lowercase
hexadecimal characters (invalid format → 422; unknown valid ID → 404).

### POST /api/v1/approvals/{approval_id}/decision

```json
{ "decision": "approve", "actor": "operator", "reason": "Reviewed" }
```

Only exact `approve` / `reject` values are accepted. Actor labels are bounded,
control-character sanitized, and default to `operator`. Rejection never
executes; approval follows the existing revalidation/tamper-check and separate
admin adapter path. Expired → 410; already decided/terminal → 409; invalid
decision → 422. In mock mode the action is recorded as `simulated: true` and
never reaches a database. Real privileged execution remains opt-in via
`AGENT_ACTIONS_ENABLED` plus separate admin credentials, and is unverified.

## POST /api/v1/knowledge/documents

Mock-only document ingestion using the existing vector adapter:

```json
{ "documents": [{ "text": "Db2 operational note", "metadata": {"source": "demo"} }] }
```

Accepts 1–20 documents, each up to 20,000 characters, and returns
`documents_added` and `mock: true`. Real-mode ingestion returns 503 until the
Db2/Ollama/DB2VS path is verified.

## POST /api/v1/sql/execute

Body `{ "sql": "...", "session_id": null }`. Validates (fail-closed), applies the hard
row cap, runs the best-effort EXPLAIN dry-run, executes read-only under the policy timeout,
records history + audit. Rejected SQL → 422 `SQL_REJECTED`.

## POST /api/v1/sql/explain

Body `{ "sql": "...", "session_id": null }`. Validates the SQL through the same gate, then
returns the access plan **without executing** the statement.

```json
{ "request_id": "...", "mock": false, "status": "OK|UNAVAILABLE|FAILED",
  "source": "db2|mock|none", "explained_sql": "...", "total_cost": 25.5,
  "operators": [ { "operator_id", "operator_type", "total_cost", "io_cost", "cpu_cost" } ],
  "objects":   [ { "schema_name", "name", "object_type" } ],
  "summary": ["..."], "sqlstate": null, "hint": null, "detail": null,
  "warnings": [], "latency_ms": 12 }
```
`UNAVAILABLE` / `FAILED` are **HTTP 200** (graceful fallback, with `hint`); only SQL rejected by
the gate is an error (422 `SQL_REJECTED`). `source="mock"` plans are synthetic.

## GET /api/v1/dba/tools · POST /api/v1/dba/tools/{tool_id}/run

Fixed catalog (`catalog.*`, SYSCAT) and monitoring (`monitor.*`, MON_GET_*) tools — see
[`DBA_TOOLS.md`](DBA_TOOLS.md). Run body: `{ "params": { "schema"?, "table"?, "limit"? },
"session_id"? }`; response `{ request_id, tool_id, kind, title, mock, source: "db2|mock",
params, columns, rows, row_count, truncated, latency_ms, notes }`.

## Database error mapping (SQLSTATE → HTTP)

| SQLSTATE / category | HTTP | `error.code` |
|---|---|---|
| `57014` timeout | 504 | `UPSTREAM_TIMEOUT` |
| `42501`, class `425` (authorization) | 403 | `DB_PERMISSION_DENIED` |
| class `427` (undefined object) | 404 | `DB_OBJECT_NOT_FOUND` |
| class `426`, `428`, `42703` (syntax/semantics) | 422 | `DB_SQL_ERROR` |
| class `08`, `28`, `570/571`, `911` (connect/auth/resource) | 503 | `ADAPTER_UNAVAILABLE` |
| anything else | 502 | `DB_ERROR` |
| invalid tool parameters | 422 | `INVALID_TOOL_PARAMS` |
| unknown tool | 404 | `NOT_FOUND` |

`error.detail` carries `sqlstate`, `category` and a curated `hint` — never credentials.

## Other routes

`GET /` info · `GET /docs` Swagger UI · `GET /openapi.json` ·
`GET /api/v1/ready` (readiness gate; 503 when any probe is not ok) ·
static SPA at `/` when `frontend/dist` exists (`SERVE_FRONTEND=true`).

**Not part of this contract:** autonomous LangChain/LangGraph agent execution.
Proposal generation remains deterministic and action inputs are explicit.
