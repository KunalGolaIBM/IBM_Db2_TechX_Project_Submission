CREATE TABLE suppliers (
    supplier_id VARCHAR(32) NOT NULL PRIMARY KEY,
    supplier_name VARCHAR(160) NOT NULL,
    lead_days INTEGER NOT NULL,
    reliability_score DECIMAL(5,2) DEFAULT 0
);
CREATE TABLE medicines (
    medicine_id VARCHAR(32) NOT NULL PRIMARY KEY,
    medicine_name VARCHAR(160) NOT NULL,
    reorder_level INTEGER NOT NULL DEFAULT 0,
    avg_daily_use DECIMAL(12,2) NOT NULL,
    supplier_id VARCHAR(32),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);
CREATE TABLE inventory (
    medicine_id VARCHAR(32) NOT NULL PRIMARY KEY,
    on_hand INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);
CREATE TABLE batches (
    batch_id VARCHAR(40) NOT NULL PRIMARY KEY,
    medicine_id VARCHAR(32) NOT NULL,
    quantity INTEGER NOT NULL,
    expiry_date DATE NOT NULL,
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);
CREATE TABLE usage_history (
    usage_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    medicine_id VARCHAR(32) NOT NULL,
    usage_date DATE NOT NULL,
    quantity_used INTEGER NOT NULL,
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);
CREATE TABLE recommendations (
    recommendation_id VARCHAR(36) NOT NULL PRIMARY KEY,
    medicine_id VARCHAR(32) NOT NULL,
    suggested_quantity INTEGER NOT NULL,
    days_of_cover DECIMAL(8,2) NOT NULL,
    rationale CLOB,
    status VARCHAR(24) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);
CREATE TABLE approval_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recommendation_id VARCHAR(36) NOT NULL,
    reviewer VARCHAR(100) NOT NULL,
    action VARCHAR(24) NOT NULL,
    approved_quantity INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id)
);
CREATE INDEX idx_batches_medicine_expiry ON batches(medicine_id, expiry_date);
CREATE INDEX idx_usage_medicine_date ON usage_history(medicine_id, usage_date);
CREATE INDEX idx_recommendations_status ON recommendations(status);
