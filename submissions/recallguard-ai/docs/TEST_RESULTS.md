# Test Results (executed)

**Environment:** Linux build sandbox, Python 3.13.18, Node 22. Date of run: 2026-11-11.
**Data engine:** backend tests run in `DB_MODE=dev`, i.e. the labelled embedded engine executing the *same* Db2 migration and query files. A live IBM Db2 server was **not** available: the sandbox network policy blocked `icr.io` and Docker Hub image pulls. The `ibm_db` driver itself is installed and exercised (connection-string and failure-handling tests). `test_live_db2_round_trip` is skipped until you set `RG_TEST_DB2=1` and the `DB2_*` variables.

## Backend — `cd src/backend && pytest -v`
```
tests/test_agents.py::test_outputs_are_valid_structured_models PASSED    [  1%]
tests/test_agents.py::test_investigation_is_grounded_in_uploaded_report PASSED [  3%]
tests/test_agents.py::test_supply_chain_agent_uses_db2_results PASSED    [  5%]
tests/test_agents.py::test_plan_is_targeted_and_excludes_same_sku_batches PASSED [  6%]
tests/test_agents.py::test_verification_passes_db2_checks_with_warnings PASSED [  8%]
tests/test_agents.py::test_verification_detects_injected_unrelated_item PASSED [ 10%]
tests/test_agents.py::test_verification_detects_dropped_batch PASSED     [ 11%]
tests/test_agents.py::test_verification_flags_invented_identifier PASSED [ 13%]
tests/test_agents.py::test_crewai_crew_builds_with_db2_tools PASSED      [ 15%]
tests/test_agents.py::test_crewai_kickoff_produces_validated_narrative PASSED [ 16%]
tests/test_agents.py::test_orchestrator_llm_mode_merges_narrative_but_keeps_db2_facts PASSED [ 18%]
tests/test_api.py::test_health_labels_engine PASSED                      [ 20%]
tests/test_api.py::test_dashboard_summary PASSED                         [ 22%]
tests/test_api.py::test_incident_validation_and_errors PASSED            [ 23%]
tests/test_api.py::test_rbac PASSED                                      [ 25%]
tests/test_api.py::test_supplier_contacts_redacted_for_viewer PASSED     [ 27%]
tests/test_api.py::test_trace_and_impact_endpoints PASSED                [ 28%]
tests/test_api.py::test_upload_validation PASSED                         [ 30%]
tests/test_api.py::test_full_human_in_the_loop_workflow PASSED           [ 32%]
tests/test_api.py::test_reject_and_reinvestigate PASSED                  [ 33%]
tests/test_api.py::test_evidence_search_returns_citations PASSED         [ 35%]
tests/test_api.py::test_demo_endpoint_and_reset PASSED                   [ 37%]
tests/test_database.py::test_connection_status_is_honestly_labelled PASSED [ 38%]
tests/test_database.py::test_all_tables_and_migrations_exist PASSED      [ 40%]
tests/test_database.py::test_seed_volume_requirements[suppliers-10] PASSED [ 42%]
tests/test_database.py::test_seed_volume_requirements[ingredient_lots-20] PASSED [ 44%]
tests/test_database.py::test_seed_volume_requirements[production_batches-30] PASSED [ 45%]
tests/test_database.py::test_seed_volume_requirements[finished_products-15] PASSED [ 47%]
tests/test_database.py::test_seed_volume_requirements[warehouses-8] PASSED [ 49%]
tests/test_database.py::test_seed_volume_requirements[retailers-20] PASSED [ 50%]
tests/test_database.py::test_seed_volume_requirements[shipments-50] PASSED [ 52%]
tests/test_database.py::test_seed_has_no_orphans PASSED                  [ 54%]
tests/test_database.py::test_duplicate_genealogy_edge_rejected PASSED    [ 55%]
tests/test_database.py::test_self_loop_and_inconsistent_input_rejected PASSED [ 57%]
tests/test_database.py::test_orphan_shipment_item_rejected PASSED        [ 59%]
tests/test_database.py::test_shipment_polymorphic_check PASSED           [ 61%]
tests/test_database.py::test_parameterised_queries_are_injection_safe PASSED [ 62%]
tests/test_db2_driver.py::test_ibm_db_driver_is_installed PASSED         [ 64%]
tests/test_db2_driver.py::test_connection_string_built_from_env_settings PASSED [ 66%]
tests/test_db2_driver.py::test_unreachable_db2_fails_gracefully_with_database_error PASSED [ 67%]
tests/test_db2_driver.py::test_traceability_sql_is_db2_compatible_by_construction PASSED [ 69%]
tests/test_db2_driver.py::test_live_db2_round_trip SKIPPED (live IBM...) [ 71%]
tests/test_genealogy.py::test_tom_2026_041_full_downstream_impact PASSED [ 72%]
tests/test_genealogy.py::test_direct_vs_indirect_classification PASSED   [ 74%]
tests/test_genealogy.py::test_near_miss_batches_never_included PASSED    [ 76%]
tests/test_genealogy.py::test_unrelated_batch_has_no_tomato_products PASSED [ 77%]
tests/test_genealogy.py::test_data_gaps_are_flagged_conservatively PASSED [ 79%]
tests/test_genealogy.py::test_units_conserved_per_batch PASSED           [ 81%]
tests/test_genealogy.py::test_upstream_trace_reaches_contaminated_lot_and_supplier PASSED [ 83%]
tests/test_genealogy.py::test_reverse_query_matches_forward_trace PASSED [ 84%]
tests/test_genealogy.py::test_lineage_path PASSED                        [ 86%]
tests/test_genealogy.py::test_trace_graph_highlights_affected_nodes PASSED [ 88%]
tests/test_risk.py::test_weights_sum_to_100 PASSED                       [ 89%]
tests/test_risk.py::test_score_bounds_and_explainability PASSED          [ 91%]
tests/test_risk.py::test_severity_is_monotonic PASSED                    [ 93%]
tests/test_risk.py::test_missing_records_increase_risk_and_reduce_confidence PASSED [ 94%]
tests/test_risk.py::test_unconfirmed_evidence_is_conservative PASSED     [ 96%]
tests/test_risk.py::test_time_since_discovery_raises_score PASSED        [ 98%]
tests/test_risk.py::test_classification_thresholds PASSED                [100%]
======================== 58 passed, 1 skipped in 21.58s ========================
```

### Critical acceptance tests
- `test_genealogy.py::test_tom_2026_041_full_downstream_impact` checks that TOM-2026-041 yields exactly:
  - 9 batches (7 finished)
  - 6 products (P-PSC, P-MAR, P-PZS, P-PTM, P-TSP, P-DAL)
  - 6 warehouses, 4 distributors, 19 retailers
  - supplier SUP-001, maximum depth 3
- `test_unrelated_batch_has_no_tomato_products` checks that PB-2026-1030 (biscuits) returns only itself and no tomato products or retailers.
- `test_near_miss_batches_never_included` checks that the same-SKU batches made from TOM-2026-042 / TOM-2026-038 are excluded.

## Frontend — `cd src/frontend && npm test`
```
 ✓ src/test/app.test.tsx (9 tests)
   Executive dashboard  › renders KPIs, risk distribution and incidents
   Executive dashboard  › shows a loading state, then an error state with retry
   Incident creation    › creates an incident, uploads the lab report and starts the investigation
   Incident creation    › shows server validation errors
   Batch tracing        › renders the Db2 genealogy graph and executed queries
   Batch tracing        › shows an error when the batch does not exist
   Recall approval      › lets a recall manager approve
   Recall approval      › requires a comment to reject and blocks analysts
   Recall approval      › renders nothing once decided
 Test Files  1 passed (1)
      Tests  9 passed (9)
```
(The Recharts "width(0)" messages are expected in jsdom, which has no layout engine.)

Also run: `npx tsc -b --noEmit` (no errors) and `vite build` (succeeds).

## End-to-end browser run (Playwright, headless Chromium, real UI + real API)
1. Dashboard → **Run Tomato Contamination Demo**. The panel showed:
   - `INC-… · CRITICAL · supplier Valle Rosso Tomato Cooperative`
   - `DOC-… · 17 claims · 3 positive result(s) · lots TOM-2026-041`
   - `Risk 84/100 CRITICAL · verification PASS_WITH_WARNINGS · deterministic fallback (no LLM)`
   - `RC-… · CLASS I · 40 items · 42,000 units · 6 same-SKU batches excluded`
2. Switched role to Recall Manager → Approve. The recall and the incident both became `EXECUTING`, with 31 simulated notifications.
3. Simulate partner responses: 18/31 acknowledged, 14,850 / 42,000 units recovered (35.4%).
4. Every page rendered with no JavaScript errors. The only console errors were Google Fonts requests, blocked by the sandbox network. At 390 px width, `scrollWidth` was 390 (no horizontal scroll) on all 7 main pages.

The screenshots in `docs/screenshots/` come from this run, in DEV MODE.

## Not tested here
- Live IBM Db2 execution of the migrations and recursive SQL (run `RG_TEST_DB2=1 pytest`).
- langchain-db2 `DB2VS` against Db2 12.1.2 `VECTOR`.
- Hosted LLM calls through CrewAI (tested only with a local stub `BaseLLM`).
- The Python 3.11 image used by `Dockerfile` (tests ran on 3.13).
