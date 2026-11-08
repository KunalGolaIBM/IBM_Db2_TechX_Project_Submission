# Architecture Decisions

Each ADR records a decision, the reason behind it, and its consequences. Status is `Accepted` unless noted.

---

## ADR-001 — The LLM plans; deterministic code executes

**Decision.** The AI layer (Stage 2, LangChain) may only produce a structured `QueryPlan`: metrics, dimensions, filters, date range, sort and limit. It never produces SQL. Validation, SQL generation, execution, verification and audit are deterministic Python.

**Why.** A text-to-SQL answer is only as trustworthy as the SQL. Free-form SQL from a model can join at the wrong grain, ignore status rules or double count refunds, and the result still looks plausible (see the traps in `evidence/DB2_VERIFICATION.md`). Keeping the model's output inside a closed schema means every answer is traceable to approved semantics.

**Consequence.** The model can only answer questions the registry can express. Anything else is returned as `AMBIGUOUS` or `BLOCKED`, which is the intended behavior.

## ADR-002 — Metric registry in code, mirrored and hash-locked in Db2

**Decision.** Metric semantics live in `core/registry.py`, which is version-controlled and reviewed. `db init` writes them to `METRICGUARD.METRIC_DEFINITIONS` together with a SHA-256 of the canonical JSON. A result is `VERIFIED` only if the runtime definition hash equals the approved row in Db2.

**Why.** It keeps one source of truth with review history, and makes semantic drift between the app and the governed database detectable. The database record also shows judges and auditors what was approved.

**Consequence.** Changing a definition requires a version bump and a re-registration. A mismatch blocks verified answers (`REGISTRY_DRIFT`).

## ADR-003 — No executable SQL in metric metadata

**Decision.** `METRIC_DEFINITIONS` stores only declarative fields: meaning, calculation prose, eligible statuses, attribution, null, refund and discount rules, allowed dimensions and filters. SQL fragments are constants in `compiler.py`, keyed by three base measures (`line_revenue_sum`, `processed_refund_sum`, `distinct_order_count`).

**Why.** Metadata tables are often writable by more people than code. Storing SQL there would turn a governance table into a code-injection surface.

## ADR-004 — Line-grain facts with per-line refund pre-aggregation

**Decision.** The compiler always builds three CTEs:
- `eligible_orders`: status, date and order-level filters
- `line_refunds`: processed refunds aggregated per `ORDER_ITEM_ID`, restricted to eligible orders
- `line_facts`: lines of eligible orders, joined 1:1 to `line_refunds`

The final aggregation is a single `GROUP BY`.

**Why.** It prevents refund × item fan-out, keeps refunds attributable to product category, and makes every additive metric reconcile (the sum of groups equals the total).

**Consequence.** Order-grain metrics (`order_count`, `average_order_value`) cannot be split by line-grain dimensions. The registry forbids that combination.

## ADR-005 — Values only as parameter markers

**Decision.** Every value in compiled SQL is a `CAST(? AS <type>)` parameter, including statuses and date bounds. Identifiers come from whitelists, and `FETCH FIRST n` uses a validated integer. A static SQL guard (`core/sql_guard.py`) re-checks every statement before it reaches Db2:
- single statement
- `SELECT` / `WITH` only
- no DDL, DML or `CALL`
- no system catalogs
- tables on an allow-list

**Why.** Defense in depth. The guard is also the gate for any future model-proposed SQL.

## ADR-006 — Least-privilege analytical connection

**Decision.** Analytical queries run as `MGREADER`, which has only `CONNECT` plus `SELECT` on the five analytical tables. Schema changes, seeding and audit writes use the instance owner. `db verify` proves that Db2 rejects a `DELETE` attempted as the reader.

**Why.** Even if every software layer failed, the database itself refuses writes from the analytics path.

## ADR-007 — Cohort (order-date) refund attribution

**Decision.** Refunds are attributed to the order date of the refunded order.

**Why.** Refund rate needs its numerator and denominator from the same orders. Cash-basis refunds against current-month revenue can exceed 100% and mislead.

**Trade-off.** Past months' net revenue can change as late refunds arrive. This is documented in `METRIC_SEMANTICS.md`. A cash-basis "refunds processed" metric can be added later as a separate, versioned metric.

## ADR-008 — Inclusive dates executed as a half-open interval

**Decision.** The API speaks inclusive calendar dates. SQL uses `>= start AND < end + 1 day`.

**Why.** `BETWEEN '2026-01-01' AND '2026-01-31'` silently drops everything after `2026-01-31 00:00:00`. The dataset contains canary orders at exactly those boundaries (TRAP-04 measures the loss).

## ADR-009 — Independent oracle for expected results

**Decision.** Expected answers are computed by `seed/oracle.py`, which uses plain Python loops over the generated objects, shares no code with the compiler, and uses `Decimal` with half-up rounding. Verification requires exact equality with Db2.

**Why.** Agreement between two independent implementations is evidence that the SQL implements the documented semantics, not just that it runs.

## ADR-010 — `VERIFIED` is earned, not assumed

**Decision.** `VERIFIED` requires all of the following:
- an approved plan with current metric versions
- registry hashes matching Db2
- SQL compiled deterministically and passing the guard
- successful execution
- reconciliation of additive metrics against a separate control-total query
- results that are not truncated and fall within data coverage

`EXECUTED_WITH_WARNINGS` means the numbers are correct for the plan, but something limits how they should be read. See `API_CONTRACT.md` §2.

## ADR-011 — Local IBM Db2 Community Edition 12.1 on Apple Silicon via Colima + QEMU

**Decision.** Run the official `icr.io/db2_community/db2` image (Db2 12.1.5.0, linux/amd64) in a Colima `vz` VM. The VM uses QEMU user-mode binfmt for amd64, and **Rosetta is disabled**.

**Why.**
- IBM publishes the image for x86_64 / ppc64le / s390x Linux only. There is no arm64 Db2 server, so Apple Silicon needs emulation.
- With Rosetta, the image's entrypoint runs `su - db2inst1 -c …`, but Rosetta's binfmt registration (flags `OCF`) lacks the preserve-argv0 flag. The login shell therefore never sources `db2profile`, and `db2start` and `CREATE DATABASE` fail with "command not found" while the entrypoint still prints "Setup has completed". This was observed in this project, and the same Rosetta conflict is reported in IBM community threads.
- QEMU's registration has `POCF` (P = preserve argv0) and works.

**Consequence.** Db2 runs under emulation, so it is slower than on native x86 but adequate for a 3k-order dataset. IBM Cloud Db2 is the supported non-emulated alternative: set `DB2_SECURITY=true` and the certificate in `.env`.

## ADR-012 — Native arm64 client driver

**Decision.** Use the `ibm_db` 3.3.0 wheel (macOS arm64, bundled clidriver v12.x) natively on the host. Only the server is emulated.

## ADR-013 — Repository layout vs. official submission layout

**Decision.** Development happens in this standalone repo (`metricguard-db2/`). The official submission is a PR to `KunalGolaIBM/IBM_Db2_TechX_Project_Submission` that adds `submissions/metricguard/`, containing `README.md`, `architecture.md`, `submission.json`, `.env.example`, `src/`, `tests/` and `docs/screenshots/`. Packaging is a later stage. The mapping is in `docs/HACKATHON_REQUIREMENTS.md`.

**Why.** The official repo validator forbids any file named `.env` and checks the folder structure. It also forbids touching anything outside the submission folder, which an active dev workflow would violate.

---

## ADR-014 — Structured planner via Claude's json_schema output, behind deterministic screens

**Decision.** The LLM planner is LangChain `ChatAnthropic(model="claude-sonnet-5-5").with_structured_output(PlannerOutput, method="json_schema", include_raw=True)`. `PlannerOutput` is a closed Pydantic model (intent, metric names, dimensions, filters, inclusive dates, sort, limit, ambiguity fields); it has no SQL field and `extra="forbid"`. Metric versions are pinned from the registry by code, never by the model. Before and independently of the planner, `planner/policy.py` screens the question for write/DDL language, raw SQL or catalog names, relative periods and a bare "revenue"/"sales". These screens can only make an outcome stricter.

**Why.**
- Claude Sonnet 5.5 rejects forced `tool_choice`, so function-calling structured output is not guaranteed; the json_schema method is the supported path. No `temperature` is sent (Sonnet 5.5 rejects non-default sampling). Effort defaults to `low` (`PLANNER_EFFORT`) because planning is extraction, not reasoning-heavy.
- Governance must not depend on the model noticing a destructive or ambiguous request. Deterministic screens make `WRITE_INTENT`, `OUT_OF_SCOPE`, `AMBIGUOUS_*` reproducible, while the model handles paraphrase.
- Unknown metrics or dimensions the model echoes are passed through as names, so the deterministic validator blocks them (`UNKNOWN_METRIC`, `UNKNOWN_DIMENSION`) instead of the model silently substituting an approved one.

**Failure mapping.** Malformed, truncated, refused or schema-violating output → `BLOCKED` + `PLAN_SCHEMA_INVALID` (V01 FAIL), audited. Provider failures (401/403, 404 model, 429, 5xx, network, timeout) → HTTP `503 PLANNER_UNAVAILABLE`, not audited and never silently replaced by the demo planner.

## ADR-015 — Labelled DEMO_RULE_BASED planner

**Decision.** `planner/rules.py` is a deterministic keyword planner for the curated questions. Every response says `planner.execution_mode = "DEMO_RULE_BASED"`, `planner.model = null`, and carries `planner.disclosure`; the audit row stores the same mode. It is used only when `PLANNER_MODE=demo`, or `auto` without an API key.

**Why.** The demo must run without credentials, but a rules engine must never be passed off as AI. Both planners feed the same validation, compiler, guard, execution, verification and audit code, so the demo still proves the governed path. The rule planner was written alongside the benchmark cases, so its benchmark score is not evidence of generalization (stated in `evaluation/benchmark-results.md`).

## ADR-016 — Append-only, least-privilege audit account

**Decision.** A third Db2 principal, `MGAUDIT` (`DB2_AUDIT_USER`), holds only `CONNECT` and `INSERT, SELECT` on `METRICGUARD.QUERY_AUDIT_LOG`. The API writes audit rows and serves `GET /api/audit*` through it. `MGREADER` stays `SELECT`-only on the five analytical tables and has no access to the audit log. Writes are parameterized. Stage 2 columns (`EXECUTION_MODE`, `PLANNER_MODEL`, `METRIC_DEFS_JSON`, `ANSWER_SUMMARY`) are added by an idempotent `ALTER TABLE … ADD COLUMN` migration (`metricguard db migrate`), so existing data is never dropped.

**Why.** Granting the reader write access for logging would undo ADR-006. Without `UPDATE`/`DELETE`, even a compromised API process cannot rewrite history. Db2 itself enforces both properties (`SQLSTATE 42501`), and `make db-verify` plus `test_analyze_db2.py` prove it on every run.

**Consequence.** An audit-write failure does not hide a valid answer: the response carries `audit.persisted = false`. Rows are stored without credentials or raw driver/provider messages (error code + generic message only).
