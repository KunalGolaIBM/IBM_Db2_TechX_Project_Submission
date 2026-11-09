-- PACT — Procurement Audit & Counterfactual Triage
-- Schema Migration 002: Case Management & Audit Tables
-- Target Database: IBM Db2 Community Edition (12.1.5.0)

-- 1. Investigation Cases
CREATE TABLE investigation_cases (
    id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    case_number VARCHAR(32) NOT NULL UNIQUE,
    po_line_id INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    priority VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',
    version INTEGER NOT NULL DEFAULT 1,
    summary VARCHAR(512),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT fk_case_poline FOREIGN KEY (po_line_id) REFERENCES po_lines(id),
    CONSTRAINT chk_case_status CHECK (status IN ('OPEN', 'INVESTIGATING', 'AWAITING_REVIEW', 'REVIEWED', 'NEEDS_EVIDENCE')),
    CONSTRAINT chk_case_priority CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
);

-- 2. Case Findings (Detected Rule Anomalies)
CREATE TABLE case_findings (
    id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    case_id INTEGER NOT NULL,
    rule_id VARCHAR(32) NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    status VARCHAR(16) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    discrepancy_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    details VARCHAR(1024) NOT NULL,
    evidence_refs VARCHAR(1024),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT fk_finding_case FOREIGN KEY (case_id) REFERENCES investigation_cases(id) ON DELETE CASCADE,
    CONSTRAINT chk_finding_status CHECK (status IN ('FAIL', 'UNKNOWN', 'PASS')),
    CONSTRAINT chk_finding_severity CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'))
);

-- 3. Scenario Runs (Counterfactual Simulations)
CREATE TABLE scenario_runs (
    id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    case_id INTEGER NOT NULL,
    simulation_type VARCHAR(64) NOT NULL,
    parameters VARCHAR(1024) NOT NULL,
    original_findings_count INTEGER NOT NULL,
    simulated_findings_count INTEGER NOT NULL,
    delta_summary VARCHAR(1024) NOT NULL,
    is_recommended SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT fk_scenario_case FOREIGN KEY (case_id) REFERENCES investigation_cases(id) ON DELETE CASCADE
);

-- 4. Review Decisions (Auditor/Human Action)
CREATE TABLE review_decisions (
    id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    case_id INTEGER NOT NULL,
    decision VARCHAR(32) NOT NULL,
    reviewer VARCHAR(64) NOT NULL,
    reviewer_notes VARCHAR(2048) NOT NULL,
    rationale VARCHAR(1024),
    decided_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT fk_decision_case FOREIGN KEY (case_id) REFERENCES investigation_cases(id) ON DELETE CASCADE,
    CONSTRAINT chk_decision_type CHECK (decision IN ('FINDING_CONFIRMED', 'EXCEPTION_APPROVED', 'ESCALATED', 'ADDITIONAL_EVIDENCE_REQUESTED'))
);

-- 5. Audit Events (Immutable Chronological Audit Log)
CREATE TABLE audit_events (
    id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    case_id INTEGER,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    actor VARCHAR(64) NOT NULL DEFAULT 'SYSTEM',
    action_details VARCHAR(2048) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT fk_audit_case FOREIGN KEY (case_id) REFERENCES investigation_cases(id) ON DELETE CASCADE
);

-- Performance Indexes
CREATE INDEX idx_case_poline ON investigation_cases(po_line_id);
CREATE INDEX idx_case_status ON investigation_cases(status);
CREATE INDEX idx_findings_case ON case_findings(case_id);
CREATE INDEX idx_findings_rule ON case_findings(rule_id);
CREATE INDEX idx_scenario_case ON scenario_runs(case_id);
CREATE INDEX idx_decision_case ON review_decisions(case_id);
CREATE INDEX idx_audit_case ON audit_events(case_id);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);
