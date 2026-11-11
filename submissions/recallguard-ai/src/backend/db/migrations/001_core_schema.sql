-- =====================================================================
-- RecallGuard AI — IBM Db2 core schema (migration 001)
-- Target: IBM Db2 11.5+ / 12.1 (LUW). Statements are separated by ';'.
--
-- Design notes
--  * Business identifiers (lot IDs, batch IDs, SKUs) are the primary keys,
--    because they are what labs, suppliers and regulators actually quote.
--  * Polymorphic relationships (a transformation input may be an ingredient
--    lot OR an intermediate batch; a shipment may originate from a facility,
--    warehouse or distributor) are modelled with one nullable FK column per
--    target table plus a NOT NULL "*_ref" column and CHECK constraints that
--    force exactly one FK to be populated and equal to the ref. This keeps
--    full referential integrity while giving the recursive CTEs a single
--    join column.
--  * All PK / UNIQUE columns are NOT NULL (required by Db2).
-- =====================================================================

CREATE TABLE suppliers (
    supplier_id        VARCHAR(20)  NOT NULL,
    supplier_name      VARCHAR(120) NOT NULL,
    country            VARCHAR(60)  NOT NULL,
    region             VARCHAR(60),
    contact_email      VARCHAR(120),
    contact_phone      VARCHAR(40),
    certification      VARCHAR(80),
    risk_tier          VARCHAR(10)  NOT NULL DEFAULT 'STANDARD',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_suppliers PRIMARY KEY (supplier_id),
    CONSTRAINT uq_supplier_name UNIQUE (supplier_name),
    CONSTRAINT ck_supplier_tier CHECK (risk_tier IN ('LOW','STANDARD','ELEVATED'))
);

CREATE TABLE ingredients (
    ingredient_id      VARCHAR(20)  NOT NULL,
    ingredient_name    VARCHAR(120) NOT NULL,
    category           VARCHAR(60)  NOT NULL,
    allergen_flag      SMALLINT     NOT NULL DEFAULT 0,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ingredients PRIMARY KEY (ingredient_id),
    CONSTRAINT ck_ing_allergen CHECK (allergen_flag IN (0,1))
);

CREATE TABLE manufacturing_facilities (
    facility_id        VARCHAR(20)  NOT NULL,
    facility_name      VARCHAR(120) NOT NULL,
    city               VARCHAR(60)  NOT NULL,
    state_region       VARCHAR(60),
    license_no         VARCHAR(40),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_facilities PRIMARY KEY (facility_id)
);

CREATE TABLE ingredient_lots (
    lot_id             VARCHAR(30)  NOT NULL,
    ingredient_id      VARCHAR(20)  NOT NULL,
    supplier_id        VARCHAR(20)  NOT NULL,
    facility_id        VARCHAR(20)  NOT NULL,
    quantity_kg        DECIMAL(12,2) NOT NULL,
    received_date      DATE         NOT NULL,
    expiry_date        DATE,
    coa_reference      VARCHAR(60),
    lot_status         VARCHAR(20)  NOT NULL DEFAULT 'RELEASED',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ingredient_lots PRIMARY KEY (lot_id),
    CONSTRAINT fk_lot_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients (ingredient_id),
    CONSTRAINT fk_lot_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id),
    CONSTRAINT fk_lot_facility FOREIGN KEY (facility_id) REFERENCES manufacturing_facilities (facility_id),
    CONSTRAINT ck_lot_qty CHECK (quantity_kg > 0),
    CONSTRAINT ck_lot_status CHECK (lot_status IN ('RELEASED','ON_HOLD','QUARANTINED','CONSUMED','DESTROYED'))
);

CREATE TABLE finished_products (
    product_id         VARCHAR(20)  NOT NULL,
    product_name       VARCHAR(120) NOT NULL,
    brand              VARCHAR(60)  NOT NULL,
    category           VARCHAR(60)  NOT NULL,
    unit_size          VARCHAR(30)  NOT NULL,
    gtin               VARCHAR(20),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_finished_products PRIMARY KEY (product_id)
);

CREATE TABLE production_batches (
    batch_id           VARCHAR(30)  NOT NULL,
    facility_id        VARCHAR(20)  NOT NULL,
    batch_type         VARCHAR(12)  NOT NULL,
    product_id         VARCHAR(20),
    description        VARCHAR(160) NOT NULL,
    quantity           DECIMAL(12,2) NOT NULL,
    quantity_unit      VARCHAR(10)  NOT NULL,
    production_date    DATE         NOT NULL,
    best_before        DATE,
    batch_status       VARCHAR(20)  NOT NULL DEFAULT 'RELEASED',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_production_batches PRIMARY KEY (batch_id),
    CONSTRAINT fk_batch_facility FOREIGN KEY (facility_id) REFERENCES manufacturing_facilities (facility_id),
    CONSTRAINT fk_batch_product FOREIGN KEY (product_id) REFERENCES finished_products (product_id),
    CONSTRAINT ck_batch_type CHECK (batch_type IN ('INTERMEDIATE','FINISHED')),
    -- finished batches must name a product, intermediates must not
    CONSTRAINT ck_batch_product CHECK ((batch_type = 'FINISHED' AND product_id IS NOT NULL)
                                    OR (batch_type = 'INTERMEDIATE' AND product_id IS NULL)),
    CONSTRAINT ck_batch_qty CHECK (quantity > 0),
    CONSTRAINT ck_batch_unit CHECK (quantity_unit IN ('KG','UNITS')),
    CONSTRAINT ck_batch_status CHECK (batch_status IN ('RELEASED','ON_HOLD','QUARANTINED','RECALLED','DESTROYED'))
);

-- Genealogy edges: (ingredient lot | intermediate batch) -> output batch
CREATE TABLE batch_transformations (
    transformation_id  VARCHAR(30)  NOT NULL,
    input_kind         VARCHAR(5)   NOT NULL,
    input_ref          VARCHAR(30)  NOT NULL,
    input_lot_id       VARCHAR(30),
    input_batch_id     VARCHAR(30),
    output_batch_id    VARCHAR(30)  NOT NULL,
    quantity_used      DECIMAL(12,2) NOT NULL,
    quantity_unit      VARCHAR(10)  NOT NULL,
    process_step       VARCHAR(80)  NOT NULL,
    transformed_at     TIMESTAMP    NOT NULL,
    record_status      VARCHAR(12)  NOT NULL DEFAULT 'VERIFIED',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_batch_transformations PRIMARY KEY (transformation_id),
    CONSTRAINT fk_tr_input_lot FOREIGN KEY (input_lot_id) REFERENCES ingredient_lots (lot_id),
    CONSTRAINT fk_tr_input_batch FOREIGN KEY (input_batch_id) REFERENCES production_batches (batch_id),
    CONSTRAINT fk_tr_output_batch FOREIGN KEY (output_batch_id) REFERENCES production_batches (batch_id),
    -- exactly one input FK populated, and input_ref mirrors it
    CONSTRAINT ck_tr_input CHECK (
        (input_kind = 'LOT'   AND input_lot_id IS NOT NULL AND input_batch_id IS NULL AND input_ref = input_lot_id)
     OR (input_kind = 'BATCH' AND input_batch_id IS NOT NULL AND input_lot_id IS NULL AND input_ref = input_batch_id)),
    CONSTRAINT ck_tr_no_self_loop CHECK (input_ref <> output_batch_id),
    CONSTRAINT ck_tr_qty CHECK (quantity_used > 0),
    CONSTRAINT ck_tr_record CHECK (record_status IN ('VERIFIED','UNVERIFIED','DISPUTED')),
    -- no duplicate genealogy edges
    CONSTRAINT uq_tr_edge UNIQUE (input_ref, output_batch_id)
);

CREATE TABLE warehouses (
    warehouse_id       VARCHAR(20)  NOT NULL,
    warehouse_name     VARCHAR(120) NOT NULL,
    city               VARCHAR(60)  NOT NULL,
    state_region       VARCHAR(60),
    temperature_class  VARCHAR(12)  NOT NULL DEFAULT 'AMBIENT',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_warehouses PRIMARY KEY (warehouse_id),
    CONSTRAINT ck_wh_temp CHECK (temperature_class IN ('AMBIENT','CHILLED','FROZEN'))
);

CREATE TABLE distributors (
    distributor_id     VARCHAR(20)  NOT NULL,
    distributor_name   VARCHAR(120) NOT NULL,
    city               VARCHAR(60)  NOT NULL,
    contact_email      VARCHAR(120),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_distributors PRIMARY KEY (distributor_id)
);

CREATE TABLE retailers (
    retailer_id        VARCHAR(20)  NOT NULL,
    retailer_name      VARCHAR(120) NOT NULL,
    retailer_type      VARCHAR(20)  NOT NULL,
    city               VARCHAR(60)  NOT NULL,
    state_region       VARCHAR(60),
    contact_email      VARCHAR(120),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_retailers PRIMARY KEY (retailer_id),
    CONSTRAINT ck_rt_type CHECK (retailer_type IN ('SUPERMARKET','CONVENIENCE','ONLINE','FOODSERVICE','HYPERMARKET'))
);

CREATE TABLE shipments (
    shipment_id        VARCHAR(30)  NOT NULL,
    origin_kind        VARCHAR(12)  NOT NULL,
    origin_ref         VARCHAR(20)  NOT NULL,
    origin_facility_id VARCHAR(20),
    origin_warehouse_id VARCHAR(20),
    origin_distributor_id VARCHAR(20),
    dest_kind          VARCHAR(12)  NOT NULL,
    dest_ref           VARCHAR(20)  NOT NULL,
    dest_warehouse_id  VARCHAR(20),
    dest_distributor_id VARCHAR(20),
    dest_retailer_id   VARCHAR(20),
    ship_date          DATE         NOT NULL,
    delivered_date     DATE,
    shipment_status    VARCHAR(12)  NOT NULL,
    carrier            VARCHAR(80),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_shipments PRIMARY KEY (shipment_id),
    CONSTRAINT fk_sh_o_fac FOREIGN KEY (origin_facility_id) REFERENCES manufacturing_facilities (facility_id),
    CONSTRAINT fk_sh_o_wh FOREIGN KEY (origin_warehouse_id) REFERENCES warehouses (warehouse_id),
    CONSTRAINT fk_sh_o_dst FOREIGN KEY (origin_distributor_id) REFERENCES distributors (distributor_id),
    CONSTRAINT fk_sh_d_wh FOREIGN KEY (dest_warehouse_id) REFERENCES warehouses (warehouse_id),
    CONSTRAINT fk_sh_d_dst FOREIGN KEY (dest_distributor_id) REFERENCES distributors (distributor_id),
    CONSTRAINT fk_sh_d_rt FOREIGN KEY (dest_retailer_id) REFERENCES retailers (retailer_id),
    CONSTRAINT ck_sh_origin CHECK (
        (origin_kind = 'FACILITY'    AND origin_facility_id IS NOT NULL AND origin_facility_id = origin_ref AND origin_warehouse_id IS NULL AND origin_distributor_id IS NULL)
     OR (origin_kind = 'WAREHOUSE'   AND origin_warehouse_id IS NOT NULL AND origin_warehouse_id = origin_ref AND origin_facility_id IS NULL AND origin_distributor_id IS NULL)
     OR (origin_kind = 'DISTRIBUTOR' AND origin_distributor_id IS NOT NULL AND origin_distributor_id = origin_ref AND origin_facility_id IS NULL AND origin_warehouse_id IS NULL)),
    CONSTRAINT ck_sh_dest CHECK (
        (dest_kind = 'WAREHOUSE'   AND dest_warehouse_id IS NOT NULL AND dest_warehouse_id = dest_ref AND dest_distributor_id IS NULL AND dest_retailer_id IS NULL)
     OR (dest_kind = 'DISTRIBUTOR' AND dest_distributor_id IS NOT NULL AND dest_distributor_id = dest_ref AND dest_warehouse_id IS NULL AND dest_retailer_id IS NULL)
     OR (dest_kind = 'RETAILER'    AND dest_retailer_id IS NOT NULL AND dest_retailer_id = dest_ref AND dest_warehouse_id IS NULL AND dest_distributor_id IS NULL)),
    CONSTRAINT ck_sh_status CHECK (shipment_status IN ('IN_TRANSIT','DELIVERED','HELD','RETURNED')),
    CONSTRAINT ck_sh_dates CHECK (delivered_date IS NULL OR delivered_date >= ship_date)
);

CREATE TABLE shipment_items (
    shipment_id        VARCHAR(30)  NOT NULL,
    batch_id           VARCHAR(30)  NOT NULL,
    quantity_units     INTEGER      NOT NULL,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_shipment_items PRIMARY KEY (shipment_id, batch_id),
    CONSTRAINT fk_si_shipment FOREIGN KEY (shipment_id) REFERENCES shipments (shipment_id),
    CONSTRAINT fk_si_batch FOREIGN KEY (batch_id) REFERENCES production_batches (batch_id),
    CONSTRAINT ck_si_qty CHECK (quantity_units > 0)
);

CREATE TABLE quality_reports (
    report_id          VARCHAR(30)  NOT NULL,
    subject_kind       VARCHAR(5)   NOT NULL,
    subject_ref        VARCHAR(30)  NOT NULL,
    report_type        VARCHAR(30)  NOT NULL,
    issued_by          VARCHAR(120) NOT NULL,
    issued_date        DATE         NOT NULL,
    result_summary     VARCHAR(400) NOT NULL,
    outcome            VARCHAR(12)  NOT NULL,
    document_id        VARCHAR(40),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_quality_reports PRIMARY KEY (report_id),
    CONSTRAINT ck_qr_kind CHECK (subject_kind IN ('LOT','BATCH')),
    CONSTRAINT ck_qr_outcome CHECK (outcome IN ('PASS','FAIL','INCONCLUSIVE'))
);

CREATE TABLE contamination_incidents (
    incident_id        VARCHAR(30)  NOT NULL,
    title              VARCHAR(160) NOT NULL,
    source_kind        VARCHAR(5)   NOT NULL,
    source_ref         VARCHAR(30)  NOT NULL,
    contaminant        VARCHAR(120) NOT NULL,
    contamination_category VARCHAR(20) NOT NULL,
    severity           VARCHAR(10)  NOT NULL,
    supplier_id        VARCHAR(20),
    reported_by        VARCHAR(80)  NOT NULL,
    discovered_at      TIMESTAMP    NOT NULL,
    incident_status    VARCHAR(20)  NOT NULL DEFAULT 'REPORTED',
    description        VARCHAR(2000),
    is_demo            SMALLINT     NOT NULL DEFAULT 0,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_incidents PRIMARY KEY (incident_id),
    CONSTRAINT fk_inc_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id),
    CONSTRAINT ck_inc_kind CHECK (source_kind IN ('LOT','BATCH')),
    CONSTRAINT ck_inc_cat CHECK (contamination_category IN ('MICROBIAL','CHEMICAL','PHYSICAL','ALLERGEN','OTHER')),
    CONSTRAINT ck_inc_sev CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    CONSTRAINT ck_inc_status CHECK (incident_status IN ('REPORTED','INVESTIGATING','EVIDENCE_REVIEW',
        'RECALL_RECOMMENDED','PENDING_APPROVAL','APPROVED','REJECTED','EXECUTING','COMPLETED'))
);

CREATE TABLE incident_affected_lots (
    incident_id        VARCHAR(30)  NOT NULL,
    node_kind          VARCHAR(5)   NOT NULL,
    node_ref           VARCHAR(30)  NOT NULL,
    relation           VARCHAR(12)  NOT NULL,
    depth              INTEGER      NOT NULL,
    identified_by      VARCHAR(40)  NOT NULL,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_incident_affected PRIMARY KEY (incident_id, node_ref),
    CONSTRAINT fk_ial_incident FOREIGN KEY (incident_id) REFERENCES contamination_incidents (incident_id),
    CONSTRAINT ck_ial_kind CHECK (node_kind IN ('LOT','BATCH')),
    CONSTRAINT ck_ial_rel CHECK (relation IN ('SOURCE','DIRECT','INDIRECT','UPSTREAM'))
);

CREATE TABLE recall_campaigns (
    recall_id          VARCHAR(30)  NOT NULL,
    incident_id        VARCHAR(30)  NOT NULL,
    title              VARCHAR(200) NOT NULL,
    recall_class       VARCHAR(10)  NOT NULL,
    recall_status      VARCHAR(20)  NOT NULL DEFAULT 'PENDING_APPROVAL',
    risk_score         INTEGER      NOT NULL,
    risk_class         VARCHAR(10)  NOT NULL,
    risk_breakdown     CLOB(1M),
    plan_json          CLOB(2M),
    verification_json  CLOB(1M),
    instructions       CLOB(1M),
    generated_by       VARCHAR(40)  NOT NULL,
    decided_by         VARCHAR(80),
    decided_at         TIMESTAMP,
    decision_comment   VARCHAR(2000),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_recall_campaigns PRIMARY KEY (recall_id),
    CONSTRAINT fk_rc_incident FOREIGN KEY (incident_id) REFERENCES contamination_incidents (incident_id),
    CONSTRAINT ck_rc_class CHECK (recall_class IN ('CLASS_I','CLASS_II','CLASS_III')),
    CONSTRAINT ck_rc_status CHECK (recall_status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','EXECUTING','COMPLETED','SUPERSEDED')),
    CONSTRAINT ck_rc_score CHECK (risk_score BETWEEN 0 AND 100)
);

CREATE TABLE recall_affected_items (
    item_id            VARCHAR(40)  NOT NULL,
    recall_id          VARCHAR(30)  NOT NULL,
    batch_id           VARCHAR(30)  NOT NULL,
    product_id         VARCHAR(20)  NOT NULL,
    location_kind      VARCHAR(12)  NOT NULL,
    location_ref       VARCHAR(20)  NOT NULL,
    quantity_units     INTEGER      NOT NULL,
    priority           VARCHAR(4)   NOT NULL,
    inclusion_basis    VARCHAR(12)  NOT NULL,
    reason             VARCHAR(600) NOT NULL,
    evidence_refs      VARCHAR(600),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_recall_items PRIMARY KEY (item_id),
    CONSTRAINT fk_ri_recall FOREIGN KEY (recall_id) REFERENCES recall_campaigns (recall_id),
    CONSTRAINT fk_ri_batch FOREIGN KEY (batch_id) REFERENCES production_batches (batch_id),
    CONSTRAINT fk_ri_product FOREIGN KEY (product_id) REFERENCES finished_products (product_id),
    CONSTRAINT uq_ri UNIQUE (recall_id, batch_id, location_ref),
    CONSTRAINT ck_ri_loc CHECK (location_kind IN ('FACILITY','WAREHOUSE','DISTRIBUTOR','RETAILER')),
    CONSTRAINT ck_ri_prio CHECK (priority IN ('P1','P2','P3')),
    CONSTRAINT ck_ri_basis CHECK (inclusion_basis IN ('DIRECT','INDIRECT','PRECAUTIONARY'))
);

CREATE TABLE recall_actions (
    action_id          VARCHAR(40)  NOT NULL,
    recall_id          VARCHAR(30)  NOT NULL,
    location_kind      VARCHAR(12)  NOT NULL,
    location_ref       VARCHAR(20)  NOT NULL,
    action_type        VARCHAR(20)  NOT NULL,
    action_status      VARCHAR(16)  NOT NULL DEFAULT 'PENDING',
    units_expected     INTEGER      NOT NULL DEFAULT 0,
    units_recovered    INTEGER      NOT NULL DEFAULT 0,
    notes              VARCHAR(1000),
    channel            VARCHAR(20)  NOT NULL DEFAULT 'SIMULATED',
    updated_by         VARCHAR(80),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_recall_actions PRIMARY KEY (action_id),
    CONSTRAINT fk_ra_recall FOREIGN KEY (recall_id) REFERENCES recall_campaigns (recall_id),
    CONSTRAINT uq_ra UNIQUE (recall_id, location_ref, action_type),
    CONSTRAINT ck_ra_type CHECK (action_type IN ('NOTIFY','QUARANTINE','RECOVER')),
    CONSTRAINT ck_ra_status CHECK (action_status IN ('PENDING','SENT','ACKNOWLEDGED','IN_PROGRESS','DONE')),
    CONSTRAINT ck_ra_units CHECK (units_recovered >= 0 AND units_expected >= 0)
);

CREATE TABLE agent_investigations (
    run_id             VARCHAR(40)  NOT NULL,
    incident_id        VARCHAR(30)  NOT NULL,
    agent_name         VARCHAR(40)  NOT NULL,
    step_no            INTEGER      NOT NULL,
    execution_mode     VARCHAR(30)  NOT NULL,
    run_status         VARCHAR(12)  NOT NULL,
    output_json        CLOB(2M),
    log_text           CLOB(1M),
    started_at         TIMESTAMP,
    completed_at       TIMESTAMP,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_agent_inv PRIMARY KEY (run_id, agent_name),
    CONSTRAINT fk_ai_incident FOREIGN KEY (incident_id) REFERENCES contamination_incidents (incident_id),
    CONSTRAINT ck_ai_status CHECK (run_status IN ('QUEUED','RUNNING','COMPLETED','FAILED')),
    CONSTRAINT ck_ai_mode CHECK (execution_mode IN ('CREWAI_LLM','DETERMINISTIC_FALLBACK'))
);

CREATE TABLE audit_logs (
    audit_id           VARCHAR(40)  NOT NULL,
    occurred_at        TIMESTAMP    NOT NULL,
    actor              VARCHAR(80)  NOT NULL,
    actor_role         VARCHAR(30)  NOT NULL,
    action_name        VARCHAR(60)  NOT NULL,
    entity_kind        VARCHAR(30)  NOT NULL,
    entity_ref         VARCHAR(40)  NOT NULL,
    details            VARCHAR(4000),
    CONSTRAINT pk_audit_logs PRIMARY KEY (audit_id)
);

CREATE TABLE evidence_documents (
    document_id        VARCHAR(40)  NOT NULL,
    incident_id        VARCHAR(30),
    filename           VARCHAR(200) NOT NULL,
    doc_type           VARCHAR(30)  NOT NULL,
    mime_type          VARCHAR(80)  NOT NULL,
    size_bytes         INTEGER      NOT NULL,
    sha256             VARCHAR(64)  NOT NULL,
    page_count         INTEGER      NOT NULL DEFAULT 1,
    verification_status VARCHAR(16) NOT NULL DEFAULT 'UNVERIFIED',
    extracted_json     CLOB(1M),
    uploaded_by        VARCHAR(80)  NOT NULL,
    storage_path       VARCHAR(400) NOT NULL,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_evidence_documents PRIMARY KEY (document_id),
    CONSTRAINT fk_ed_incident FOREIGN KEY (incident_id) REFERENCES contamination_incidents (incident_id),
    CONSTRAINT uq_ed_sha UNIQUE (sha256),
    CONSTRAINT ck_ed_type CHECK (doc_type IN ('LAB_REPORT','SUPPLIER_CERTIFICATE','QC_RECORD','CONTAMINATION_NOTICE','OTHER')),
    CONSTRAINT ck_ed_ver CHECK (verification_status IN ('UNVERIFIED','VERIFIED','DISPUTED'))
);

-- Text chunks used for retrieval. embedding_json holds a portable JSON
-- vector; migration 003 adds a native Db2 VECTOR column when supported.
CREATE TABLE evidence_chunks (
    chunk_id           VARCHAR(50)  NOT NULL,
    document_id        VARCHAR(40)  NOT NULL,
    chunk_no           INTEGER      NOT NULL,
    page_no            INTEGER      NOT NULL,
    section_label      VARCHAR(120),
    content            VARCHAR(4000) NOT NULL,
    embedding_json     CLOB(64K),
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_evidence_chunks PRIMARY KEY (chunk_id),
    CONSTRAINT fk_ec_doc FOREIGN KEY (document_id) REFERENCES evidence_documents (document_id)
);

CREATE TABLE incident_comments (
    comment_id         VARCHAR(40)  NOT NULL,
    incident_id        VARCHAR(30)  NOT NULL,
    author             VARCHAR(80)  NOT NULL,
    author_role        VARCHAR(30)  NOT NULL,
    body               VARCHAR(2000) NOT NULL,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_incident_comments PRIMARY KEY (comment_id),
    CONSTRAINT fk_ic_incident FOREIGN KEY (incident_id) REFERENCES contamination_incidents (incident_id)
)
