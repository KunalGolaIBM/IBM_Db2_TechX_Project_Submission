-- ========================================================================
-- IBM Db2 TechX Summit 2026: Db2 WorkRelay Intelligence
-- Schema Definition for Incident Persistence, Audit Events & Knowledge Base
-- Compatible with IBM Db2 11.5 / 12.1+ and local test mock databases
-- ========================================================================

-- 1. Main Incidents Table
CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(32) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description CLOB NOT NULL,
    service VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    current_step VARCHAR(100) NOT NULL,
    workflow VARCHAR(100),
    resolution CLOB,
    escalation_reason CLOB,
    retry_count INT DEFAULT 0 NOT NULL,
    metadata CLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 2. Incident Audit Lifecycle Events Table
CREATE TABLE IF NOT EXISTS incident_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id VARCHAR(32) NOT NULL,
    event VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL,
    step VARCHAR(100) NOT NULL,
    details CLOB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

-- 3. Incident Remediation Actions Table
CREATE TABLE IF NOT EXISTS incident_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    status VARCHAR(30) NOT NULL,
    result CLOB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
);

-- 4. Incident Knowledge Base & Runbooks Table (for LlamaIndex Retrieval)
CREATE TABLE IF NOT EXISTS incident_knowledge_docs (
    doc_id VARCHAR(64) NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    service VARCHAR(100) NOT NULL,
    content CLOB NOT NULL,
    resolution_steps CLOB NOT NULL,
    metadata CLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for fast filtering and reporting in enterprise operations
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents (service);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents (severity);
CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_incident ON incident_events (incident_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_actions_incident ON incident_actions (incident_id);
CREATE INDEX IF NOT EXISTS idx_docs_service ON incident_knowledge_docs (service);
