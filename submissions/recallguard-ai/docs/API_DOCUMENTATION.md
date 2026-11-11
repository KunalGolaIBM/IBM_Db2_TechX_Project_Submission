# API Documentation

Base path `/api/v1`. Interactive OpenAPI docs are at `http://localhost:8000/docs`.

**Identity headers (authentication-ready):** `X-User-Id`, `X-User-Role` (`viewer` | `analyst` | `recall_manager` | `admin`). When the headers are missing, the caller is treated as a demo analyst, unless `REQUIRE_AUTH_HEADERS=true`, in which case the request gets a 401. Every response carries `X-Data-Engine: IBM-Db2 | DEV-MODE-NOT-DB2`.

**Errors:** `{"error": "<kind>", "detail": ...}`

| Status | Kind | Meaning |
|---|---|---|
| 404 | `not_found` | Resource does not exist |
| 409 | `invalid_state` | State transition not allowed |
| 409 | `integrity_violation` | Database constraint rejected the write |
| 413 | | File too large |
| 422 | `validation_error` / `upload_rejected` | Invalid request body or upload |
| 403 | | Role lacks the permission |
| 503 | `database_unavailable` | Database cannot be reached |

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/health` | any | DB mode/connection/latency/vector support, AI mode, integration versions |
| GET | `/dashboard/summary` | read | KPIs, risk & status distribution, audit timeline, network counts |
| GET | `/incidents` | read | List (`?status=`) |
| POST | `/incidents` | analyst+ | Create. Body: `title, source_ref, contaminant, contamination_category, severity, supplier_id?, discovered_at?, description?`. 404 if the lot/batch is not in Db2 |
| GET | `/incidents/{id}` | read | Incident + comments + evidence + recalls + allowed transitions |
| POST | `/incidents/{id}/investigate` | analyst+ | 202. Starts the 5-agent run (`?background=false` runs synchronously) |
| POST | `/incidents/{id}/reinvestigate` | analyst+ | 202. Re-run with a reason |
| GET | `/incidents/{id}/investigation` | read | Latest run: status, mode, progress, each agent's output and log |
| POST | `/incidents/{id}/comments` | analyst+ | Add a review comment |
| GET | `/supply-chain/trace/{ref}` | read | Graph nodes/edges (upstream + downstream + distribution), affected flags, queries executed |
| GET | `/supply-chain/impact/{ref}` | read | Full impact report: batches, products, hops, locations, data gaps, summary |
| GET | `/supply-chain/catalog` | read | Lots, batches, suppliers (contacts redacted below recall_manager) |
| GET | `/recalls` | read | Recall list with item counts and units |
| POST | `/recalls/generate` | analyst+ | Body `{incident_id}`. Creates a `PENDING_APPROVAL` recall from the latest verified run |
| GET | `/recalls/{id}` | read | Plan, items, risk, verification, actions, progress |
| POST | `/recalls/{id}/approve` | recall_manager | Body `{comment}`. Approves, then creates SIMULATED actions → `EXECUTING` |
| POST | `/recalls/{id}/reject` | recall_manager | Body `{comment}` (required) |
| POST | `/recalls/{id}/actions/{action_id}` | recall_manager | Update an action status / units recovered |
| POST | `/recalls/{id}/simulate-acknowledgements` | recall_manager | Demo: simulated partner responses |
| POST | `/recalls/{id}/complete` | recall_manager | 409 while actions are open |
| GET | `/evidence` | read | Documents (`?incident_id=&doc_type=`) with extracted claims |
| GET | `/evidence/search?q=` | read | Cited retrieval; reports the engine used |
| POST | `/evidence/upload` | analyst+ | multipart `file`, `incident_id?`, `doc_type?`. pdf/txt/md/csv, ≤10 MB |
| GET | `/evidence/{id}` | read | Document detail |
| POST | `/evidence/{id}/verification` | recall_manager | `VERIFIED` / `DISPUTED` / `UNVERIFIED` |
| GET | `/audit-logs` | read | `?entity_ref=&limit=` |
| GET | `/demo/sample-lab-report` | any | Fictional TOM-2026-041 lab report PDF |
| GET | `/demo/tomato-incident` | any | Demo incident template |
| POST | `/demo/tomato` | analyst+ | Server-side one-shot demo run (used by tests) |
| POST | `/demo/reset` | recall_manager | Removes `is_demo` incidents and their dependants |

### Example
```bash
curl -s -X POST localhost:8000/api/v1/incidents -H 'Content-Type: application/json' \
  -H 'X-User-Id: qa@example.com' -H 'X-User-Role: analyst' \
  -d '{"title":"Salmonella in tomato puree","source_ref":"TOM-2026-041","contaminant":"Salmonella","contamination_category":"MICROBIAL","severity":"CRITICAL"}'
```
