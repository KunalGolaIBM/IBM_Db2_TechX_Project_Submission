-- ========================================================================
-- IBM Db2 TechX Summit 2026: Native Db2 Schema Definition
-- Run directly in IBM Db2 Community Edition (db2 -tvf schema_db2.sql)
-- ========================================================================

CREATE TABLE incidents (
    id VARCHAR(32) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description CLOB(1M) NOT NULL,
    service VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    current_step VARCHAR(100) NOT NULL,
    workflow VARCHAR(100),
    resolution CLOB(1M),
    escalation_reason CLOB(1M),
    retry_count INT DEFAULT 0 NOT NULL,
    metadata CLOB(1M),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE incident_events (
    event_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id VARCHAR(32) NOT NULL,
    event VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL,
    step VARCHAR(100) NOT NULL,
    details CLOB(1M),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_event_incident FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

CREATE TABLE incident_actions (
    action_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    status VARCHAR(30) NOT NULL,
    result CLOB(1M),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT fk_action_incident FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

CREATE TABLE incident_knowledge_docs (
    doc_id VARCHAR(64) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    service VARCHAR(100) NOT NULL,
    content CLOB(1M) NOT NULL,
    resolution_steps CLOB(1M) NOT NULL,
    metadata CLOB(1M),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_incidents_status ON incidents (status);
CREATE INDEX idx_incidents_service ON incidents (service);
CREATE INDEX idx_incidents_severity ON incidents (severity);
CREATE INDEX idx_incidents_created ON incidents (created_at DESC);
CREATE INDEX idx_events_incident ON incident_events (incident_id, timestamp);
CREATE INDEX idx_actions_incident ON incident_actions (incident_id);
CREATE INDEX idx_docs_service ON incident_knowledge_docs (service);
