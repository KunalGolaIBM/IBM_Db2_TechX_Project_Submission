-- COLDCHAIN_DB schema for ColdChain Guardian
-- Ensure the database COLDCHAIN_DB exists before running this script.

-- 1. PRODUCTS
CREATE TABLE PRODUCTS (
    product_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    product_category VARCHAR(100),
    min_temperature FLOAT NOT NULL,
    max_temperature FLOAT NOT NULL,
    sensitivity_level VARCHAR(50)
);

-- 2. SHIPMENTS
CREATE TABLE SHIPMENTS (
    shipment_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id INTEGER NOT NULL,
    vehicle_id VARCHAR(100),
    source_location VARCHAR(200),
    destination_location VARCHAR(200),
    shipment_status VARCHAR(50),
    departure_time TIMESTAMP,
    expected_arrival TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES PRODUCTS(product_id) ON DELETE CASCADE
);

-- 3. SENSOR_READINGS
CREATE TABLE SENSOR_READINGS (
    reading_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shipment_id INTEGER NOT NULL,
    temperature FLOAT NOT NULL,
    humidity FLOAT,
    recorded_at TIMESTAMP NOT NULL,
    FOREIGN KEY (shipment_id) REFERENCES SHIPMENTS(shipment_id) ON DELETE CASCADE
);

-- 4. INCIDENTS
CREATE TABLE INCIDENTS (
    incident_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shipment_id INTEGER NOT NULL,
    incident_type VARCHAR(100),
    severity VARCHAR(20),
    description CLOB,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES SHIPMENTS(shipment_id) ON DELETE CASCADE
);

-- 5. RISK_ASSESSMENTS
CREATE TABLE RISK_ASSESSMENTS (
    assessment_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id INTEGER NOT NULL,
    risk_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    explanation CLOB,
    assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES INCIDENTS(incident_id) ON DELETE CASCADE
);

-- 6. RECOMMENDATIONS
CREATE TABLE RECOMMENDATIONS (
    recommendation_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id INTEGER NOT NULL,
    action VARCHAR(200) NOT NULL,
    justification CLOB,
    priority INTEGER,
    approval_status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES INCIDENTS(incident_id) ON DELETE CASCADE
);

-- 7. KNOWLEDGE_DOCUMENTS
CREATE TABLE KNOWLEDGE_DOCUMENTS (
    document_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    content CLOB,
    source VARCHAR(200),
    embedding BLOB -- placeholder for vector (use LANGCHAIN_DB2 vector column if available)
);

-- 8. AUDIT_LOGS
CREATE TABLE AUDIT_LOGS (
    log_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id INTEGER,
    agent_name VARCHAR(100),
    action_taken VARCHAR(200),
    details CLOB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES INCIDENTS(incident_id) ON DELETE CASCADE
);

-- Indexes for fast look‑ups
CREATE INDEX idx_sensor_shipment ON SENSOR_READINGS(shipment_id);
CREATE INDEX idx_incident_shipment ON INCIDENTS(shipment_id);
CREATE INDEX idx_risk_incident ON RISK_ASSESSMENTS(incident_id);
CREATE INDEX idx_rec_incident ON RECOMMENDATIONS(incident_id);

