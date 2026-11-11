# Database Schema & Queries (IBM Db2)

## Migrations
| File | Purpose |
|---|---|
| `001_core_schema.sql` | 23 tables with PK/FK/UNIQUE/CHECK constraints |
| `002_indexes.sql` | 21 indexes, each backing a named query |
| `003_views.sql` | `V_LOCATIONS`: a single directory of facilities, warehouses, distributors and retailers |

The runner (`app/database/__init__.py`) records applied files in `SCHEMA_MIGRATIONS` and applies each file inside one transaction. Db2 DDL is transactional.

## Tables
| Domain | Table | Key / notable constraints |
|---|---|---|
| Master data | `SUPPLIERS` | PK `supplier_id`; `UNIQUE(supplier_name)`; `risk_tier` CHECK |
| | `INGREDIENTS` | `allergen_flag` CHECK 0/1 |
| | `MANUFACTURING_FACILITIES` | |
| | `FINISHED_PRODUCTS` | SKU PK, GTIN |
| | `WAREHOUSES`, `DISTRIBUTORS`, `RETAILERS` | `temperature_class` / `retailer_type` CHECKs |
| Traceability | `INGREDIENT_LOTS` | FKs to ingredient, supplier, facility; `quantity_kg > 0`; `lot_status` CHECK |
| | `PRODUCTION_BATCHES` | `FINISHED ⇔ product_id NOT NULL` CHECK; status CHECK |
| | `BATCH_TRANSFORMATIONS` | **Genealogy edges.** Polymorphic input with an FK per target + exactly-one CHECK; `UNIQUE(input_ref, output_batch_id)`; no self-loop; `record_status` VERIFIED/UNVERIFIED/DISPUTED |
| | `SHIPMENTS` | Polymorphic origin (facility, warehouse or distributor) and destination (warehouse, distributor or retailer) with exactly-one CHECKs (null-safe); `delivered_date >= ship_date` |
| | `SHIPMENT_ITEMS` | PK `(shipment_id, batch_id)`; FK to batch → no orphan items |
| | `QUALITY_REPORTS` | COA / process QC / lab outcomes PASS, FAIL, INCONCLUSIVE |
| Incidents | `CONTAMINATION_INCIDENTS` | 9-state `incident_status` CHECK; category & severity CHECKs; `is_demo` |
| | `INCIDENT_AFFECTED_LOTS` | Db2-derived impact snapshot per incident (SOURCE/DIRECT/INDIRECT, depth) |
| | `INCIDENT_COMMENTS` | review notes |
| Recall | `RECALL_CAMPAIGNS` | class, status, score 0–100 CHECK, plan / verification / risk JSON in CLOB |
| | `RECALL_AFFECTED_ITEMS` | `UNIQUE(recall_id, batch_id, location_ref)`; priority, basis, reason, evidence refs |
| | `RECALL_ACTIONS` | `UNIQUE(recall_id, location_ref, action_type)`; channel defaults to `SIMULATED` |
| AI & audit | `AGENT_INVESTIGATIONS` | PK `(run_id, agent_name)`; `execution_mode` CREWAI_LLM / DETERMINISTIC_FALLBACK; output JSON + log CLOB |
| | `AUDIT_LOGS` | append-only; microsecond timestamps |
| Evidence | `EVIDENCE_DOCUMENTS` | `UNIQUE(sha256)`; verification status; extracted claims JSON |
| | `EVIDENCE_CHUNKS` | page, section, text, portable JSON vector (native `VECTOR` via langchain-db2 `RG_EVIDENCE_VECTORS`) |

## Named queries (`db/queries/traceability.sql`)
| Query | Type | Purpose | Index used |
|---|---|---|---|
| `IMPACT_CTES` (fragment) | recursive ×2 | `seeds` → `genealogy` (recursive over transformations) → `affected_batches` → `flow` (recursive over shipments, same batch, date-ordered) → `hops` | `ix_tr_input_ref`, `ix_si_batch`, `ix_sh_origin` |
| `downstream_genealogy` | recursive | Edges below a lot or batch (graph view) | `ix_tr_input_ref` |
| `upstream_genealogy` | recursive | Ancestors of a batch, up to lots and suppliers | `ix_tr_output` |
| `impact_batches` | recursive | Affected batches with minimum depth → direct vs indirect | |
| `impact_hops` | recursive | Every shipment leg that carried an affected batch | |
| `impact_location_balance` | recursive + aggregate | Units received / forwarded / held / in transit per batch per location, plus facility stock | `ix_sh_dest` |
| `impact_unverified_edges` | recursive | Non-VERIFIED transformation records on the contamination path | |
| `impact_intermediate_balance` | recursive + aggregate | Intermediate quantity produced vs recorded consumption | |
| `lot_consumption` | aggregate | Source-lot quantity not linked to any batch | |
| `verify_finished_descendants` | recursive (reverse) | Upstream walk from every finished batch; must equal the forward trace | `ix_tr_output` |
| `verify_batch_lineage` | recursive | Does batch X descend from source S? | `ix_tr_output` |
| `verify_direct_recipients` | join | Every recipient of a batch, independent of hop order | `ix_si_batch` |

### Db2-specific rules followed
- No `RECURSIVE` keyword: a self-referencing CTE is recursive in Db2.
- Every column of a recursive CTE is `CAST` in both the initialisation and recursive fullselects, so types and lengths match (avoids SQL0344N/SQL0373N).
- Each recursive leg has an explicit depth bound (`< 12` / `< 8`). This guarantees termination and suppresses SQL0347W.
- Pagination uses `FETCH FIRST n ROWS ONLY`.
- All values pass through `?` parameter markers.

A static test (`tests/test_db2_driver.py::test_traceability_sql_is_db2_compatible_by_construction`) enforces these rules.

## Seed design (`db/seed/generate_seed.py`, deterministic)
- **Scenario 1 — TOM-2026-041 (live demo).** 2,400 kg from SUP-001 enters PB-1001 (tomato base) and PB-1002 (pasta sauce).
  - PB-1001 feeds marinara (1004), pizza sauce (1005, and 1006 via an **UNVERIFIED** manual log), soup (1008), and the masala gravy base PB-1003.
  - PB-1003 feeds paneer tikka masala (1007) and dal tadka (1009).
  - Distribution reaches 6 warehouses, 4 distributors and 19 retailers. Kolkata is reached through a warehouse-to-warehouse hop.
  - Deliberate gaps: DST-05 dead-end, an in-transit leg, 150 kg of gravy base unaccounted, 100 kg of the lot unlinked.
- **Near-misses:** TOM-2026-042 / TOM-2026-038 make the *same SKUs*, and they reach some of the *same retailers*. None of them may appear in scope.
- **Scenario 2 — CHI-2026-017** (historical, completed recall). **Scenario 3 — MLK-2026-233** (presumptive, pending approval).
- **Background batches** follow fixed routing rules (no randomness), so the tests can assert exact sets.
