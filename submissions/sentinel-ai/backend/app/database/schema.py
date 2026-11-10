import logging
from app.database.db2_connector import db_connector

logger = logging.getLogger("sentinel.schema")

TABLES = {
    "USER_ACCOUNTS": """
    CREATE TABLE IF NOT EXISTS USER_ACCOUNTS (
        user_id VARCHAR(64) PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        email VARCHAR(150) NOT NULL UNIQUE,
        role VARCHAR(100) NOT NULL,
        department VARCHAR(100) NOT NULL,
        security_clearance VARCHAR(50) NOT NULL,
        status VARCHAR(50) DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    
    "LOGIN_EVENTS": """
    CREATE TABLE IF NOT EXISTS LOGIN_EVENTS (
        event_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address VARCHAR(45) NOT NULL,
        device_name VARCHAR(150),
        device_type VARCHAR(50),
        location VARCHAR(100),
        status VARCHAR(20) NOT NULL, -- 'SUCCESS' or 'FAILURE'
        failure_reason VARCHAR(255),
        user_agent VARCHAR(255)
    );
    """,
    
    "ACCESS_LOGS": """
    CREATE TABLE IF NOT EXISTS ACCESS_LOGS (
        log_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resource_id VARCHAR(100) NOT NULL,
        resource_name VARCHAR(255) NOT NULL,
        resource_type VARCHAR(100) NOT NULL,
        access_type VARCHAR(50) NOT NULL, -- 'READ', 'WRITE', 'EXECUTE', 'EXPORT'
        status VARCHAR(20) NOT NULL, -- 'ALLOWED' or 'DENIED'
        classification_level VARCHAR(50) NOT NULL -- 'UNCLASSIFIED', 'CONFIDENTIAL', 'SECRET', 'TOP_SECRET'
    );
    """,
    
    "SECURITY_ALERTS": """
    CREATE TABLE IF NOT EXISTS SECURITY_ALERTS (
        alert_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        event_type VARCHAR(100) NOT NULL,
        severity VARCHAR(20) NOT NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
        description TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        correlated_incident_id VARCHAR(64),
        status VARCHAR(50) DEFAULT 'OPEN'
    );
    """,
    
    "INCIDENTS": """
    CREATE TABLE IF NOT EXISTS INCIDENTS (
        incident_id VARCHAR(64) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        user_id VARCHAR(64) NOT NULL,
        status VARCHAR(50) DEFAULT 'INVESTIGATING', -- 'INVESTIGATING', 'CONTAINED', 'RESOLVED', 'CLOSED'
        severity VARCHAR(20) NOT NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
        risk_score INTEGER NOT NULL, -- 0 to 100
        mitre_technique_ids TEXT, -- JSON or comma-separated
        summary TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    
    "AI_ANALYSIS": """
    CREATE TABLE IF NOT EXISTS AI_ANALYSIS (
        analysis_id VARCHAR(64) PRIMARY KEY,
        incident_id VARCHAR(64) NOT NULL,
        agent_name VARCHAR(100) NOT NULL,
        analysis_type VARCHAR(100) NOT NULL,
        findings TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        confidence_score REAL NOT NULL, -- 0.0 to 1.0
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    
    "RESPONSE_RECOMMENDATIONS": """
    CREATE TABLE IF NOT EXISTS RESPONSE_RECOMMENDATIONS (
        recommendation_id VARCHAR(64) PRIMARY KEY,
        incident_id VARCHAR(64) NOT NULL,
        action_type VARCHAR(100) NOT NULL, -- 'LOCK_ACCOUNT', 'REVOKE_SESSIONS', 'FORCE_MFA_RESET', 'ISOLATE_ENDPOINT'
        description TEXT NOT NULL,
        status VARCHAR(50) DEFAULT 'PENDING_APPROVAL', -- 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXECUTED'
        approved_by VARCHAR(100),
        approved_at TIMESTAMP,
        execution_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
}

def init_database_tables():
    """Initializes all 7 tables in Db2 or SQLite."""
    logger.info("Initializing SENTINEL AI database tables...")
    for table_name, ddl in TABLES.items():
        try:
            db_connector.execute_update(ddl)
            logger.info(f"Verified table: {table_name}")
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {e}")

