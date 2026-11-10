-- ============================================================================
-- IBM Db2 Hack 2026: Citizen Grievance Portal Database Schema (DDL Reference)
-- Database: GRIEVDB
-- Schema: DB2INST1
-- NOTE: Schema creation is executed via SQLAlchemy create_all in database.py
-- to maintain a single source of truth for table and column definitions.
-- ============================================================================

-- Connect to database
CONNECT TO GRIEVDB;

-- 1. Departments Table
CREATE TABLE departments (
    id INT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    nodal_email VARCHAR(150),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);

-- 2. Grievances Table
CREATE TABLE grievances (
    id INT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    tracking_id VARCHAR(32) NOT NULL UNIQUE,
    citizen_name VARCHAR(150) NOT NULL,
    contact VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description VARCHAR(3000) NOT NULL,
    ward VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
    status VARCHAR(50) NOT NULL DEFAULT 'Filed',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    resolved_at TIMESTAMP,
    department_id INT,
    subject VARCHAR(255),
    state VARCHAR(100) DEFAULT 'Delhi (NCT)',
    pincode VARCHAR(10),
    latitude DOUBLE,
    longitude DOUBLE,
    CONSTRAINT fk_grv_department FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE INDEX idx_grv_tracking_id ON grievances(tracking_id);
CREATE INDEX idx_grv_category ON grievances(category);
CREATE INDEX idx_grv_ward ON grievances(ward);
CREATE INDEX idx_grv_status ON grievances(status);
CREATE INDEX idx_grv_priority ON grievances(priority);
CREATE INDEX idx_grv_created_at ON grievances(created_at);

-- 3. Grievance Status History / Audit Log Table
CREATE TABLE grievance_updates (
    id INT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
    grievance_id INT NOT NULL,
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    notes VARCHAR(1000),
    updated_by VARCHAR(100) NOT NULL DEFAULT 'System',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT fk_upd_grievance FOREIGN KEY (grievance_id) REFERENCES grievances(id) ON DELETE CASCADE
);

CREATE INDEX idx_upd_grievance_id ON grievance_updates(grievance_id);

-- ============================================================================
-- 4. Native IBM Db2 Stored Procedure: Automated SLA Escalation Engine
-- ============================================================================
-- Procedure: SP_ESCALATE_OVERDUE
-- Evaluates continuous date arithmetic on Db2 engine: (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15
-- Automatically escalates lingering dockets to Critical and returns count.
CREATE OR REPLACE PROCEDURE SP_ESCALATE_OVERDUE (OUT escalated_count INT)
LANGUAGE SQL
BEGIN
    DECLARE v_count INT DEFAULT 0;

    -- Count open grievances exceeding statutory 15-day SLA
    SELECT COUNT(*) INTO v_count
    FROM grievances
    WHERE status != 'Resolved'
      AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15;

    -- Automatically elevate priority to Critical for overdue dockets
    UPDATE grievances
    SET priority = 'Critical'
    WHERE status != 'Resolved'
      AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15
      AND priority != 'Critical';

    SET escalated_count = v_count;
END;

-- ============================================================================
-- 5. Native IBM Db2 Kernel Trigger: Automated Audit Trail Engine
-- ============================================================================
-- Trigger: TRG_AUDIT_STATUS_CHANGE
-- Automatically captures priority and status changes directly at the Db2 kernel level,
-- writing an immutable audit record to grievance_updates for ACID compliance.
BEGIN
  DECLARE CONTINUE HANDLER FOR SQLSTATE '42704' BEGIN END;
  EXECUTE IMMEDIATE 'DROP TRIGGER TRG_AUDIT_STATUS_CHANGE';
END;

CREATE TRIGGER TRG_AUDIT_STATUS_CHANGE
AFTER UPDATE OF status, priority ON grievances
REFERENCING OLD AS O NEW AS N
FOR EACH ROW
WHEN (N.status <> O.status OR N.priority <> O.priority)
INSERT INTO grievance_updates (
    grievance_id, 
    previous_status, 
    new_status, 
    notes, 
    updated_by, 
    created_at
) VALUES (
    N.id, 
    O.status, 
    N.status, 
    CONCAT('Kernel Trigger Audit: Priority changed to ', CONCAT(N.priority, CONCAT(', Status changed to ', N.status))), 
    'Db2 Engine (TRG_AUDIT_STATUS_CHANGE)', 
    CURRENT TIMESTAMP
);

-- Commit transaction
COMMIT;
