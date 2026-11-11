-- =====================================================================
-- RecallGuard AI — performance indexes (migration 002)
-- Every index below backs a specific traceability query; see
-- db/queries/*.sql and docs/DATABASE_SCHEMA.md for the mapping.
-- =====================================================================

-- Downstream genealogy: "which batches consumed node X?"  (recursive CTE join)
CREATE INDEX ix_tr_input_ref ON batch_transformations (input_ref, output_batch_id);

-- Upstream genealogy: "what went into batch Y?"
CREATE INDEX ix_tr_output ON batch_transformations (output_batch_id, input_ref);

CREATE INDEX ix_lot_supplier ON ingredient_lots (supplier_id, received_date);
CREATE INDEX ix_lot_ingredient ON ingredient_lots (ingredient_id);

CREATE INDEX ix_batch_product ON production_batches (product_id, production_date);
CREATE INDEX ix_batch_facility ON production_batches (facility_id, production_date);

-- Distribution trace: shipments carrying a batch, then hop by origin_ref
CREATE INDEX ix_si_batch ON shipment_items (batch_id, shipment_id);
CREATE INDEX ix_sh_origin ON shipments (origin_ref, ship_date);
CREATE INDEX ix_sh_dest ON shipments (dest_ref, ship_date);
CREATE INDEX ix_sh_status ON shipments (shipment_status);

CREATE INDEX ix_inc_status ON contamination_incidents (incident_status, discovered_at);
CREATE INDEX ix_inc_source ON contamination_incidents (source_ref);

CREATE INDEX ix_rc_incident ON recall_campaigns (incident_id, recall_status);
CREATE INDEX ix_ri_recall ON recall_affected_items (recall_id, location_ref);
CREATE INDEX ix_ra_recall ON recall_actions (recall_id, action_status);

CREATE INDEX ix_ai_incident ON agent_investigations (incident_id, created_at);
CREATE INDEX ix_audit_entity ON audit_logs (entity_kind, entity_ref, occurred_at);
CREATE INDEX ix_audit_time ON audit_logs (occurred_at);

CREATE INDEX ix_qr_subject ON quality_reports (subject_ref);
CREATE INDEX ix_ed_incident ON evidence_documents (incident_id);
CREATE INDEX ix_ec_doc ON evidence_chunks (document_id, chunk_no)
