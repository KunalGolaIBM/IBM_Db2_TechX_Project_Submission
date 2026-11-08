# MetricGuard API Contract — v1.2.0

Pydantic source of truth: [`backend/metricguard/api/schemas.py`](../src/backend/metricguard/api/schemas.py) · Machine-readable: [`docs/openapi.json`](../src/docs/openapi.json) (`make openapi`). The JSON examples below use real values from the seeded Db2 dataset.

The frontend must not depend on any field that is not listed here. Adding an **optional** field is a minor version change (1.x). Removing or renaming a field, or changing its meaning, requires 2.0.

**Real responses** captured from the running code against live Db2 are in [`docs/examples/`](../src/docs/examples/) (regenerate with `scripts/capture_api_examples.py`). Prefer them over the abbreviated snippets below.

### Changelog

**1.2.0, Stage 4 clarifications (2026-11-07)**: no schema change, `api_version` stays `1.2.0`.
- `answer.headline` for a ranked plan (dimensions + `order_by` on a metric + `limit`) is now the first-ranked row, labelled e.g. `"Top region: NA · Net Revenue (Q2 2026)"`. Before, it was the all-groups control total, which answered "Which region had the highest net revenue?" with a number that is not any region's value. Unranked grouped plans keep the control total.
- `PLANNER_TIMEOUT_SECONDS` default 45 → 30 s per attempt (see §6.6).

**1.2.0 (Stage 3.5, 2026-11-07)** — additive only; no field was removed, renamed or re-typed.
- `planner.provider` (`"meta"` | `"anthropic"` | `"metricguard-rules"`, optional) on every analyze response. See §6.7.
- `GET /api/health` → `planner.provider` may now be `"meta"`.
- `planner.name` is provider-specific for real models: `"langchain-meta"`, `"langchain-anthropic"` (was `"langchain-structured"` in 1.1.0, which never served a live request). `"rules-demo"` is unchanged. Audit `planner` stores this name.
- `503 PLANNER_UNAVAILABLE` message now names `AI_PROVIDER`; behavior is unchanged: no silent switch to the demo planner.

**1.1.0 (Stage 2, 2026-11-07)** — additive only; no field was removed, renamed or re-typed.
- `POST /api/analyze` is implemented (no more `501`).
- `planner.execution_mode` (`"LLM"` | `"DEMO_RULE_BASED"`) and `planner.disclosure` on every analyze response. See §6.7.
- `GET /api/health`: `planner.execution_mode`; `planner.provider` is `"meta"`, `"anthropic"` or `"metricguard-rules"` (`"meta"` added in 1.2.0).
- Audit: `execution_mode` on list items; `execution_mode`, `planner_model`, `metric_definitions[]`, `answer_summary` on detail.
- New reason codes: `PLAN_SCHEMA_INVALID`, `COMPILER_REJECTED`, `SQL_NOT_PARAMETERIZED` (BLOCKED); `REGISTRY_UNVERIFIED`, `PRIVILEGED_CONNECTION` (warning).
- `503 PLANNER_UNAVAILABLE` also covers LLM provider failures (auth, unknown model, rate limit, 5xx, timeout).
- V09 also recomputes ratio metrics (AOV, refund rate) from their components for single-row KPI plans.

**1.0.0 (Stage 1)** — initial frozen contract.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000` (dev). All paths start with `/api`. |
| Format | `application/json; charset=utf-8`. Unknown request fields are rejected (`422`). |
| Timestamps | ISO-8601. Response timestamps are UTC (`2026-11-07T20:15:03.412Z` or `+00:00`). Dates are `YYYY-MM-DD`. |
| Identifiers | `request_id` is a UUID v4 string. Metric references are `name@version` (e.g. `net_revenue@1.0.0`). |
| Numbers in results | JSON numbers. `USD` uses 2 decimals, `COUNT` is an integer, and `RATIO` is a fraction (`0.076714` = 7.6714%, so the UI multiplies by 100 to show a percent). `null` means "undefined" (e.g. AOV with 0 orders). It never means 0. |
| Strings in results | Dimension values are codes (`EMEA`, `2026-01`). Labels for codes come from `GET /api/metrics` (`dimensions[].allowed_values`); the UI may map codes to friendly names. |
| HTTP status policy | `POST /api/analyze` returns **200 for every analysis outcome**: `VERIFIED`, `EXECUTED_WITH_WARNINGS`, `AMBIGUOUS`, `BLOCKED` and `EXECUTION_FAILED`. Non-2xx codes are reserved for transport-level problems: invalid request (`422`), unknown audit id (`404`), unimplemented (`501`), unavailable dependencies (`503`). |
| CORS | `CORS_ORIGINS` env (default `http://localhost:3000`). Methods `GET`, `POST`. |
| Auth | None in v1 (local demo). |

## 2. Validation status (the trust signal)

Every `/api/analyze` response has exactly one `status`. These five are the only values:

| Status | SQL executed? | Numbers shown? | Precise meaning |
|---|:-:|:-:|---|
| `VERIFIED` | yes | yes | Every check in the table below is `PASS` or `SKIPPED`. The plan uses only approved metrics at their current versions. Registry hashes match the approved rows in Db2. The SQL was produced by the deterministic compiler, passed the static guard and is fully parameterized. Db2 executed it. Additive metrics reconcile against an independent control-total query. The result is complete: not truncated, not empty, and the date range lies within data coverage. |
| `EXECUTED_WITH_WARNINGS` | yes | yes, with a warning banner | The SQL is governed and executed and the numbers are correct for the plan. At least one post-execution check is `WARN`, or a verification could not be completed. Examples: rows truncated to `max_rows`, empty result, date range partly outside coverage, reconciliation could not run. Each warning appears in `verification.reasons` with `severity: "warning"`. |
| `AMBIGUOUS` | no | no | The question maps to more than one approved interpretation (e.g. "revenue" means gross or net; "last quarter" is relative and has no anchor). `clarification` lists the options. Each option includes a `suggested_question` that the UI re-submits verbatim. |
| `BLOCKED` | no | no | The request violates policy before execution. Causes: unknown or unapproved metric, version mismatch, disallowed dimension or filter, invalid filter value, write or DDL intent, out-of-scope question, guard rejection, or registry drift. `verification.reasons` explains why with `severity: "error"`. |
| `EXECUTION_FAILED` | attempted | no | The plan was valid, but Db2 failed: connection, timeout or SQL error. `error` is populated (`DB2_ERROR`, `QUERY_TIMEOUT` or `DATABASE_UNAVAILABLE`, with `sqlstate`). |

### Verification checks (`verification.checks[]`)

`id` and `name` are stable, so the UI may render them as a checklist. `status` is one of `PASS | WARN | FAIL | SKIPPED`.

| id | name | Meaning | Failure leads to |
|---|---|---|---|
| V01 | `plan_schema` | The planner output parses as a `QueryPlan` (malformed, truncated or refused LLM output fails here). | BLOCKED (`PLAN_SCHEMA_INVALID`) |
| V02 | `metric_approval` | All metrics exist, are `APPROVED` and use the current version. | BLOCKED |
| V03 | `registry_integrity` | The runtime definition hash equals `METRIC_DEFINITIONS.DEFINITION_HASH` in Db2. | BLOCKED (`REGISTRY_DRIFT`); WARN if Db2 could not be read |
| V04 | `dimension_filter_policy` | Dimensions, filters and values are allowed for every metric. | BLOCKED |
| V05 | `deterministic_sql` | SQL was generated by `metricguard-compiler`. | BLOCKED |
| V06 | `sql_guard` | Single `SELECT` statement, allow-listed tables, no DDL/DML/system catalogs. | BLOCKED |
| V07 | `parameterized` | Marker count equals parameter count, and no plan values appear inside the SQL text. | BLOCKED |
| V08 | `execution` | Db2 executed the query within the timeout. | EXECUTION_FAILED |
| V09 | `reconciliation` | For additive metrics with dimensions, the sum of groups equals an independent ungrouped Db2 query, and every returned group equals the same group in a separate control grouping (so top-N and truncated results are checked too). Non-additive metrics (AOV, refund rate) are recomputed from reconciled components, per group and overall, including single-row KPI plans. `SKIPPED` only for a single additive total. | WARN → EXECUTED_WITH_WARNINGS |
| V10 | `completeness` | Not truncated, at least one row, date range within coverage. | WARN → EXECUTED_WITH_WARNINGS |
| V11 | `null_semantics` | `null` appears only where the registry allows it (AOV or refund rate with a zero denominator). | WARN → EXECUTED_WITH_WARNINGS |

Assumptions are not warnings. A defaulted date range (`DEFAULT_DATE_RANGE`) is disclosed in `assumptions[]` and as an `info` reason, and it does not downgrade `VERIFIED`.

**Precedence:** BLOCKED > AMBIGUOUS > EXECUTION_FAILED > EXECUTED_WITH_WARNINGS > VERIFIED. Checks that do not run because an earlier one failed are reported as `SKIPPED`.

### Reason codes (`verification.reasons[].code`)

| Code | Severity | Status |
|---|---|---|
| `AMBIGUOUS_METRIC`, `AMBIGUOUS_TIME_RANGE` | warning | AMBIGUOUS |
| `UNKNOWN_METRIC`, `METRIC_NOT_APPROVED`, `METRIC_VERSION_MISMATCH`, `DUPLICATE_METRIC` | error | BLOCKED |
| `UNKNOWN_DIMENSION`, `DIMENSION_NOT_ALLOWED`, `DUPLICATE_DIMENSION` | error | BLOCKED |
| `UNKNOWN_FILTER`, `FILTER_NOT_ALLOWED`, `FILTER_VALUE_NOT_ALLOWED`, `DUPLICATE_FILTER`, `INVALID_ORDER_BY` | error | BLOCKED |
| `PLAN_SCHEMA_INVALID` (planner output not a valid plan), `COMPILER_REJECTED`, `SQL_NOT_PARAMETERIZED` | error | BLOCKED |
| `WRITE_INTENT`, `OUT_OF_SCOPE`, `REGISTRY_DRIFT` | error | BLOCKED |
| `SQL_NOT_SELECT`, `SQL_MULTI_STATEMENT`, `SQL_FORBIDDEN_KEYWORD`, `SQL_SYSTEM_CATALOG`, `SQL_TABLE_NOT_ALLOWED`, `SQL_BLOCK_COMMENT` | error | BLOCKED |
| `DB2_ERROR`, `QUERY_TIMEOUT`, `DATABASE_UNAVAILABLE` | error | EXECUTION_FAILED |
| `RESULT_TRUNCATED`, `EMPTY_RESULT`, `RANGE_OUTSIDE_COVERAGE`, `RECONCILIATION_MISMATCH`, `RECONCILIATION_UNAVAILABLE`, `UNEXPECTED_NULL` | warning | EXECUTED_WITH_WARNINGS |
| `REGISTRY_UNVERIFIED` (Db2 registry unreadable), `PRIVILEGED_CONNECTION` (no read-only account configured) | warning | EXECUTED_WITH_WARNINGS |
| `DEFAULT_DATE_RANGE`, `RECONCILED` | info | any executed status |

---

## 3. `GET /api/health`

Returns `200` when Db2 is reachable and `503` when it is not. Both use the same body. `status: "ok"` requires Db2 to be up, all 6 tables present, and `db_hash_match: true`.

```json
{
  "status": "ok",
  "api_version": "1.2.0",
  "service_version": "0.1.0",
  "time": "2026-11-07T20:15:03.412000Z",
  "database": {
    "status": "up",
    "vendor": "IBM Db2",
    "server_version": "DB2/LINUXX8664 12.01.0500",
    "service_level": "DB2 v12.1.5.0",
    "database": "MGDB",
    "schema_name": "METRICGUARD",
    "latency_ms": 18.4,
    "tables_present": 6,
    "tables_expected": 6,
    "error": null
  },
  "registry": {
    "metrics": 6,
    "fingerprint": "0c78f16f500bb55d516877d2d9bd0d8124bb2ae7bd3a086a1ea4fa8ed16cd362",
    "db_hash_match": true
  },
  "planner": { "status": "ready", "provider": "meta", "model": "muse-spark-1.3", "execution_mode": "LLM" }
}
```

`planner` reflects what `POST /api/analyze` will use: `{"status": "ready", "provider": "metricguard-rules", "model": null, "execution_mode": "DEMO_RULE_BASED"}` without an API key (`PLANNER_MODE=auto`), or `{"status": "not_configured", "provider": null, "model": null, "execution_mode": null}` when `PLANNER_MODE=llm` and no key is set.

Down (`503`): `database.status: "down"`, the version, latency and table fields are `null`, and `database.error = {"code": "DATABASE_UNAVAILABLE", "message": "IBM Db2 is unavailable.", "details": [], "sqlstate": "08001"}`. `registry.db_hash_match` is `null`.

## 4. `GET /api/metrics`

```json
{
  "registry_fingerprint": "0c78f16f500bb55d516877d2d9bd0d8124bb2ae7bd3a086a1ea4fa8ed16cd362",
  "data_coverage": { "start_date": "2026-01-01", "end_date": "2026-06-30", "timezone": "UTC" },
  "metrics": [
    {
      "name": "net_revenue",
      "version": "1.0.0",
      "display_name": "Net Revenue",
      "description": "Gross revenue minus processed refunds on the same completed orders.",
      "calculation": "gross_revenue - refund_amount, both computed at order-line grain for the same eligible orders.",
      "unit": "USD",
      "scale": 2,
      "kind": "DERIVED",
      "additive": true,
      "eligible_order_statuses": ["COMPLETED"],
      "date_attribution": "Attributed to the UTC order timestamp ORDERS.ORDER_TS. …",
      "null_handling": "Lines without refunds contribute 0 refund (COALESCE). Empty result yields 0.00.",
      "refund_treatment": "Refunds are attributed to the order date of the refunded order (cohort basis), …",
      "discount_treatment": "Line discounts (ORDER_ITEMS.DISCOUNT_AMOUNT, a line total) are subtracted: …",
      "allowed_dimensions": ["order_month", "region", "channel", "product_category"],
      "allowed_filters": ["region", "channel", "product_category"],
      "synonyms": ["revenue after refunds", "net sales"],
      "lifecycle_status": "APPROVED",
      "owner": "finance-analytics",
      "definition_hash": "471c17a8d0ab04f51b24dee73de00272b26c4d91cb26d1901751c439f5d26232"
    }
  ],
  "dimensions": [
    { "name": "order_month", "display_name": "Order month", "description": "Calendar month (UTC) of ORDERS.ORDER_TS, formatted YYYY-MM.", "data_type": "string", "allowed_values": null },
    { "name": "region", "display_name": "Region", "description": "Sales region of the order (ORDERS.REGION_CODE).", "data_type": "string", "allowed_values": ["NA", "EMEA", "APAC", "LATAM"] }
  ],
  "filters": [
    { "name": "region", "display_name": "Region", "operators": ["in"], "allowed_values": ["NA", "EMEA", "APAC", "LATAM"] }
  ]
}
```

The response contains all 6 metrics, 4 dimensions (`order_month`, `region`, `channel`, `product_category`) and 3 filters. Text marked `…` above is abbreviated in this document only.

## 5. `GET /api/examples`

```json
{
  "examples": [
    {
      "id": "ex-05-emea-monthly-q1",
      "question": "Show net revenue and order count by month for EMEA in Q1 2026.",
      "category": "trend",
      "description": "Region filter plus the Jan-31 23:59:59 / Feb-01 00:00:00 boundary canaries.",
      "expected_status": "VERIFIED"
    },
    {
      "id": "ex-09-blocked-aov-by-category",
      "question": "What is the average order value by product category?",
      "category": "governance",
      "description": "An order cannot be split across categories, so AOV by category is not an approved breakdown.",
      "expected_status": "BLOCKED"
    }
  ]
}
```

There are 10 examples: 7 `VERIFIED`, 1 `AMBIGUOUS` and 2 `BLOCKED`. `category` is one of `trend | comparison | ranking | kpi | governance`.

## 6. `POST /api/analyze`

### Request

```json
{ "question": "Show net revenue and order count by month for EMEA in Q1 2026.", "options": { "max_rows": 100 } }
```

| Field | Type | Rules |
|---|---|---|
| `question` | string | required, 3–1000 chars |
| `options.max_rows` | int | optional, 1–500, default 100 |

### Response object (all statuses)

| Field | Type | Present when |
|---|---|---|
| `request_id` | uuid | always |
| `created_at` | datetime | always |
| `api_version` | `"1.2.0"` | always |
| `status` | ValidationStatus | always |
| `question` | string | always (echo) |
| `answer` | `{summary, headline}` \| null | VERIFIED, EXECUTED_WITH_WARNINGS. `headline`: single value for KPI plans, the first-ranked row for top/bottom-N plans, otherwise the control total |
| `plan` | QueryPlan \| null | when a plan was produced (also for BLOCKED by policy; null for WRITE_INTENT / OUT_OF_SCOPE / AMBIGUOUS) |
| `assumptions` | `[{code, message}]` | always (may be empty) |
| `metrics` | `[MetricUsage]` | always (empty if no plan) |
| `sql` | SqlBlock \| null | VERIFIED, EXECUTED_WITH_WARNINGS, EXECUTION_FAILED |
| `result` | ResultBlock \| null | VERIFIED, EXECUTED_WITH_WARNINGS |
| `chart` | ChartSpec \| null | VERIFIED, EXECUTED_WITH_WARNINGS |
| `verification` | Verification | always |
| `clarification` | Clarification \| null | AMBIGUOUS only |
| `timing` | Timing | always (`execution_ms`, `verification_ms` null if not reached) |
| `planner` | `{name, provider, model, execution_mode, disclosure}` | always (§6.7) |
| `audit` | `{persisted, url}` | always; `persisted:false` only if the audit write itself failed |
| `error` | ErrorBody \| null | EXECUTION_FAILED only |

`answer.summary` is produced by a deterministic template from `result.rows`, never written freely by the LLM. Every number in the summary therefore equals a number in `result`.

**QueryPlan**
- `metrics[{name,version}]` (1–4)
- `dimensions[]` (0–2)
- `filters[{field, operator:"in", values[]}]` (0–5)
- `date_range{start_date, end_date, attribution:"order_date", source:"explicit"|"default"}`
- `order_by[{field, direction:"asc"|"desc"}]` (0–3)
- `limit` (int|null)

**Chart rules** (`chart.type`)

| Plan | Chart |
|---|---|
| no dimensions | `kpi`; `x: null`; one series per metric, each with a single point (`x: null`) |
| 1 dimension = `order_month` | `line` |
| 1 categorical dimension | `bar` |
| 2 dimensions | first dimension on x, one series per value of the second dimension, first metric only. `line` if x is `order_month`, otherwise `grouped_bar` |

`chart.series` only contains metrics that share the **first metric's unit**. Other metrics still appear in `result`. Series `key` is the metric name, or `"<metric>:<value>"` for 2-dimension charts.

### 6.1 `VERIFIED` (real values from Db2)

```json
{
  "request_id": "6f1c2a7e-3b8d-4e51-9a0c-2d4b7e9f1a33",
  "created_at": "2026-11-07T20:16:41.208000Z",
  "api_version": "1.2.0",
  "status": "VERIFIED",
  "question": "Show net revenue and order count by month for EMEA in Q1 2026.",
  "answer": {
    "summary": "EMEA net revenue in Q1 2026 was $79,292.47 across 339 completed orders; March was the highest month at $31,392.69.",
    "headline": { "metric": "net_revenue", "label": "Net Revenue (Q1 2026, EMEA)", "value": 79292.47, "unit": "USD", "formatted": "$79,292.47" }
  },
  "plan": {
    "metrics": [ { "name": "net_revenue", "version": "1.0.0" }, { "name": "order_count", "version": "1.0.0" } ],
    "dimensions": ["order_month"],
    "filters": [ { "field": "region", "operator": "in", "values": ["EMEA"] } ],
    "date_range": { "start_date": "2026-01-01", "end_date": "2026-03-31", "attribution": "order_date", "source": "explicit" },
    "order_by": [],
    "limit": null
  },
  "assumptions": [],
  "metrics": [
    { "name": "net_revenue", "version": "1.0.0", "display_name": "Net Revenue", "unit": "USD", "scale": 2, "definition_hash": "471c17a8d0ab04f51b24dee73de00272b26c4d91cb26d1901751c439f5d26232" },
    { "name": "order_count", "version": "1.0.0", "display_name": "Order Count", "unit": "COUNT", "scale": 0, "definition_hash": "c1f1986331b0122264c5be4793d30003583ca0807e16e066daf967de0ed6a364" }
  ],
  "sql": {
    "text": "WITH eligible_orders AS (\n    SELECT o.ORDER_ID, o.ORDER_TS, o.REGION_CODE, o.CHANNEL_CODE\n    FROM METRICGUARD.ORDERS o\n    WHERE o.STATUS IN (CAST(? AS VARCHAR(16)))\n      AND o.ORDER_TS >= CAST(? AS TIMESTAMP)\n      AND o.ORDER_TS < CAST(? AS TIMESTAMP)\n      AND o.REGION_CODE IN (CAST(? AS VARCHAR(16)))\n),\nline_refunds AS (\n    -- Pre-aggregate refunds per order line BEFORE joining (no fan-out).\n    SELECT r.ORDER_ITEM_ID, SUM(r.REFUND_AMOUNT) AS REFUND_AMOUNT\n    FROM METRICGUARD.REFUNDS r\n    JOIN eligible_orders e ON e.ORDER_ID = r.ORDER_ID\n    WHERE r.STATUS = CAST(? AS VARCHAR(12))\n    GROUP BY r.ORDER_ITEM_ID\n),\nline_facts AS (\n    SELECT e.ORDER_ID, e.ORDER_TS, e.REGION_CODE, e.CHANNEL_CODE, p.CATEGORY,\n           (i.QUANTITY * i.UNIT_PRICE) - i.DISCOUNT_AMOUNT AS LINE_REVENUE,\n           COALESCE(lr.REFUND_AMOUNT, 0) AS LINE_REFUND\n    FROM eligible_orders e\n    JOIN METRICGUARD.ORDER_ITEMS i ON i.ORDER_ID = e.ORDER_ID\n    JOIN METRICGUARD.PRODUCTS p ON p.PRODUCT_ID = i.PRODUCT_ID\n    LEFT JOIN line_refunds lr ON lr.ORDER_ITEM_ID = i.ORDER_ITEM_ID\n)\nSELECT VARCHAR_FORMAT(f.ORDER_TS, 'YYYY-MM') AS ORDER_MONTH,\n       CAST(COALESCE(SUM(f.LINE_REVENUE), 0) - COALESCE(SUM(f.LINE_REFUND), 0) AS DECIMAL(18,2)) AS NET_REVENUE,\n       COUNT(DISTINCT f.ORDER_ID) AS ORDER_COUNT\nFROM line_facts f\nGROUP BY VARCHAR_FORMAT(f.ORDER_TS, 'YYYY-MM')\nORDER BY ORDER_MONTH ASC\nFETCH FIRST 101 ROWS ONLY",
    "dialect": "db2",
    "parameters": [
      { "position": 1, "name": "eligible_status_1", "db2_type": "VARCHAR(16)", "value": "COMPLETED" },
      { "position": 2, "name": "date_start_inclusive", "db2_type": "TIMESTAMP", "value": "2026-01-01 00:00:00" },
      { "position": 3, "name": "date_end_exclusive", "db2_type": "TIMESTAMP", "value": "2026-04-01 00:00:00" },
      { "position": 4, "name": "filter_region_1", "db2_type": "VARCHAR(16)", "value": "EMEA" },
      { "position": 5, "name": "refund_status", "db2_type": "VARCHAR(12)", "value": "PROCESSED" }
    ],
    "generated_by": "metricguard-compiler",
    "sql_hash": "862486670a4b4f555b043d7f545a1e9aebb37426f832c9809084bfa8aff6cba4",
    "tables": ["METRICGUARD.ORDERS", "METRICGUARD.ORDER_ITEMS", "METRICGUARD.PRODUCTS", "METRICGUARD.REFUNDS"]
  },
  "result": {
    "columns": [
      { "name": "order_month", "label": "Order month", "role": "dimension", "data_type": "string", "unit": null, "scale": null },
      { "name": "net_revenue", "label": "Net Revenue", "role": "metric", "data_type": "decimal", "unit": "USD", "scale": 2 },
      { "name": "order_count", "label": "Order Count", "role": "metric", "data_type": "integer", "unit": "COUNT", "scale": 0 }
    ],
    "rows": [
      { "order_month": "2026-01", "net_revenue": 25347.46, "order_count": 114 },
      { "order_month": "2026-02", "net_revenue": 22552.32, "order_count": 95 },
      { "order_month": "2026-03", "net_revenue": 31392.69, "order_count": 130 }
    ],
    "row_count": 3,
    "truncated": false
  },
  "chart": {
    "type": "line",
    "title": "Net Revenue by Order month",
    "x": { "field": "order_month", "label": "Order month" },
    "series": [
      { "key": "net_revenue", "label": "Net Revenue", "metric": "net_revenue", "unit": "USD",
        "points": [ { "x": "2026-01", "y": 25347.46 }, { "x": "2026-02", "y": 22552.32 }, { "x": "2026-03", "y": 31392.69 } ] }
    ]
  },
  "verification": {
    "status": "VERIFIED",
    "summary": "Approved metrics, governed SQL, executed on IBM Db2 and reconciled with an independent control total.",
    "reasons": [
      { "code": "RECONCILED", "severity": "info", "message": "Monthly net_revenue and order_count sum to the Q1 control totals (79,292.47; 339)." }
    ],
    "checks": [
      { "id": "V01", "name": "plan_schema", "status": "PASS", "detail": "Plan parsed." },
      { "id": "V02", "name": "metric_approval", "status": "PASS", "detail": "net_revenue@1.0.0, order_count@1.0.0 approved." },
      { "id": "V03", "name": "registry_integrity", "status": "PASS", "detail": "Definition hashes match METRICGUARD.METRIC_DEFINITIONS." },
      { "id": "V04", "name": "dimension_filter_policy", "status": "PASS", "detail": "order_month and region filter allowed." },
      { "id": "V05", "name": "deterministic_sql", "status": "PASS", "detail": "Generated by metricguard-compiler." },
      { "id": "V06", "name": "sql_guard", "status": "PASS", "detail": "Single SELECT on 4 allow-listed tables." },
      { "id": "V07", "name": "parameterized", "status": "PASS", "detail": "5 markers, 5 parameters." },
      { "id": "V08", "name": "execution", "status": "PASS", "detail": "Db2 returned 3 rows." },
      { "id": "V09", "name": "reconciliation", "status": "PASS", "detail": "Group sums equal control totals." },
      { "id": "V10", "name": "completeness", "status": "PASS", "detail": "3 rows, not truncated, range within coverage." },
      { "id": "V11", "name": "null_semantics", "status": "PASS", "detail": "No NULL metric values." }
    ]
  },
  "clarification": null,
  "timing": { "total_ms": 912.4, "planning_ms": 803.1, "validation_ms": 1.2, "execution_ms": 74.6, "verification_ms": 33.5 },
  "planner": { "name": "langchain-meta", "provider": "meta", "model": "muse-spark-1.3", "execution_mode": "LLM", "disclosure": null },
  "audit": { "persisted": true, "url": "/api/audit/6f1c2a7e-3b8d-4e51-9a0c-2d4b7e9f1a33" },
  "error": null
}
```

The values above are correct for the seeded dataset (the same numbers appear in `docs/examples/grouped-analysis.json`, captured from live Db2). `request_id`, `created_at`, `timing`, the check `detail` strings and the summary wording are illustrative; the real summary template is shown in the captured examples.

### 6.2 `EXECUTED_WITH_WARNINGS` (diff from 6.1)

```json
{
  "status": "EXECUTED_WITH_WARNINGS",
  "plan": { "…": "…", "date_range": { "start_date": "2026-06-01", "end_date": "2026-08-31", "attribution": "order_date", "source": "explicit" } },
  "verification": {
    "status": "EXECUTED_WITH_WARNINGS",
    "summary": "Executed with governed SQL, but the requested period extends beyond available data.",
    "reasons": [
      { "code": "RANGE_OUTSIDE_COVERAGE", "severity": "warning", "message": "Data covers 2026-01-01..2026-06-30; July and August 2026 have no orders." }
    ],
    "checks": [ { "id": "V10", "name": "completeness", "status": "WARN", "detail": "Range extends 62 days beyond coverage." } ]
  }
}
```

### 6.3 `AMBIGUOUS`

```json
{
  "request_id": "b7d0c3e1-58a2-4f0b-9a71-0e6c2f4d8a10",
  "created_at": "2026-11-07T20:18:02.004000Z",
  "api_version": "1.2.0",
  "status": "AMBIGUOUS",
  "question": "What was our revenue last quarter?",
  "answer": null,
  "plan": null,
  "assumptions": [],
  "metrics": [],
  "sql": null,
  "result": null,
  "chart": null,
  "verification": {
    "status": "AMBIGUOUS",
    "summary": "\"Revenue\" matches two approved metrics and \"last quarter\" needs an anchor date.",
    "reasons": [
      { "code": "AMBIGUOUS_METRIC", "severity": "warning", "message": "\"revenue\" could mean gross_revenue or net_revenue." },
      { "code": "AMBIGUOUS_TIME_RANGE", "severity": "warning", "message": "\"last quarter\" is relative; data covers Q1–Q2 2026." }
    ],
    "checks": [
      { "id": "V01", "name": "plan_schema", "status": "SKIPPED", "detail": "No single plan." }
    ]
  },
  "clarification": {
    "prompt": "Which revenue do you mean?",
    "options": [
      { "id": "net_revenue", "label": "Net Revenue", "description": "After processed refunds.", "suggested_question": "What was net revenue in Q2 2026?" },
      { "id": "gross_revenue", "label": "Gross Revenue", "description": "After discounts, before refunds.", "suggested_question": "What was gross revenue in Q2 2026?" }
    ]
  },
  "timing": { "total_ms": 655.0, "planning_ms": 652.7, "validation_ms": 0.0, "execution_ms": null, "verification_ms": null },
  "planner": { "name": "langchain-meta", "provider": "meta", "model": "muse-spark-1.3", "execution_mode": "LLM", "disclosure": null },
  "audit": { "persisted": true, "url": "/api/audit/b7d0c3e1-58a2-4f0b-9a71-0e6c2f4d8a10" },
  "error": null
}
```

### 6.4 `BLOCKED`

```json
{
  "request_id": "0e9a4b52-7c1d-4f3e-8b6a-5d2c1e0f9b77",
  "created_at": "2026-11-07T20:19:10.550000Z",
  "api_version": "1.2.0",
  "status": "BLOCKED",
  "question": "What is the average order value by product category?",
  "answer": null,
  "plan": {
    "metrics": [ { "name": "average_order_value", "version": "1.0.0" } ],
    "dimensions": ["product_category"],
    "filters": [],
    "date_range": { "start_date": "2026-01-01", "end_date": "2026-06-30", "attribution": "order_date", "source": "default" },
    "order_by": [],
    "limit": null
  },
  "assumptions": [ { "code": "DEFAULT_DATE_RANGE", "message": "No period given; using data coverage 2026-01-01..2026-06-30." } ],
  "metrics": [ { "name": "average_order_value", "version": "1.0.0", "display_name": "Average Order Value", "unit": "USD", "scale": 2, "definition_hash": "<64-hex>" } ],
  "sql": null,
  "result": null,
  "chart": null,
  "verification": {
    "status": "BLOCKED",
    "summary": "This breakdown is not approved for Average Order Value.",
    "reasons": [
      { "code": "DIMENSION_NOT_ALLOWED", "severity": "error", "message": "'average_order_value' cannot be broken down by 'product_category' (allowed: order_month, region, channel)." }
    ],
    "checks": [
      { "id": "V01", "name": "plan_schema", "status": "PASS", "detail": "Plan parsed." },
      { "id": "V02", "name": "metric_approval", "status": "PASS", "detail": "average_order_value@1.0.0 approved." },
      { "id": "V04", "name": "dimension_filter_policy", "status": "FAIL", "detail": "product_category not allowed." }
    ]
  },
  "clarification": null,
  "timing": { "total_ms": 702.3, "planning_ms": 700.9, "validation_ms": 0.8, "execution_ms": null, "verification_ms": null },
  "planner": { "name": "langchain-meta", "provider": "meta", "model": "muse-spark-1.3", "execution_mode": "LLM", "disclosure": null },
  "audit": { "persisted": true, "url": "/api/audit/0e9a4b52-7c1d-4f3e-8b6a-5d2c1e0f9b77" },
  "error": null
}
```

Write intent (`"Delete all refunds from March…"`) returns `plan: null`, `metrics: []`, with reason `WRITE_INTENT`.

### 6.5 `EXECUTION_FAILED`

```json
{
  "status": "EXECUTION_FAILED",
  "answer": null,
  "result": null,
  "chart": null,
  "sql": { "text": "WITH eligible_orders AS (…", "dialect": "db2", "parameters": [ "…" ], "generated_by": "metricguard-compiler", "sql_hash": "…", "tables": [ "…" ] },
  "verification": {
    "status": "EXECUTION_FAILED",
    "summary": "The governed query could not be executed on IBM Db2.",
    "reasons": [ { "code": "QUERY_TIMEOUT", "severity": "error", "message": "Db2 did not finish within 15 s." } ],
    "checks": [ { "id": "V08", "name": "execution", "status": "FAIL", "detail": "SQLSTATE 57014" }, { "id": "V09", "name": "reconciliation", "status": "SKIPPED", "detail": "Not executed." } ]
  },
  "timing": { "total_ms": 15840.2, "planning_ms": 790.0, "validation_ms": 1.0, "execution_ms": 15040.1, "verification_ms": null },
  "error": { "code": "QUERY_TIMEOUT", "message": "Db2 did not finish within 15 s.", "details": [], "sqlstate": "57014" }
}
```

All other fields have the same shape as in 6.1.

### 6.6 Transport errors

| HTTP | `error.code` | When |
|---|---|---|
| 422 | `INVALID_REQUEST` | Body fails validation (e.g. `question` shorter than 3 characters, unknown field) |
| 501 | `NOT_IMPLEMENTED` | Not used since 1.1.0 (kept in the enum for compatibility) |
| 503 | `PLANNER_UNAVAILABLE` | No planner is available (`PLANNER_MODE=llm` without a key), or the LLM provider failed: rejected credentials, unknown model, rate limit, 5xx, network error or timeout (`PLANNER_TIMEOUT_SECONDS`, default 30 s per attempt, `PLANNER_MAX_RETRIES` 1). Not audited. The service never silently switches to the demo planner. |
| 500 | `INTERNAL_ERROR` | Unexpected server error (body still follows ErrorResponse) |

```json
{
  "request_id": null,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Request validation failed.",
    "details": [ { "field": "question", "issue": "String should have at least 3 characters" } ],
    "sqlstate": null
  }
}
```

### 6.7 Planner execution mode (real LLM vs demo)

| `planner.execution_mode` | `planner.name` | `planner.provider` | `planner.model` | `planner.disclosure` | Meaning |
|---|---|---|---|---|---|
| `LLM` | `langchain-meta` | `meta` | `muse-spark-1.3` (or `META_MODEL`) | `null` | LangChain + Meta Model API produced the typed plan. |
| `LLM` | `langchain-anthropic` | `anthropic` | `claude-sonnet-5-5` (or `PLANNER_MODEL`) | `null` | Optional legacy adapter. Not exercised against the real Anthropic API. |
| `DEMO_RULE_BASED` | `rules-demo` | `metricguard-rules` | `null` | non-empty text | Deterministic keyword rules for the curated examples; **not an LLM**. The UI must show the disclosure whenever this mode is active. |

`provider` is optional for compatibility with 1.1.0 clients; the server always sets it. Both modes use the identical pipeline after planning (validation, registry hash, compiler, guard, read-only execution, verification, audit). Provider selection: `AI_PROVIDER` (`meta`, `anthropic`, `demo`, `auto`); see [`AI_PROVIDER_CONFIGURATION.md`](AI_PROVIDER_CONFIGURATION.md). A failing or unconfigured real provider returns `503 PLANNER_UNAVAILABLE`; it never produces a demo-planner answer.

## 7. `GET /api/audit`

Query parameters:
- `limit`: 1–100, default 20
- `offset`: ≥0, default 0
- `status`: optional ValidationStatus

Results are newest first.

```json
{
  "items": [
    {
      "request_id": "6f1c2a7e-3b8d-4e51-9a0c-2d4b7e9f1a33",
      "created_at": "2026-11-07T20:16:41.208000",
      "question": "Show net revenue and order count by month for EMEA in Q1 2026.",
      "status": "VERIFIED",
      "metric_refs": ["net_revenue@1.0.0", "order_count@1.0.0"],
      "row_count": 3,
      "total_ms": 912,
      "planner": "langchain-meta",
      "execution_mode": "LLM"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

`created_at` is a Db2 `TIMESTAMP` written by the server in UTC and returned without an offset. Treat it as UTC.

## 8. `GET /api/audit/{request_id}`

Returns `200`, `404 AUDIT_NOT_FOUND`, or `422 INVALID_REQUEST` (id is not a UUID).

```json
{
  "request_id": "6f1c2a7e-3b8d-4e51-9a0c-2d4b7e9f1a33",
  "created_at": "2026-11-07T20:16:41.208000",
  "api_version": "1.2.0",
  "question": "Show net revenue and order count by month for EMEA in Q1 2026.",
  "status": "VERIFIED",
  "status_reason": "RECONCILED",
  "planner": "langchain-meta",
  "metric_refs": ["net_revenue@1.0.0", "order_count@1.0.0"],
  "plan": { "metrics": [ { "name": "net_revenue", "version": "1.0.0" }, { "name": "order_count", "version": "1.0.0" } ], "dimensions": ["order_month"], "filters": [ { "field": "region", "operator": "in", "values": ["EMEA"] } ], "date_range": { "start_date": "2026-01-01", "end_date": "2026-03-31", "attribution": "order_date", "source": "explicit" }, "order_by": [], "limit": null },
  "sql": { "text": "WITH eligible_orders AS (…", "parameters": [ { "position": 1, "name": "eligible_status_1", "db2_type": "VARCHAR(16)", "value": "COMPLETED" } ], "sql_hash": "862486670a4b4f555b043d7f545a1e9aebb37426f832c9809084bfa8aff6cba4" },
  "verification": { "status": "VERIFIED", "summary": "…", "reasons": [ "…" ], "checks": [ "…" ] },
  "result_preview": { "columns": [ "…" ], "rows": [ { "order_month": "2026-01", "net_revenue": 25347.46, "order_count": 114 } ], "row_count": 3, "truncated": false },
  "row_count": 3,
  "timing": { "total_ms": 912, "planning_ms": 803, "validation_ms": 1, "execution_ms": 75, "verification_ms": 34 },
  "error": null,
  "execution_mode": "LLM",
  "planner_model": "muse-spark-1.3",
  "metric_definitions": [
    { "ref": "net_revenue@1.0.0", "definition_hash": "471c17a8d0ab04f51b24dee73de00272b26c4d91cb26d1901751c439f5d26232", "db2_hash_match": true }
  ],
  "answer_summary": "Net Revenue for Q1 2026, EMEA totals $79,292.47 across 3 months; the highest is 2026-03 at $31,392.69."
}
```

`execution_mode`, `planner_model` and `answer_summary` are `null` (and `metric_definitions` empty) for rows written before 1.1.0. `db2_hash_match` is `null` when the request never reached the registry check (BLOCKED by policy, AMBIGUOUS). The audit log is append-only: the audit account has no UPDATE or DELETE privilege.

In this section only, `"…"` stands for objects whose shape is identical to §6.1. `result_preview` holds at most the first 20 rows. Audit timing is stored as whole milliseconds.

## 9. UI rendering guide (non-normative)

| Status | Primary display |
|---|---|
| VERIFIED | Answer + chart + "Verified" badge. A "How we know" panel shows the checks, SQL, parameters and metric definitions. |
| EXECUTED_WITH_WARNINGS | Same as VERIFIED, plus a warning banner listing the `warning` reasons. |
| AMBIGUOUS | Clarification prompt with one button per option; clicking one re-submits its `suggested_question`. |
| BLOCKED | The `error` reasons in plain language and the allowed alternatives (from `GET /api/metrics`). No numbers. |
| EXECUTION_FAILED | Error message and SQLSTATE, plus a retry button. SQL is still shown for transparency. |
| any, `planner.execution_mode = DEMO_RULE_BASED` | A persistent, visible "Demo mode — rule-based planner, not AI" label using `planner.disclosure`. |
