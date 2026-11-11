# Detailed Architecture

The concise, hackathon-template version is [`../architecture.md`](../architecture.md). This document covers the internals.

## Code map
```
src/backend/
  app/main.py                FastAPI app, error handlers, CORS, access log, X-Data-Engine header
  app/core/config.py         pydantic-settings (env-only secrets)
  app/core/security.py       Principal from headers, role → permission map
  app/core/risk_config.json  configurable risk weights / thresholds
  app/database/base.py       Database interface (query/execute/transaction), value normalisation
  app/database/db2.py        IBM Db2 implementation (ibm_db_dbi, per-thread connections, retries)
  app/database/devmode.py    DEV MODE engine — same SQL, labelled NOT Db2
  app/database/queries.py    loads named SQL from db/queries/*.sql, expands {{IMPACT_CTES}}
  app/services/traceability.py  impact analysis, data gaps, graph shaping (no Python graph traversal)
  app/services/risk.py       explainable 6-factor score
  app/services/incidents.py  9-state machine, comments
  app/services/recalls.py    generate / approve / reject / execute / actions / complete
  app/services/evidence.py   upload validation, PDF/text parsing, grounded extraction, chunking, embeddings, DB2VS
  app/agents/                schemas, deterministic agents, CrewAI crew, orchestrator
  db/migrations, db/queries, db/seed
src/frontend/src/
  pages/        8 pages (+ incident and recall detail)
  components/   ui primitives (shadcn-style), SupplyGraph (React Flow), DemoPanel
  hooks/        TanStack Query hooks, demo runner
  services/api.ts typed API client with role headers
```

## Why the tracing lives in Db2
Recall scope is a **graph reachability** problem over two kinds of edges:
- transformations (lot or batch → batch)
- shipments (location → location, per batch, time-ordered)

Running this as recursive SQL inside Db2 gives four things:
1. One authoritative answer computed next to the data, using indexes, with no export to Python.
2. Transactional consistency with the incident and recall rows written in the same database.
3. An independent second formulation (reverse traversal) for verification.
4. Auditable SQL that a regulator can read.

Python only shapes the rows. There is deliberately no Python graph walk. The single exception is `lineage_path`, which builds a human-readable path string from the edge rows that Db2 already returned.

## Distribution-flow recursion
The anchor takes legs that leave the producing facility and carry an affected batch. Each recursive step joins `shipments.origin_ref = previous.dest_ref`, `ship_date >= previous.ship_date`, and the **same** batch in `shipment_items`. This models facility → warehouse → (warehouse →) distributor → retailer chains of any length up to 8 hops. `hops` de-duplicates converging paths.

## Concurrency & transactions
- Each request uses its own Db2 connection (thread-local). Writes commit explicitly, and multi-step changes run inside `transaction()`.
- State changes use compare-and-set updates, which prevents concurrent double transitions.
- Investigations run in a background thread and persist after each agent.

## Deployment
- `docker-compose.yml` runs Db2 Community Edition (`icr.io/db2_community/db2`, privileged), the API (waiting for the Db2 healthcheck) and the UI.
- For Db2 on Cloud, set `DB2_HOST`/`DB2_PORT`/`DB2_SECURITY=SSL` and run only the API and UI.
