-- ============================================================
-- MediTwin AI — IBM Db2 Database Schema
-- IBM Db2Hack 2026
-- ============================================================

-- ============================================================
-- PATIENT table
-- ============================================================
CREATE TABLE PATIENT (
    patient_id      INTEGER       NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    demo_code       VARCHAR(20)   NOT NULL,
    display_name    VARCHAR(100)  NOT NULL,
    birth_year      INTEGER,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_patient PRIMARY KEY (patient_id),
    CONSTRAINT uq_patient_code UNIQUE (demo_code)
);

-- ============================================================
-- DOCUMENT table
-- ============================================================
CREATE TABLE DOCUMENT (
    document_id     INTEGER       NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    patient_id      INTEGER       NOT NULL,
    file_name       VARCHAR(255)  NOT NULL,
    document_type   VARCHAR(50)   NOT NULL DEFAULT 'LAB_REPORT',
    extracted_text  CLOB,
    uploaded_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parse_status    VARCHAR(20)   NOT NULL DEFAULT 'PENDING',
    source_hash     VARCHAR(64),
    CONSTRAINT pk_document PRIMARY KEY (document_id),
    CONSTRAINT fk_document_patient FOREIGN KEY (patient_id)
        REFERENCES PATIENT (patient_id) ON DELETE CASCADE,
    CONSTRAINT uq_doc_patient UNIQUE (document_id, patient_id),
    CONSTRAINT uq_patient_source_hash UNIQUE (patient_id, source_hash),
    CONSTRAINT ck_doc_parse_status CHECK (parse_status IN ('PENDING', 'PARSED', 'FAILED'))
);

CREATE INDEX idx_document_patient ON DOCUMENT (patient_id);
CREATE INDEX idx_document_status ON DOCUMENT (parse_status);

-- ============================================================
-- OBSERVATION table
-- ============================================================
CREATE TABLE OBSERVATION (
    observation_id          INTEGER        NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    patient_id              INTEGER        NOT NULL,
    document_id             INTEGER        NOT NULL,
    test_code               VARCHAR(50),
    test_name               VARCHAR(200)   NOT NULL,
    value_numeric           DECIMAL(12,4),
    value_text              VARCHAR(500),
    unit                    VARCHAR(50),
    original_value_numeric  DECIMAL(12,4),
    original_unit           VARCHAR(50),
    corrected_value_numeric DECIMAL(12,4),
    corrected_unit          VARCHAR(50),
    reference_low           DECIMAL(12,4),
    reference_high          DECIMAL(12,4),
    observed_at             DATE,
    source_page             INTEGER,
    source_snippet          VARCHAR(500),
    extraction_confidence   DECIMAL(3,2),
    review_status           VARCHAR(20)    NOT NULL DEFAULT 'PENDING',
    reviewed_by             VARCHAR(100),
    reviewed_at             TIMESTAMP,
    created_at              TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_observation PRIMARY KEY (observation_id),
    CONSTRAINT fk_obs_doc_patient FOREIGN KEY (document_id, patient_id)
        REFERENCES DOCUMENT (document_id, patient_id) ON DELETE CASCADE,
    CONSTRAINT ck_obs_review_status CHECK (review_status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE INDEX idx_obs_patient ON OBSERVATION (patient_id);
CREATE INDEX idx_obs_patient_test ON OBSERVATION (patient_id, test_code);
CREATE INDEX idx_obs_review ON OBSERVATION (review_status);
CREATE INDEX idx_obs_date ON OBSERVATION (observed_at);

-- ============================================================
-- TIMELINE_EVENT table
-- ============================================================
CREATE TABLE TIMELINE_EVENT (
    event_id              INTEGER        NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    patient_id            INTEGER        NOT NULL,
    event_type            VARCHAR(50)    NOT NULL,
    event_time            TIMESTAMP      NOT NULL,
    title                 VARCHAR(200)   NOT NULL,
    summary               VARCHAR(1000),
    related_document_id   INTEGER,
    CONSTRAINT pk_timeline_event PRIMARY KEY (event_id),
    CONSTRAINT fk_timeline_patient FOREIGN KEY (patient_id)
        REFERENCES PATIENT (patient_id) ON DELETE CASCADE,
    CONSTRAINT fk_timeline_document FOREIGN KEY (related_document_id)
        REFERENCES DOCUMENT (document_id) ON DELETE SET NULL
);

CREATE INDEX idx_timeline_patient ON TIMELINE_EVENT (patient_id);
CREATE INDEX idx_timeline_time ON TIMELINE_EVENT (event_time);

-- ============================================================
-- AUDIT_LOG table (append-only)
-- ============================================================
CREATE TABLE AUDIT_LOG (
    audit_id      INTEGER        NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    actor_id      VARCHAR(100)   NOT NULL DEFAULT 'SYSTEM',
    action        VARCHAR(50)    NOT NULL,
    entity_type   VARCHAR(50)    NOT NULL,
    entity_id     INTEGER,
    details_json  CLOB,
    logged_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_audit_log PRIMARY KEY (audit_id)
);

CREATE INDEX idx_audit_time ON AUDIT_LOG (logged_at);
CREATE INDEX idx_audit_entity ON AUDIT_LOG (entity_type, entity_id);
